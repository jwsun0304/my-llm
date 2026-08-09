/************************************************************
 * kem_standalone_test.c
 *
 * Standalone ML-KEM-512 hardware test on single Zynq/ZCU board.
 * Sequence:
 *   1) KEYGEN  : randombytes(64B) -> sk, ek
 *   2) ENCAP   : ek + random msg(32B) -> ssk_enc, ct
 *   3) DECAP   : sk + ct -> ssk_dec
 *   4) COMPARE : ssk_enc == ssk_dec
 *
 * This file intentionally removes network / AES / DSA / video logic.
 * It uses only KEM AXI-Lite + DMA0 + shared DMA buffer through /dev/mem.
 *
 * Build on PetaLinux:
 *   gcc -O2 -Wall -Wextra -o kem_standalone_test kem_standalone_test.c
 *
 * Run:
 *   sudo ./kem_standalone_test
 *   sudo ./kem_standalone_test 1
 ************************************************************/

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <dirent.h>
#include <errno.h>
#include <time.h>
#include <inttypes.h>

// =======================================================
// Address Map: adjust only if your Vivado address map changed
// =======================================================
#define KEM_BASE        0xA0010000UL
#define KEM_RANGE       0x10000UL

#define DMA0_BASE       0xA0000000UL
#define DMA_RANGE       0x10000UL

#define DMA_BUF_BASE    0x60000000UL
#define DMA_BUF_SIZE    0x01000000UL

#define DMA_KEM_IN_OFFSET   0x00000000UL
#define DMA_KEM_OUT_OFFSET  0x00001000UL

// =======================================================
// AXI DMA registers
// =======================================================
#define MM2S_DMACR     0x00
#define MM2S_DMASR     0x04
#define MM2S_SA        0x18
#define MM2S_SA_MSB    0x1C
#define MM2S_LENGTH    0x28

#define S2MM_DMACR     0x30
#define S2MM_DMASR     0x34
#define S2MM_DA        0x48
#define S2MM_DA_MSB    0x4C
#define S2MM_LENGTH    0x58

#define DMA_RESET      0x4
#define DMA_RS         0x1

#define DMASR_HALTED   (1u << 0)
#define DMASR_IDLE     (1u << 1)
#define DMASR_INTERR   (1u << 4)
#define DMASR_SLVERR   (1u << 5)
#define DMASR_DECERR   (1u << 6)
#define DMASR_IOC_IRQ  (1u << 12)
#define DMASR_ERR_IRQ  (1u << 14)

#define DMA_ERROR_MASK (DMASR_INTERR | DMASR_SLVERR | DMASR_DECERR | DMASR_ERR_IRQ)

// =======================================================
// ML-KEM-512 sizes used by the current RTL/software flow
// =======================================================
#define KEM512_RANDOM_BYTES     64u
#define KEM512_SECRET_VEC_BYTES 768u
#define KEM512_EK_BYTES         800u
#define KEM512_HEK_BYTES        32u
#define KEM512_EXTRA_BYTES      64u
#define KEM512_DK_FILE_BYTES    (KEM512_SECRET_VEC_BYTES + KEM512_HEK_BYTES + KEM512_EK_BYTES) // 1600
#define KEM512_KEYGEN_OUT_BYTES (KEM512_SECRET_VEC_BYTES + KEM512_EK_BYTES + KEM512_EXTRA_BYTES) // 1632
#define KEM512_MSG_BYTES        32u
#define KEM512_CT_BYTES         768u
#define KEM512_SSK_BYTES        32u
#define KEM512_ENCAP_IN_BYTES   (KEM512_EK_BYTES + KEM512_MSG_BYTES) // 832
#define KEM512_ENCAP_OUT_BYTES  (KEM512_SSK_BYTES + KEM512_CT_BYTES) // 800

// Decap stream format used by the existing RTL interface:
// 128 words: 6B secret_vector + 2B ct
//  64 words: remaining ct
//   4 words: H(ek)
// 100 words: ek
#define KEM512_DECAP_IN_WORDS   (128u + 64u + 4u + 100u)
#define KEM512_DECAP_IN_BYTES   (KEM512_DECAP_IN_WORDS * 8u) // 2368
#define KEM512_DECAP_OUT_BYTES  32u

// KEM AXI-Lite control values from existing flow
#define KEM_REG_CTRL        0x00
#define KEM_REG_RESET       0x08
#define KEM_CTRL_KEYGEN_512 0x05u  // mode_func=01, mode_k=01
#define KEM_CTRL_ENCAP_512  0x06u  // mode_func=10, mode_k=01
#define KEM_CTRL_DECAP_512  0x07u  // mode_func=11, mode_k=01

#define KEM_TIMEOUT_US      5000000.0  // 5 seconds safety timeout
#define VERBOSE_DUMP        1

// =======================================================
// Globals
// =======================================================
static int mem_fd = -1;
static volatile uint32_t *kem_reg  = NULL;
static volatile uint32_t *dma0_reg = NULL;
static volatile uint8_t  *dma_buf_virt = NULL;
static unsigned int kem_reset_count = 0;

// =======================================================
// Basic utilities
// =======================================================
static double now_usec(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec * 1e6 + (double)ts.tv_nsec / 1e3;
}

static void timing_log(const char *op, const char *step, double step_t0, double total_t0)
{
    double now = now_usec();
    printf("[%s][TIME] %-34s step=%10.0f us total=%10.0f us\n",
           op, step, now - step_t0, now - total_t0);
}

static void timing_mark(const char *op, const char *msg, double total_t0)
{
    printf("[%s][MARK] %-34s total=%10.0f us\n",
           op, msg, now_usec() - total_t0);
}

