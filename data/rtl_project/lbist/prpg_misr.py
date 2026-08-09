"""
prpg_misr.py
------------
PRPG (Pseudo-Random Pattern Generator)와 MISR (Multiple-Input Signature
Register)를 구현한다. 논문 스펙에 맞춰 두 레지스터 모두 16-bit로 둔다.

PRPG:
    16-bit Galois LFSR을 core로 사용한다. 다만 214개(s5378 입력 수)의
    스캔 셀에 매 사이클 서로 다른 패턴을 공급하려면, 16-bit 상태만으로는
    폭이 부족하므로 실제 LBIST 하드웨어처럼 "phase shifter"(위상 편이
    네트워크)를 두어 16-bit core의 여러 tap을 XOR 조합해 넓은 패턴을
    만든다. 이 phase shifter 덕분에 16-bit라는 좁은 상태 공간을 갖고도
    (제한적이지만) 넓은 스캔 벡터를 생성할 수 있다 — 이것이 실제 LBIST가
    PRPG 기반 무작위 패턴만으로는 특정 고장(난검출 고장, Random Pattern
    Resistant fault)을 놓치는 근본 원인이다.

MISR:
    16-bit MISR이 매 사이클 228-bit CUT 출력을 16-bit 시그니처로
    압축한다. 압축은 (a) 출력 비트들을 16개 채널로 XOR-fold하고,
    (b) 결과를 다항식 피드백 시프트 레지스터에 XOR-in 하는 전형적인
    parallel MISR 구조를 따른다.
"""


class GaloisLFSR:
    """16-bit Galois LFSR. Fibonacci/Galois 다항식은 CRC-16-ish
    x^16 + x^14 + x^13 + x^11 + 1 (0xB400 taps) 를 사용한다."""

    def __init__(self, seed: int = 0xACE1, width: int = 16, taps: int = 0xB400):
        assert seed != 0, "LFSR seed must be non-zero"
        self.width = width
        self.mask = (1 << width) - 1
        self.taps = taps
        self.state = seed & self.mask

    def step(self) -> int:
        lsb = self.state & 1
        self.state >>= 1
        if lsb:
            self.state ^= self.taps
        self.state &= self.mask
        return self.state

    def peek(self) -> int:
        return self.state


class PhaseShifterPRPG:
    """
    16-bit Galois LFSR + XOR phase-shifter로 num_bits 폭의 패턴을 생성.

    각 출력 채널 j (0..num_bits-1) 는 LFSR의 서로 다른 3개 탭
    (offset 조합)을 XOR해서 만든다. 오프셋은 채널 번호에 따라 결정론적,
    상호소수 성질을 이용해 채널 간 상관을 낮춘다.
    """

    def __init__(self, num_bits: int, seed: int = 0xACE1):
        self.lfsr = GaloisLFSR(seed=seed, width=16)
        self.num_bits = num_bits
        # 채널별 3-tap 오프셋 (16보다 작은 서로 다른 소수 간격 사용)
        self._offsets = [
            ((3 * j) % 16, (7 * j + 1) % 16, (11 * j + 5) % 16)
            for j in range(num_bits)
        ]

    def next_pattern(self) -> list:
        """LFSR을 한 스텝 전진시키고, 그 상태로부터 num_bits 폭 패턴 생성."""
        state = self.lfsr.step()
        bits = [(state >> i) & 1 for i in range(16)]
        pattern = []
        for (a, b, c) in self._offsets:
            pattern.append(bits[a] ^ bits[b] ^ bits[c])
        return pattern


class MISR:
    """16-bit Multiple-Input Signature Register."""

    def __init__(self, num_inputs: int, width: int = 16, taps: int = 0xB400):
        self.width = width
        self.mask = (1 << width) - 1
        self.taps = taps
        self.signature = 0
        self.num_inputs = num_inputs
        # 각 CUT 출력 비트가 XOR로 합쳐질 MISR 채널(k = idx % width)
        self._channel_of = [i % width for i in range(num_inputs)]

    def compress(self, output_bits: list) -> int:
        """MISR을 한 사이클 갱신: LFSR 시프트 후 입력을 XOR-in."""
        # 1) 다항식 피드백 시프트 (LFSR과 동일한 방식으로 내부 상태 전진)
        lsb = self.signature & 1
        shifted = self.signature >> 1
        if lsb:
            shifted ^= self.taps
        shifted &= self.mask

        # 2) 228-bit 출력 -> 16채널로 XOR-fold
        fold = 0
        for i, bit in enumerate(output_bits):
            if bit:
                fold ^= (1 << self._channel_of[i])

        self.signature = (shifted ^ fold) & self.mask
        return self.signature


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")
