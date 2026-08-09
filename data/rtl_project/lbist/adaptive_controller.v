// adaptive_controller.v
// ----------------------
// src/adaptive_controller.py 의 AdaptiveTController.update() 를 그대로
// FSM/데이터패스로 옮긴 것. 기본 파라미터는 Optuna(TPE)로 찾은 최적값:
//     T_init=33, T_max=1024, delta_T=193, K=3, W=34,
//     alpha=0.8410895754890528, calibration_patterns=int(33*2.183035341991451)=72
//
// Python 알고리즘 요약 (매 update(hd) 호출마다):
//   n_seen += 1
//   if baseline is None:                       # calibration 구간
//       calib_hds.append(hd)
//       if n_seen >= calibration_patterns:
//           baseline = mean(calib_hds)  (<=0 이면 misr_width/2 로 대체)
//       hd_window.append(hd)
//       return False                            # stall 판정 없음
//   hd_window.append(hd)
//   avg_hd = mean(hd_window)
//   threshold = alpha * baseline
//   if avg_hd < threshold:
//       consecutive_low += 1
//       if consecutive_low >= K:
//           T = min(T + delta_T, T_max)
//           consecutive_low = 0
//           return (T actually changed)
//   else:
//       consecutive_low = 0
//   return False
//
// 부동소수점(mean, alpha*baseline)을 하드웨어에서 그대로 쓰지 않기 위해,
// baseline/avg_hd를 "평균값"으로 미리 나누지 않고 (합, 개수) 쌍으로 유지한
// 채 아래처럼 교차곱으로 비교한다 (양쪽 다 양수이므로 부등식 방향 보존):
//
//   avg_hd < alpha * baseline
//   window_sum/window_count < alpha * baseline_sum/CALIB_PATTERNS
//   window_sum * CALIB_PATTERNS * 2^F  <  ALPHA_FIXED * baseline_sum * window_count
//     (ALPHA_FIXED = round(alpha * 2^F), F=ALPHA_FRAC_BITS)
//
// ALPHA_FIXED 기본값 14111141 / 2^24 = 0.8410895466... (alpha와의 오차 ~3e-8,
// HD가 정수라는 점을 감안하면 실질적으로 원본 float 비교와 동일한 결과를 준다).
// baseline<=0 폴백(misr_width/2.0)도 (misr_width*CALIB_PATTERNS)/2 형태의
// 정수 합으로 정확히 표현 가능해 정밀도 손실 없이 그대로 구현했다.