static inline void mmio_write(volatile uint32_t *base, uint32_t offset, uint32_t value)
{
    base[offset >> 2] = value;
}

static inline uint32_t mmio_read(volatile uint32_t *base, uint32_t offset)
{
    return base[offset >> 2];
}

static void *map_region(off_t base, size_t range, const char *name)
{
    void *p = mmap(NULL, range, PROT_READ | PROT_WRITE, MAP_SHARED, mem_fd, base);
    if (p == MAP_FAILED) {
        fprintf(stderr, "[MMIO][ERR] mmap %s failed: base=0x%08lX range=0x%zX errno=%d (%s)\n",
                name, (unsigned long)base, range, errno, strerror(errno));
        exit(EXIT_FAILURE);
    }
    printf("[MMIO] mapped %-8s base=0x%08lX range=0x%zX virt=%p\n",
           name, (unsigned long)base, range, p);
    return p;
}

static void mmio_init(void)
{
    printf("[MMIO] Opening /dev/mem\n");
    mem_fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (mem_fd < 0) {
        fprintf(stderr, "[MMIO][ERR] open /dev/mem failed: errno=%d (%s)\n", errno, strerror(errno));
        exit(EXIT_FAILURE);
    }

    kem_reg = (volatile uint32_t *)map_region((off_t)KEM_BASE, KEM_RANGE, "KEM");
    dma0_reg = (volatile uint32_t *)map_region((off_t)DMA0_BASE, DMA_RANGE, "DMA0");

    dma_buf_virt = (volatile uint8_t *)mmap(NULL, DMA_BUF_SIZE,
                                            PROT_READ | PROT_WRITE,
                                            MAP_SHARED, mem_fd,
                                            (off_t)DMA_BUF_BASE);
    if (dma_buf_virt == MAP_FAILED) {
        fprintf(stderr, "[MMIO][ERR] mmap DMA buffer failed: base=0x%08lX size=0x%zX errno=%d (%s)\n",
                (unsigned long)DMA_BUF_BASE, (size_t)DMA_BUF_SIZE, errno, strerror(errno));
        exit(EXIT_FAILURE);
    }
    printf("[MMIO] mapped DMA_BUF base=0x%08lX size=0x%zX virt=%p\n",
           (unsigned long)DMA_BUF_BASE, (size_t)DMA_BUF_SIZE, (void *)dma_buf_virt);
}

static void mmio_deinit(void)
{
    if (dma_buf_virt && dma_buf_virt != MAP_FAILED) munmap((void *)dma_buf_virt, DMA_BUF_SIZE);
    if (dma0_reg) munmap((void *)dma0_reg, DMA_RANGE);
    if (kem_reg) munmap((void *)kem_reg, KEM_RANGE);
    if (mem_fd >= 0) close(mem_fd);
}

static void dev_memset8(volatile uint8_t *dst, uint8_t value, size_t len)
{
    for (size_t i = 0; i < len; i++) dst[i] = value;
}

static void dev_memcpy_to8(volatile uint8_t *dst, const uint8_t *src, size_t len)
{
    for (size_t i = 0; i < len; i++) dst[i] = src[i];
}

static void dev_memcpy_from8(uint8_t *dst, const volatile uint8_t *src, size_t len)
{
    for (size_t i = 0; i < len; i++) dst[i] = src[i];
}

static int fill_random_bytes(uint8_t *buf, size_t len)
{
    int fd = open("/dev/urandom", O_RDONLY);
    if (fd < 0) {
        fprintf(stderr, "[RAND][ERR] open /dev/urandom failed: %s\n", strerror(errno));
        return -1;
    }

    size_t got = 0;
    while (got < len) {
        ssize_t r = read(fd, buf + got, len - got);
        if (r < 0) {
            if (errno == EINTR) continue;
            fprintf(stderr, "[RAND][ERR] read /dev/urandom failed: %s\n", strerror(errno));
            close(fd);
            return -1;
        }
        if (r == 0) {
            fprintf(stderr, "[RAND][ERR] /dev/urandom returned EOF\n");
            close(fd);
            return -1;
        }
        got += (size_t)r;
    }

    close(fd);
    return 0;
}

static void print_hex_line(const char *tag, const uint8_t *buf, size_t len)
{
    printf("[%s] ", tag);
    for (size_t i = 0; i < len; i++) printf("%02X", buf[i]);
    printf("\n");
}

static void dump_bytes_hex(const char *tag, const volatile uint8_t *buf, size_t len)
{
#if VERBOSE_DUMP
    printf("\n[%s] BYTE DUMP START len=%zu\n", tag, len);
    for (size_t i = 0; i < len; i += 16) {
        printf("[%s][%04zu] ", tag, i);
        for (size_t j = 0; j < 16; j++) {
            if (i + j < len) printf("%02X ", buf[i + j]);
            else             printf("   ");
        }
        printf(" | ");
        for (size_t j = 0; j < 16 && i + j < len; j++) {
            uint8_t c = buf[i + j];
            printf("%c", (c >= 0x20 && c <= 0x7E) ? (char)c : 46);
        }
        printf("\n");
    }
    printf("[%s] BYTE DUMP END\n", tag);
#else
    (void)tag;
    (void)buf;
    (void)len;
#endif
}

static void dump_words64_be(const char *tag, const volatile uint8_t *buf, size_t len)
{
#if VERBOSE_DUMP
    printf("\n[%s] U64 DUMP START len=%zu\n", tag, len);
    for (size_t i = 0; i < len; i += 8) {
        uint64_t w = 0;
        size_t remain = (len - i >= 8) ? 8 : (len - i);
        for (size_t j = 0; j < remain; j++) w = (w << 8) | buf[i + j];
        for (size_t j = remain; j < 8; j++) w <<= 8;
        printf("[%s][%04zu] 0x%016" PRIX64 "\n", tag, i / 8, w);
    }
    printf("[%s] U64 DUMP END\n\n", tag);
#else
    (void)tag;
    (void)buf;
    (void)len;
#endif
}

