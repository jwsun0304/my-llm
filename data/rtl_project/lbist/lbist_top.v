// lbist_top.v
// -----------
// PRPG + MISR + AdaptiveTController 통합 top module.
//
// 주의(스코프 한정): 이 저장소의 결함 시뮬레이터(src/fault_sim.py)는 Python
// 전용이라 합성 가능한 CUT(회로) 모델이 없다. 따라서 이 top은 MISR의
// response 입력을 PRPG가 만든 pattern 자체로 루프백한다 (실제 배포에서는
// response를 CUT의 스캔아웃/컴팩터 출력에 연결하면 된다). 이 단순화로도
// PRPG -> MISR -> HD -> AdaptiveTController 로 이어지는 제어/데이터패스
// 통합 자체는 동일하게 검증된다.
//
// 매 enable 사이클: prpg가 한 스텝 전진 -> misr이 그 pattern을 response로
// 받아 압축 -> (새 signature, 이전 signature)의 Hamming Distance 계산 ->
// controller.update(hd) 로 T-period 갱신. experiment.py의 한 패턴 루프와
// 동일한 순서로 같은 클록 엣지 안에서 전부 갱신된다.

module lbist_top #(
    parameter WIDTH             = 64,        // PRPG pattern 폭 = MISR response 폭 (loop-back)
    parameter [15:0] SEED       = 16'hACE1,
    // adaptive_controller로 그대로 전달되는 파라미터 (기본값 = Optuna 최적값)
    parameter T_INIT            = 33,
    parameter T_MAX              = 1024,
    parameter DELTA_T            = 193,
    parameter K                  = 3,
    parameter W                  = 34,
    parameter CALIB_PATTERNS     = 72,
    parameter ALPHA_FRAC_BITS    = 24,
    parameter ALPHA_FIXED        = 14111141
)(
    input  wire                              clk,
    input  wire                              rst_n,
    input  wire                              enable,
    output reg  [WIDTH-1:0]                  pattern,   // 등록본 - 관측용 (아래 주석 참고)
    output wire [15:0]                       signature,
    output wire [$clog2(T_MAX + 1) - 1:0]    current_T,
    output wire                              stalled
);

    wire [15:0] next_signature;
    wire [WIDTH-1:0] next_pattern;

    prpg #(
        .NUM_BITS (WIDTH),
        .SEED     (SEED)
    ) u_prpg (
        .clk          (clk),
        .rst_n        (rst_n),
        .enable       (enable),
        .pattern      (),
        .next_pattern (next_pattern),
        .lfsr_state   ()
    );

    // misr(내부)은 same-edge 시야를 위해 next_pattern(조합, 계속 값이 바뀜)을
    // 직접 쓴다. 반면 top의 pattern 출력은 "패턴 P가 실제로 반영된 이후"에도
    // 안정적으로 유지돼야(=레지스터여야) 외부에서 관측/비교하기 쉽다 - live wire인
    // next_pattern을 그대로 노출하면 이 엣지가 지나가자마자 "다음 패턴"의
    // 미리보기 값으로 계속 바뀌어버려 post-edge 샘플링과 어긋난다.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            pattern <= {WIDTH{1'b0}};
        else if (enable)
            pattern <= next_pattern;
    end

    misr #(
        .NUM_INPUTS (WIDTH)
    ) u_misr (
        .clk            (clk),
        .rst_n          (rst_n),
        .enable         (enable),
        .response       (next_pattern),    // loop-back: CUT 없음 (위 주석 참고)
        .signature      (signature),
        .next_signature (next_signature)
    );

    function [4:0] popcount16;
        input [15:0] v;
        integer b;
        begin
            popcount16 = 5'd0;
            for (b = 0; b < 16; b = b + 1)
                popcount16 = popcount16 + v[b];
        end
    endfunction

    // prev_sig가 아직 없는 "첫 패턴" 사이클엔 python처럼 hd=0 강제
    reg primed;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            primed <= 1'b0;
        else if (enable)
            primed <= 1'b1;
    end

    wire [4:0] hd_raw = popcount16(next_signature ^ signature);
    wire [4:0] hd     = primed ? hd_raw : 5'd0;

    adaptive_controller #(
        .T_INIT         (T_INIT),
        .T_MAX          (T_MAX),
        .DELTA_T        (DELTA_T),
        .K              (K),
        .W              (W),
        .CALIB_PATTERNS (CALIB_PATTERNS),
        .MISR_WIDTH     (16),
        .ALPHA_FRAC_BITS(ALPHA_FRAC_BITS),
        .ALPHA_FIXED    (ALPHA_FIXED)
    ) u_ctrl (
        .clk        (clk),
        .rst_n      (rst_n),
        .update     (enable),
        .hd         (hd),
        .current_T  (current_T),
        .stalled    (stalled)
    );

endmodule