module adaptive_controller #(
    parameter T_INIT           = 33,
    parameter T_MAX             = 1024,
    parameter DELTA_T           = 193,
    parameter K                 = 3,
    parameter W                 = 34,
    parameter CALIB_PATTERNS    = 72,
    parameter MISR_WIDTH        = 16,
    parameter ALPHA_FRAC_BITS   = 24,
    parameter ALPHA_FIXED       = 14111141,   // round(0.8410895754890528 * 2^24)

    parameter HD_WIDTH   = $clog2(MISR_WIDTH + 1),        // hd: 0..MISR_WIDTH
    parameter T_WIDTH     = $clog2(T_MAX + 1),              // current_T: 0..T_MAX
    parameter WCNT_WIDTH  = $clog2(W + 1),                  // window_count: 0..W
    parameter WSUM_WIDTH  = $clog2(W * MISR_WIDTH + 1),     // window_sum
    parameter NSEEN_WIDTH = $clog2(CALIB_PATTERNS + 1),     // n_seen: 0..CALIB_PATTERNS
    parameter CSUM_WIDTH  = $clog2(CALIB_PATTERNS * MISR_WIDTH + 1), // calib_sum
    parameter KCNT_WIDTH  = $clog2(K + 1)                   // consecutive_low: 0..K
)(
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   update,       // 1 pulse = 파이썬 update(hd) 호출 1회
    input  wire [HD_WIDTH-1:0]    hd,
    output reg  [T_WIDTH-1:0]     current_T,
    output reg                    stalled        // T가 실제로 바뀐 사이클에 1펄스
);

    // ---------------- calibration 상태 ----------------
    reg                    calib_done;
    reg  [NSEEN_WIDTH-1:0] n_seen;
    reg  [CSUM_WIDTH-1:0]  calib_sum;
    reg  [CSUM_WIDTH-1:0]  baseline_sum;   // = sum(calib_hds), 고정 후 불변

    // ---------------- sliding window (circular buffer + running sum) ----------------
    reg  [HD_WIDTH-1:0]   window_buf [0:W-1];
    reg  [$clog2(W)-1:0]  wr_ptr;
    reg  [WCNT_WIDTH-1:0] window_count;
    reg  [WSUM_WIDTH-1:0] window_sum;

    wire                  window_full = (window_count == W[WCNT_WIDTH-1:0]);
    wire [HD_WIDTH-1:0]   oldest      = window_buf[wr_ptr];

    wire [WSUM_WIDTH-1:0]  window_sum_next   = window_sum - (window_full ? oldest : {HD_WIDTH{1'b0}}) + hd;
    wire [WCNT_WIDTH-1:0]  window_count_next = window_full ? W[WCNT_WIDTH-1:0] : (window_count + 1'b1);

    // ---------------- K-consecutive-low counter ----------------
    reg  [KCNT_WIDTH-1:0] consecutive_low;

    // ---------------- calibration 종료 시점 계산 ----------------
    wire [NSEEN_WIDTH:0]  n_seen_next    = n_seen + 1'b1;   // 1비트 여유 (오버플로 방지)
    wire                  calib_finishes = !calib_done && (n_seen_next >= CALIB_PATTERNS);
    wire [CSUM_WIDTH-1:0] calib_sum_next = calib_sum + hd;

    localparam [CSUM_WIDTH-1:0] BASELINE_FALLBACK =
        (MISR_WIDTH * CALIB_PATTERNS) / 2;   // misr_width/2.0 폴백을 합(sum) 형태로 표현

    wire [CSUM_WIDTH-1:0] baseline_sum_candidate =
        (calib_sum_next == 0) ? BASELINE_FALLBACK : calib_sum_next;

    // ---------------- 정체(threshold) 비교: 교차곱, 64-bit로 오버플로 방지 ----------------
    wire [63:0] lhs = ($unsigned(window_sum_next) * $unsigned(CALIB_PATTERNS))
                       * (64'd1 << ALPHA_FRAC_BITS);
    wire [63:0] rhs = ($unsigned(ALPHA_FIXED) * $unsigned(baseline_sum))
                       * $unsigned(window_count_next);
    wire        below_threshold = calib_done && (lhs < rhs);

    wire [T_WIDTH-1:0] t_plus_delta = current_T + DELTA_T[T_WIDTH-1:0];
    wire [T_WIDTH-1:0] t_next       = (t_plus_delta > T_MAX[T_WIDTH-1:0]) ? T_MAX[T_WIDTH-1:0] : t_plus_delta;
    wire               will_trigger = below_threshold && (consecutive_low + 1'b1 >= K[KCNT_WIDTH:0]);
    wire               t_changes    = will_trigger && (t_next != current_T);

    integer i;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            calib_done      <= 1'b0;
            n_seen          <= {NSEEN_WIDTH{1'b0}};
            calib_sum       <= {CSUM_WIDTH{1'b0}};
            baseline_sum    <= {CSUM_WIDTH{1'b0}};
            wr_ptr          <= {$clog2(W){1'b0}};
            window_count    <= {WCNT_WIDTH{1'b0}};
            window_sum      <= {WSUM_WIDTH{1'b0}};
            consecutive_low <= {KCNT_WIDTH{1'b0}};
            current_T       <= T_INIT[T_WIDTH-1:0];
            stalled         <= 1'b0;
            for (i = 0; i < W; i = i + 1)
                window_buf[i] <= {HD_WIDTH{1'b0}};
        end else if (update) begin
            // sliding window는 calibration/steady-state 공통으로 매 사이클 갱신
            window_buf[wr_ptr] <= hd;
            wr_ptr             <= (wr_ptr == W[$clog2(W)-1:0] - 1'b1) ? {$clog2(W){1'b0}} : wr_ptr + 1'b1;
            window_sum         <= window_sum_next;
            window_count       <= window_count_next;
            n_seen             <= n_seen_next[NSEEN_WIDTH-1:0];

            if (!calib_done) begin
                // ---- calibration 구간: baseline 수집만, stall 판정 없음 ----
                calib_sum  <= calib_sum_next;
                if (calib_finishes) begin
                    calib_done   <= 1'b1;
                    baseline_sum <= baseline_sum_candidate;
                end
                stalled <= 1'b0;
            end else begin
                // ---- steady-state: threshold 비교 & K-카운트 & T 갱신 ----
                if (below_threshold) begin
                    if (will_trigger) begin
                        consecutive_low <= {KCNT_WIDTH{1'b0}};
                        if (t_changes) begin
                            current_T <= t_next;
                            stalled   <= 1'b1;
                        end else begin
                            stalled <= 1'b0;
                        end
                    end else begin
                        consecutive_low <= consecutive_low + 1'b1;
                        stalled <= 1'b0;
                    end
                end else begin
                    consecutive_low <= {KCNT_WIDTH{1'b0}};
                    stalled <= 1'b0;
                end
            end
        end else begin
            stalled <= 1'b0;   // update가 없는 사이클엔 pulse 유지하지 않음
        end
    end

endmodule