// =======================================================
// Directory / file utilities
// =======================================================
static int ensure_dir(const char *path)
{
    struct stat st;
    if (stat(path, &st) == 0) {
        if (S_ISDIR(st.st_mode)) return 0;
        fprintf(stderr, "[DIR][ERR] %s exists but is not a directory\n", path);
        return -1;
    }
    if (mkdir(path, 0777) != 0) {
        fprintf(stderr, "[DIR][ERR] mkdir %s failed: %s\n", path, strerror(errno));
        return -1;
    }
    return 0;
}

static void clean_dir(const char *path)
{
    DIR *dir = opendir(path);
    if (!dir) return;

    struct dirent *entry;
    char fullpath[512];

    while ((entry = readdir(dir)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) continue;
        snprintf(fullpath, sizeof(fullpath), "%s/%s", path, entry->d_name);

        struct stat st;
        if (stat(fullpath, &st) != 0) continue;

        if (S_ISDIR(st.st_mode)) {
            clean_dir(fullpath);
            rmdir(fullpath);
        } else {
            unlink(fullpath);
        }
    }
    closedir(dir);
}

static int prepare_dirs(void)
{
    const char *dirs[] = {
        "enc_key", "sk", "ssk", "ssk_dec", "cipher", "sb", "randombytes"
    };

    for (size_t i = 0; i < sizeof(dirs) / sizeof(dirs[0]); i++) {
        if (ensure_dir(dirs[i]) != 0) return -1;
        clean_dir(dirs[i]);
    }
    return 0;
}

static int write_decimal_file(const char *path, const uint8_t *buf, size_t len)
{
    FILE *fp = fopen(path, "w");
    if (!fp) {
        fprintf(stderr, "[FILE][ERR] cannot open %s: %s\n", path, strerror(errno));
        return -1;
    }

    for (size_t i = 0; i < len; i++) fprintf(fp, "%u ", buf[i]);
    fclose(fp);
    return 0;
}

static int write_binary_file(const char *path, const uint8_t *buf, size_t len)
{
    FILE *fp = fopen(path, "wb");
    if (!fp) {
        fprintf(stderr, "[FILE][ERR] cannot open %s: %s\n", path, strerror(errno));
        return -1;
    }

    size_t wr = fwrite(buf, 1, len, fp);
    fclose(fp);

    if (wr != len) {
        fprintf(stderr, "[FILE][ERR] fwrite mismatch %s: wr=%zu len=%zu\n", path, wr, len);
        return -1;
    }
    return 0;
}

static uint8_t *load_decimal_file(const char *path, size_t *out_len)
{
    FILE *fp = fopen(path, "r");
    if (!fp) {
        fprintf(stderr, "[FILE][ERR] cannot open %s: %s\n", path, strerror(errno));
        return NULL;
    }

    size_t cap = 2048;
    size_t idx = 0;
    uint8_t *buf = (uint8_t *)malloc(cap);
    if (!buf) {
        fclose(fp);
        return NULL;
    }

    int v;
    while (fscanf(fp, "%d", &v) == 1) {
        if (idx >= cap) {
            cap *= 2;
            uint8_t *nbuf = (uint8_t *)realloc(buf, cap);
            if (!nbuf) {
                free(buf);
                fclose(fp);
                return NULL;
            }
            buf = nbuf;
        }
        if (v < 0) v = 0;
        if (v > 255) v = 255;
        buf[idx++] = (uint8_t)v;
    }

    fclose(fp);
    *out_len = idx;
    return buf;
}

static int load_ek_from_pksb(uint32_t file_id, const char *folder, uint8_t *ek_out, size_t ek_need)
{
    char path[256];
    snprintf(path, sizeof(path), "%s/pksb%06u.txt", folder, file_id);

    size_t len = 0;
    uint8_t *buf = load_decimal_file(path, &len);
    if (!buf) return -1;

    if (len < ek_need) {
        fprintf(stderr, "[KEM][ERR] EK file too small: %s len=%zu need=%zu\n", path, len, ek_need);
        free(buf);
        return -1;
    }

    memcpy(ek_out, buf, ek_need);
    free(buf);
    return 0;
}

// =======================================================
// DMA / KEM control
// =======================================================
static int wait_reg_bit_clear(volatile uint32_t *base, uint32_t off, uint32_t mask, double timeout_us)
{
    double t0 = now_usec();
    while (mmio_read(base, off) & mask) {
        if ((now_usec() - t0) > timeout_us) {
            fprintf(stderr, "[WAIT][ERR] timeout waiting clear: off=0x%X val=0x%08X mask=0x%08X\n",
                    off, mmio_read(base, off), mask);
            return -1;
        }
    }
    return 0;
}

static int dma_reset_all(volatile uint32_t *dma)
{
    mmio_write(dma, MM2S_DMACR, DMA_RESET);
    mmio_write(dma, S2MM_DMACR, DMA_RESET);

    if (wait_reg_bit_clear(dma, MM2S_DMACR, DMA_RESET, 100000.0) != 0) return -1;
    if (wait_reg_bit_clear(dma, S2MM_DMACR, DMA_RESET, 100000.0) != 0) return -1;

    // Clear sticky interrupts/errors. AXI DMA status bits are write-to-clear.
    mmio_write(dma, MM2S_DMASR, 0xFFFFFFFFu);
    mmio_write(dma, S2MM_DMASR, 0xFFFFFFFFu);

    mmio_write(dma, MM2S_DMACR, DMA_RS);
    mmio_write(dma, S2MM_DMACR, DMA_RS);
    return 0;
}

static int dma_wait_both_done_timed(volatile uint32_t *dma, const char *op_name, double timeout_us, double total_t0)
{
    double wait_t0 = now_usec();
    int mm2s_done = 0;
    int s2mm_done = 0;
    uint32_t mm2s_sr = 0;
    uint32_t s2mm_sr = 0;

    while (!(mm2s_done && s2mm_done)) {
        mm2s_sr = mmio_read(dma, MM2S_DMASR);
        s2mm_sr = mmio_read(dma, S2MM_DMASR);

        if (mm2s_sr & DMA_ERROR_MASK) {
            fprintf(stderr, "[DMA][%s][MM2S][ERR] status=0x%08X\n", op_name, mm2s_sr);
            return -1;
        }
        if (s2mm_sr & DMA_ERROR_MASK) {
            fprintf(stderr, "[DMA][%s][S2MM][ERR] status=0x%08X\n", op_name, s2mm_sr);
            return -1;
        }

        if (!mm2s_done && (mm2s_sr & DMASR_IOC_IRQ)) {
            mm2s_done = 1;
            printf("[%s][DONE] DMA INPUT  complete: MM2S_DMASR=0x%08X wait=%10.0f us total=%10.0f us\n",
                   op_name, mm2s_sr, now_usec() - wait_t0, now_usec() - total_t0);
        }

        if (!s2mm_done && (s2mm_sr & DMASR_IOC_IRQ)) {
            s2mm_done = 1;
            printf("[%s][DONE] DMA OUTPUT complete: S2MM_DMASR=0x%08X wait=%10.0f us total=%10.0f us\n",
                   op_name, s2mm_sr, now_usec() - wait_t0, now_usec() - total_t0);
        }

        if ((now_usec() - wait_t0) > timeout_us) {
            fprintf(stderr,
                    "[DMA][%s][ERR] timeout MM2S_DMASR=0x%08X S2MM_DMASR=0x%08X wait=%.0f us\n",
                    op_name, mm2s_sr, s2mm_sr, now_usec() - wait_t0);
            return -1;
        }
    }

    printf("[%s][TIME] DMA wait both done                 step=%10.0f us total=%10.0f us\n",
           op_name, now_usec() - wait_t0, now_usec() - total_t0);
    return 0;
}

static void kem_soft_reset(void)
{
    kem_reset_count++;
    mmio_write(kem_reg, KEM_REG_RESET, 0x1u);
    mmio_write(kem_reg, KEM_REG_RESET, 0x0u);
    printf("[KEM] soft reset count=%u\n", kem_reset_count);
}

static int run_kem_dma(uint32_t ctrl_value, size_t in_bytes, size_t out_bytes, const char *op_name)
{
    const uint64_t src_phys = DMA_BUF_BASE + DMA_KEM_IN_OFFSET;
    const uint64_t dst_phys = DMA_BUF_BASE + DMA_KEM_OUT_OFFSET;
    double t_total = now_usec();
    double t_step;

    printf("[%s] DMA start: in=%zuB out=%zuB ctrl=0x%08X\n",
           op_name, in_bytes, out_bytes, ctrl_value);
    printf("[%s][ADDR] MM2S src=0x%016" PRIX64 " S2MM dst=0x%016" PRIX64 "\n",
           op_name, src_phys, dst_phys);

    t_step = now_usec();
    kem_soft_reset();
    timing_log(op_name, "KEM soft reset", t_step, t_total);

    t_step = now_usec();
    if (dma_reset_all(dma0_reg) != 0) {
        fprintf(stderr, "[%s][ERR] DMA reset failed\n", op_name);
        return -1;
    }
    timing_log(op_name, "DMA reset/enable", t_step, t_total);
    printf("[%s][STAT] after reset: MM2S_DMASR=0x%08X S2MM_DMASR=0x%08X\n",
           op_name, mmio_read(dma0_reg, MM2S_DMASR), mmio_read(dma0_reg, S2MM_DMASR));

    // Arm S2MM first to avoid missing early output data.
    t_step = now_usec();
    mmio_write(dma0_reg, S2MM_DA,     (uint32_t)(dst_phys & 0xFFFFFFFFu));
    mmio_write(dma0_reg, S2MM_DA_MSB, (uint32_t)(dst_phys >> 32));
    mmio_write(dma0_reg, S2MM_LENGTH, (uint32_t)out_bytes);
    timing_log(op_name, "S2MM output channel armed", t_step, t_total);
    printf("[%s][ARM] S2MM_DA=0x%08X_%08X LEN=%zu\n",
           op_name, (uint32_t)(dst_phys >> 32), (uint32_t)(dst_phys & 0xFFFFFFFFu), out_bytes);

    // Then arm MM2S input stream.
    t_step = now_usec();
    mmio_write(dma0_reg, MM2S_SA,     (uint32_t)(src_phys & 0xFFFFFFFFu));
    mmio_write(dma0_reg, MM2S_SA_MSB, (uint32_t)(src_phys >> 32));
    mmio_write(dma0_reg, MM2S_LENGTH, (uint32_t)in_bytes);
    timing_log(op_name, "MM2S input channel armed", t_step, t_total);
    printf("[%s][ARM] MM2S_SA=0x%08X_%08X LEN=%zu\n",
           op_name, (uint32_t)(src_phys >> 32), (uint32_t)(src_phys & 0xFFFFFFFFu), in_bytes);

    // Trigger KEM RTL.
    t_step = now_usec();
    mmio_write(kem_reg, KEM_REG_CTRL, ctrl_value);
    timing_log(op_name, "KEM control write/start", t_step, t_total);
    printf("[%s][CTRL] reg0 write=0x%08X readback=0x%08X\n",
           op_name, ctrl_value, mmio_read(kem_reg, KEM_REG_CTRL));

    t_step = now_usec();
    if (dma_wait_both_done_timed(dma0_reg, op_name, KEM_TIMEOUT_US, t_total) != 0) return -1;
    timing_log(op_name, "DMA HW execution total", t_step, t_total);

    printf("[%s] DMA done: MM2S_DMASR=0x%08X S2MM_DMASR=0x%08X elapsed=%.0f us\n",
           op_name, mmio_read(dma0_reg, MM2S_DMASR), mmio_read(dma0_reg, S2MM_DMASR), now_usec() - t_total);
    return 0;
}

// =======================================================
// KEM operations
// =======================================================
static int kem_keygen_512(uint32_t file_id)
{
    printf("\n========== [1] ML-KEM-512 KEYGEN START ==========\n");
    double t_total = now_usec();
    double t_step;

    volatile uint8_t *dma_in  = dma_buf_virt + DMA_KEM_IN_OFFSET;
    volatile uint8_t *dma_out = dma_buf_virt + DMA_KEM_OUT_OFFSET;

    uint8_t randombytes[KEM512_RANDOM_BYTES];
    uint8_t out[KEM512_KEYGEN_OUT_BYTES];
    uint8_t secret_vector[KEM512_SECRET_VEC_BYTES];
    uint8_t ek[KEM512_EK_BYTES];
    uint8_t extra[KEM512_EXTRA_BYTES];

    t_step = now_usec();
    memset(randombytes, 0, sizeof(randombytes));
    memset(out, 0, sizeof(out));
    memset(secret_vector, 0, sizeof(secret_vector));
    memset(ek, 0, sizeof(ek));
    memset(extra, 0, sizeof(extra));
    timing_log("KEYGEN", "local buffer memset", t_step, t_total);

    t_step = now_usec();
    if (fill_random_bytes(randombytes, sizeof(randombytes)) != 0) return -1;
    timing_log("KEYGEN", "generate randombytes 64B", t_step, t_total);

    t_step = now_usec();
    dev_memset8(dma_in,  0x00, KEM512_RANDOM_BYTES);
    dev_memset8(dma_out, 0x00, KEM512_KEYGEN_OUT_BYTES);
    timing_log("KEYGEN", "DMA buffer clear", t_step, t_total);

    t_step = now_usec();
    dev_memcpy_to8(dma_in, randombytes, KEM512_RANDOM_BYTES);
    timing_log("KEYGEN", "DMA input copy complete", t_step, t_total);
    printf("[KEYGEN][DONE] DMA input buffer prepared: %u bytes total=%10.0f us\n",
           KEM512_RANDOM_BYTES, now_usec() - t_total);

    t_step = now_usec();
    dump_bytes_hex("KEYGEN-DMA-IN-BYTE", dma_in, KEM512_RANDOM_BYTES);
    dump_words64_be("KEYGEN-DMA-IN-U64", dma_in, KEM512_RANDOM_BYTES);
    timing_log("KEYGEN", "DMA input dump", t_step, t_total);

    t_step = now_usec();
    if (run_kem_dma(KEM_CTRL_KEYGEN_512,
                    KEM512_RANDOM_BYTES,
                    KEM512_KEYGEN_OUT_BYTES,
                    "KEYGEN") != 0) {
        return -1;
    }
    timing_log("KEYGEN", "run_kem_dma returned", t_step, t_total);

    t_step = now_usec();
    dump_bytes_hex("KEYGEN-DMA-OUT-BYTE", dma_out, KEM512_KEYGEN_OUT_BYTES);
    dump_words64_be("KEYGEN-DMA-OUT-U64", dma_out, KEM512_KEYGEN_OUT_BYTES);
    timing_log("KEYGEN", "DMA output dump", t_step, t_total);
    printf("[KEYGEN][DONE] DMA output buffer captured: %u bytes total=%10.0f us\n",
           KEM512_KEYGEN_OUT_BYTES, now_usec() - t_total);

    t_step = now_usec();
    dev_memcpy_from8(out, dma_out, KEM512_KEYGEN_OUT_BYTES);
    timing_log("KEYGEN", "DMA output copy to local", t_step, t_total);

    t_step = now_usec();
    memcpy(secret_vector, out, KEM512_SECRET_VEC_BYTES);
    memcpy(ek,            out + KEM512_SECRET_VEC_BYTES, KEM512_EK_BYTES);
    memcpy(extra,         out + KEM512_SECRET_VEC_BYTES + KEM512_EK_BYTES, KEM512_EXTRA_BYTES);
    timing_log("KEYGEN", "split SV/EK/extra", t_step, t_total);

    char path[256];

    t_step = now_usec();
    snprintf(path, sizeof(path), "enc_key/pksb%06u.txt", file_id);
    if (write_decimal_file(path, ek, KEM512_EK_BYTES) != 0) return -1;
    snprintf(path, sizeof(path), "sb/K2_SK_512.txt");
    if (write_decimal_file(path, secret_vector, KEM512_SECRET_VEC_BYTES) != 0) return -1;
    snprintf(path, sizeof(path), "sb/K2_ELSE_sb.txt");
    if (write_decimal_file(path, extra, KEM512_HEK_BYTES) != 0) return -1;

    // Decap key file format expected by current Decap code:
    // secret_vector(768B) + H(ek)(32B) + ek(800B) = 1600B
    uint8_t dk_file[KEM512_DK_FILE_BYTES];
    memcpy(dk_file, secret_vector, KEM512_SECRET_VEC_BYTES);
    memcpy(dk_file + KEM512_SECRET_VEC_BYTES, extra, KEM512_HEK_BYTES);
    memcpy(dk_file + KEM512_SECRET_VEC_BYTES + KEM512_HEK_BYTES, ek, KEM512_EK_BYTES);

    snprintf(path, sizeof(path), "sk/sk%06u.txt", file_id);
    if (write_decimal_file(path, dk_file, sizeof(dk_file)) != 0) return -1;
    snprintf(path, sizeof(path), "randombytes/keygen_rand_%06u.txt", file_id);
    if (write_decimal_file(path, randombytes, sizeof(randombytes)) != 0) return -1;
    timing_log("KEYGEN", "save output files", t_step, t_total);

    printf("[KEYGEN] saved enc_key/pksb%06u.txt, sk/sk%06u.txt\n", file_id, file_id);
    printf("========== [1] ML-KEM-512 KEYGEN END   elapsed=%.0f us ==========\n", now_usec() - t_total);
    return 0;
}

static int kem_encap_512(uint32_t file_id, uint8_t ssk_enc[KEM512_SSK_BYTES])
{
    printf("\n========== [2] ML-KEM-512 ENCAP START ==========\n");
    double t_total = now_usec();
    double t_step;

    volatile uint8_t *dma_in  = dma_buf_virt + DMA_KEM_IN_OFFSET;
    volatile uint8_t *dma_out = dma_buf_virt + DMA_KEM_OUT_OFFSET;

    uint8_t ek[KEM512_EK_BYTES];
    uint8_t msg[KEM512_MSG_BYTES];
    uint8_t out[KEM512_ENCAP_OUT_BYTES];
    uint8_t ct[KEM512_CT_BYTES];

    t_step = now_usec();
    memset(ek, 0, sizeof(ek));
    memset(msg, 0, sizeof(msg));
    memset(out, 0, sizeof(out));
    memset(ct, 0, sizeof(ct));
    memset(ssk_enc, 0, KEM512_SSK_BYTES);
    timing_log("ENCAP", "local buffer memset", t_step, t_total);

    t_step = now_usec();
    if (load_ek_from_pksb(file_id, "enc_key", ek, KEM512_EK_BYTES) != 0) return -1;
    timing_log("ENCAP", "load EK file 800B", t_step, t_total);

    t_step = now_usec();
    if (fill_random_bytes(msg, sizeof(msg)) != 0) return -1;
    timing_log("ENCAP", "generate msg random 32B", t_step, t_total);

    t_step = now_usec();
    dev_memset8(dma_in,  0x00, KEM512_ENCAP_IN_BYTES);
    dev_memset8(dma_out, 0x00, KEM512_ENCAP_OUT_BYTES);
    timing_log("ENCAP", "DMA buffer clear", t_step, t_total);

    // Input stream: ek(800B) + msg(32B)
    t_step = now_usec();
    dev_memcpy_to8(dma_in, ek, KEM512_EK_BYTES);
    dev_memcpy_to8(dma_in + KEM512_EK_BYTES, msg, KEM512_MSG_BYTES);
    timing_log("ENCAP", "DMA input build EK+msg", t_step, t_total);
    printf("[ENCAP][DONE] DMA input buffer prepared: %u bytes total=%10.0f us\n",
           KEM512_ENCAP_IN_BYTES, now_usec() - t_total);

    t_step = now_usec();
    dump_bytes_hex("ENCAP-DMA-IN-BYTE", dma_in, KEM512_ENCAP_IN_BYTES);
    dump_words64_be("ENCAP-DMA-IN-U64", dma_in, KEM512_ENCAP_IN_BYTES);
    timing_log("ENCAP", "DMA input dump", t_step, t_total);

    t_step = now_usec();
    if (run_kem_dma(KEM_CTRL_ENCAP_512,
                    KEM512_ENCAP_IN_BYTES,
                    KEM512_ENCAP_OUT_BYTES,
                    "ENCAP") != 0) {
        return -1;
    }
    timing_log("ENCAP", "run_kem_dma returned", t_step, t_total);

    t_step = now_usec();
    dump_bytes_hex("ENCAP-DMA-OUT-BYTE", dma_out, KEM512_ENCAP_OUT_BYTES);
    dump_words64_be("ENCAP-DMA-OUT-U64", dma_out, KEM512_ENCAP_OUT_BYTES);
    timing_log("ENCAP", "DMA output dump", t_step, t_total);
    printf("[ENCAP][DONE] DMA output buffer captured: %u bytes total=%10.0f us\n",
           KEM512_ENCAP_OUT_BYTES, now_usec() - t_total);

    t_step = now_usec();
    dev_memcpy_from8(out, dma_out, KEM512_ENCAP_OUT_BYTES);
    memcpy(ssk_enc, out, KEM512_SSK_BYTES);
    memcpy(ct, out + KEM512_SSK_BYTES, KEM512_CT_BYTES);
    timing_log("ENCAP", "copy/split SSK+CT", t_step, t_total);

    char path[256];

    t_step = now_usec();
    snprintf(path, sizeof(path), "ssk/ssk%06u.bin", file_id);
    if (write_binary_file(path, ssk_enc, KEM512_SSK_BYTES) != 0) return -1;
    snprintf(path, sizeof(path), "cipher/ct%06u.txt", file_id);
    if (write_decimal_file(path, ct, KEM512_CT_BYTES) != 0) return -1;
    snprintf(path, sizeof(path), "randombytes/encap_msg_%06u.txt", file_id);
    if (write_decimal_file(path, msg, sizeof(msg)) != 0) return -1;
    timing_log("ENCAP", "save output files", t_step, t_total);

    print_hex_line("ENCAP-SSK", ssk_enc, KEM512_SSK_BYTES);
    printf("[ENCAP] saved ssk/ssk%06u.bin, cipher/ct%06u.txt\n", file_id, file_id);
    printf("========== [2] ML-KEM-512 ENCAP END   elapsed=%.0f us ==========\n", now_usec() - t_total);
    return 0;
}

static int kem_decap_512(uint32_t file_id, uint8_t ssk_dec[KEM512_SSK_BYTES])
{
    printf("\n========== [3] ML-KEM-512 DECAP START ==========\n");
    double t_total = now_usec();
    double t_step;

    char sk_path[256];
    char ct_path[256];
    snprintf(sk_path, sizeof(sk_path), "sk/sk%06u.txt", file_id);
    snprintf(ct_path, sizeof(ct_path), "cipher/ct%06u.txt", file_id);

    size_t sk_len = 0;
    size_t ct_len = 0;

    t_step = now_usec();
    uint8_t *sk_bytes = load_decimal_file(sk_path, &sk_len);
    timing_log("DECAP", "load SK file", t_step, t_total);

    t_step = now_usec();
    uint8_t *ct_bytes = load_decimal_file(ct_path, &ct_len);
    timing_log("DECAP", "load CT file", t_step, t_total);

    if (!sk_bytes || !ct_bytes) {
        free(sk_bytes);
        free(ct_bytes);
        return -1;
    }

    t_step = now_usec();
    if (sk_len < KEM512_DK_FILE_BYTES) {
        fprintf(stderr, "[DECAP][ERR] SK file too small: len=%zu need=%u\n", sk_len, KEM512_DK_FILE_BYTES);
        free(sk_bytes);
        free(ct_bytes);
        return -1;
    }

    if (ct_len < KEM512_CT_BYTES) {
        fprintf(stderr, "[DECAP][ERR] CT file too small: len=%zu need=%u\n", ct_len, KEM512_CT_BYTES);
        free(sk_bytes);
        free(ct_bytes);
        return -1;
    }
    timing_log("DECAP", "validate SK/CT length", t_step, t_total);

    volatile uint8_t *dma_in  = dma_buf_virt + DMA_KEM_IN_OFFSET;
    volatile uint8_t *dma_out = dma_buf_virt + DMA_KEM_OUT_OFFSET;

    t_step = now_usec();
    dev_memset8(dma_in,  0x00, KEM512_DECAP_IN_BYTES);
    dev_memset8(dma_out, 0x00, KEM512_DECAP_OUT_BYTES);
    timing_log("DECAP", "DMA buffer clear", t_step, t_total);

    uint8_t *secret_vector = sk_bytes;
    uint8_t *hek           = sk_bytes + KEM512_SECRET_VEC_BYTES;
    uint8_t *ek            = sk_bytes + KEM512_SECRET_VEC_BYTES + KEM512_HEK_BYTES;

    size_t off = 0;

    t_step = now_usec();
    // 1) 128 words: 6B secret_vector + 2B ct
    {
        size_t sv_idx = 0;
        size_t ct_idx = 0;
        for (size_t w = 0; w < 128; w++) {
            dma_in[off + 0] = secret_vector[sv_idx + 0];
            dma_in[off + 1] = secret_vector[sv_idx + 1];
            dma_in[off + 2] = secret_vector[sv_idx + 2];
            dma_in[off + 3] = secret_vector[sv_idx + 3];
            dma_in[off + 4] = secret_vector[sv_idx + 4];
            dma_in[off + 5] = secret_vector[sv_idx + 5];
            dma_in[off + 6] = ct_bytes[ct_idx + 0];
            dma_in[off + 7] = ct_bytes[ct_idx + 1];
            sv_idx += 6;
            ct_idx += 2;
            off += 8;
        }
    }
    timing_log("DECAP", "build input part1 SV6+CT2", t_step, t_total);

    t_step = now_usec();
    // 2) remaining ct: 512B = 64 words
    {
        size_t ct_idx = 256;
        for (size_t w = 0; w < 64; w++) {
            dev_memcpy_to8(dma_in + off, ct_bytes + ct_idx, 8);
            ct_idx += 8;
            off += 8;
        }
    }
    timing_log("DECAP", "build input part2 CT rest", t_step, t_total);

    t_step = now_usec();
    // 3) H(ek): 32B = 4 words
    for (size_t w = 0; w < 4; w++) {
        dev_memcpy_to8(dma_in + off, hek + (w * 8), 8);
        off += 8;
    }
    timing_log("DECAP", "build input part3 H(EK)", t_step, t_total);

    t_step = now_usec();
    // 4) ek: 800B = 100 words
    for (size_t w = 0; w < 100; w++) {
        dev_memcpy_to8(dma_in + off, ek + (w * 8), 8);
        off += 8;
    }
    timing_log("DECAP", "build input part4 EK", t_step, t_total);

    t_step = now_usec();
    if (off != KEM512_DECAP_IN_BYTES) {
        fprintf(stderr, "[DECAP][ERR] input build length mismatch: off=%zu need=%u\n", off, KEM512_DECAP_IN_BYTES);
        free(sk_bytes);
        free(ct_bytes);
        return -1;
    }
    timing_log("DECAP", "validate input build length", t_step, t_total);
    printf("[DECAP][DONE] DMA input buffer prepared: %u bytes total=%10.0f us\n",
           KEM512_DECAP_IN_BYTES, now_usec() - t_total);

    t_step = now_usec();
    dump_bytes_hex("DECAP-DMA-IN-BYTE", dma_in, KEM512_DECAP_IN_BYTES);
    dump_words64_be("DECAP-DMA-IN-U64", dma_in, KEM512_DECAP_IN_BYTES);
    timing_log("DECAP", "DMA input dump", t_step, t_total);

    t_step = now_usec();
    if (run_kem_dma(KEM_CTRL_DECAP_512,
                    KEM512_DECAP_IN_BYTES,
                    KEM512_DECAP_OUT_BYTES,
                    "DECAP") != 0) {
        free(sk_bytes);
        free(ct_bytes);
        return -1;
    }
    timing_log("DECAP", "run_kem_dma returned", t_step, t_total);

    t_step = now_usec();
    dump_bytes_hex("DECAP-DMA-OUT-BYTE", dma_out, KEM512_DECAP_OUT_BYTES);
    dump_words64_be("DECAP-DMA-OUT-U64", dma_out, KEM512_DECAP_OUT_BYTES);
    timing_log("DECAP", "DMA output dump", t_step, t_total);
    printf("[DECAP][DONE] DMA output buffer captured: %u bytes total=%10.0f us\n",
           KEM512_DECAP_OUT_BYTES, now_usec() - t_total);

    t_step = now_usec();
    dev_memcpy_from8(ssk_dec, dma_out, KEM512_SSK_BYTES);
    timing_log("DECAP", "copy SSK_DEC", t_step, t_total);

    char path[256];
    t_step = now_usec();
    snprintf(path, sizeof(path), "ssk_dec/ssk_dec%06u.bin", file_id);
    if (write_binary_file(path, ssk_dec, KEM512_SSK_BYTES) != 0) {
        free(sk_bytes);
        free(ct_bytes);
        return -1;
    }
    timing_log("DECAP", "save SSK_DEC file", t_step, t_total);

    print_hex_line("DECAP-SSK", ssk_dec, KEM512_SSK_BYTES);
    printf("[DECAP] saved ssk_dec/ssk_dec%06u.bin\n", file_id);
    printf("========== [3] ML-KEM-512 DECAP END   elapsed=%.0f us ==========\n", now_usec() - t_total);

    free(sk_bytes);
    free(ct_bytes);
    return 0;
}

// =======================================================
// Main
// =======================================================
int main(int argc, char **argv)
{
    double t_main = now_usec();
    double t_step;

    uint32_t file_id = 1;
    if (argc >= 2) {
        unsigned long v = strtoul(argv[1], NULL, 10);
        if (v == 0 || v > 999999UL) {
            fprintf(stderr, "Usage: %s [file_id: 1..999999]\n", argv[0]);
            return EXIT_FAILURE;
        }
        file_id = (uint32_t)v;
    }

    printf("\n=====================================\n");
    printf(" Standalone ML-KEM-512 HW Test\n");
    printf(" KEYGEN -> ENCAP -> DECAP -> COMPARE\n");
    printf(" file_id = %u\n", file_id);
    printf("=====================================\n\n");

    t_step = now_usec();
    if (prepare_dirs() != 0) {
        fprintf(stderr, "[MAIN][ERR] directory preparation failed\n");
        return EXIT_FAILURE;
    }
    timing_log("MAIN", "prepare output directories", t_step, t_main);

    t_step = now_usec();
    mmio_init();
    timing_log("MAIN", "MMIO/DMA buffer mapping", t_step, t_main);

    uint8_t ssk_enc[KEM512_SSK_BYTES];
    uint8_t ssk_dec[KEM512_SSK_BYTES];
    memset(ssk_enc, 0, sizeof(ssk_enc));
    memset(ssk_dec, 0, sizeof(ssk_dec));

    int ret = EXIT_FAILURE;

    t_step = now_usec();
    if (kem_keygen_512(file_id) != 0) {
        fprintf(stderr, "[MAIN][FAIL] KEYGEN failed\n");
        goto cleanup;
    }
    timing_log("MAIN", "KEYGEN total", t_step, t_main);

    t_step = now_usec();
    if (kem_encap_512(file_id, ssk_enc) != 0) {
        fprintf(stderr, "[MAIN][FAIL] ENCAP failed\n");
        goto cleanup;
    }
    timing_log("MAIN", "ENCAP total", t_step, t_main);

    t_step = now_usec();
    if (kem_decap_512(file_id, ssk_dec) != 0) {
        fprintf(stderr, "[MAIN][FAIL] DECAP failed\n");
        goto cleanup;
    }
    timing_log("MAIN", "DECAP total", t_step, t_main);

    printf("\n========== [4] SSK COMPARE ==========\n");
    t_step = now_usec();
    print_hex_line("ENCAP-SSK", ssk_enc, KEM512_SSK_BYTES);
    print_hex_line("DECAP-SSK", ssk_dec, KEM512_SSK_BYTES);

    if (memcmp(ssk_enc, ssk_dec, KEM512_SSK_BYTES) == 0) {
        printf("\n[TEST][PASS] ML-KEM-512 KEYGEN -> ENCAP -> DECAP success\n");
        ret = EXIT_SUCCESS;
    } else {
        printf("\n[TEST][FAIL] SSK mismatch\n");
        ret = EXIT_FAILURE;
    }
    timing_log("MAIN", "SSK compare", t_step, t_main);

cleanup:
    t_step = now_usec();
    mmio_deinit();
    timing_log("MAIN", "MMIO deinit", t_step, t_main);
    printf("[MAIN][TIME] TOTAL elapsed=%.0f us\n", now_usec() - t_main);
    return ret;
}
