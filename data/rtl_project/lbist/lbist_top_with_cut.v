// lbist_top_with_cut.v
// gen_top_with_cut.py로 자동 생성. s1494_cut(=s1494.bench, inputs=14, outputs=25)를 실제 CUT으로 MISR에 물린 버전.
// lbist_top.v(루프백, CUT 없음)는 그대로 보존하고 이 파일만 추가된 것.
//
// 매 enable 사이클: prpg가 pattern[NUM_INPUTS-1:0] 생성 -> CUT의 각 입력핀에
// (bench 파일에 등장한 순서 그대로) 연결 -> CUT의 각 출력핀을 (역시 등장 순서
// 그대로) response[NUM_OUTPUTS-1:0]로 모아 MISR에 입력 -> HD 계산 ->
// adaptive_controller.update(). experiment.py의 한 패턴 루프와 동일한 순서.

module lbist_top_with_cut #(
    parameter [15:0] SEED       = 16'hACE1,
    parameter T_INIT            = 33,
    parameter T_MAX              = 1024,
    parameter DELTA_T            = 193,
    parameter K                  = 3,
    parameter W                  = 34,
    parameter CALIB_PATTERNS     = 72,
    parameter ALPHA_FRAC_BITS    = 24,
    parameter ALPHA_FIXED        = 14111141
)(
    input  wire                            clk,
    input  wire                            rst_n,
    input  wire                            enable,
    output reg  [13:0]                     pattern,   // 등록본(관측용)
    output reg  [24:0]                     response,  // 등록본(관측용)
    output wire [15:0]                     signature,
    output wire [$clog2(T_MAX + 1) - 1:0]  current_T,
    output wire                            stalled
);

    // CUT(게이트레벨 netlist)의 개별 핀 wire - 이름은 bench 라인 번호 그대로
    wire n1, n2, n3, n4, n5, n6, n7, n8;
    wire n9, n10, n11, n12, n13, n14, n513, n568;
    wire n569, n596, n597, n598, n599, n600, n601, n619;
    wire n620, n621, n640, n641, n642, n643, n644, n645;
    wire n646, n647, n655, n656, n657, n658, n661;

    wire [15:0] next_signature;
    wire [13:0] next_pattern;
    wire [24:0] response_live;   // CUT 출력을 모은 조합 버스 (misr이 same-edge로 소비)

    prpg #(.NUM_BITS(14), .SEED(SEED)) u_prpg (
        .clk          (clk),
        .rst_n        (rst_n),
        .enable       (enable),
        .pattern      (),
        .next_pattern (next_pattern),
        .lfsr_state   ()
    );

    // CUT/MISR은 same-edge 시야를 위해 next_pattern/response_live(조합, 계속
    // 바뀜)을 직접 쓴다. 반면 top의 pattern/response 출력은 이 값이 '패턴 P에
    // 대한 결과'로 안정적으로 유지돼야(=레지스터여야) 외부에서 post-edge에
    // 샘플링해도 어긋나지 않는다 - live wire를 그대로 노출하면 이 엣지가
    // 지나가자마자 '다음 패턴'의 미리보기 값으로 계속 바뀌어버린다.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pattern  <= {14{1'b0}};
            response <= {25{1'b0}};
        end else if (enable) begin
            pattern  <= next_pattern;
            response <= response_live;
        end
    end

    assign n1 = next_pattern[0];
    assign n2 = next_pattern[1];
    assign n3 = next_pattern[2];
    assign n4 = next_pattern[3];
    assign n5 = next_pattern[4];
    assign n6 = next_pattern[5];
    assign n7 = next_pattern[6];
    assign n8 = next_pattern[7];
    assign n9 = next_pattern[8];
    assign n10 = next_pattern[9];
    assign n11 = next_pattern[10];
    assign n12 = next_pattern[11];
    assign n13 = next_pattern[12];
    assign n14 = next_pattern[13];

    s1494_cut u_cut (
        .n1(n1),
        .n2(n2),
        .n3(n3),
        .n4(n4),
        .n5(n5),
        .n6(n6),
        .n7(n7),
        .n8(n8),
        .n9(n9),
        .n10(n10),
        .n11(n11),
        .n12(n12),
        .n13(n13),
        .n14(n14),
        .n513(n513),
        .n568(n568),
        .n569(n569),
        .n596(n596),
        .n597(n597),
        .n598(n598),
        .n599(n599),
        .n600(n600),
        .n601(n601),
        .n619(n619),
        .n620(n620),
        .n621(n621),
        .n640(n640),
        .n641(n641),
        .n642(n642),
        .n643(n643),
        .n644(n644),
        .n645(n645),
        .n646(n646),
        .n647(n647),
        .n655(n655),
        .n656(n656),
        .n657(n657),
        .n658(n658),
        .n661(n661)
    );

    assign response_live[0] = n513;
    assign response_live[1] = n568;
    assign response_live[2] = n569;
    assign response_live[3] = n596;
    assign response_live[4] = n597;
    assign response_live[5] = n598;
    assign response_live[6] = n599;
    assign response_live[7] = n600;
    assign response_live[8] = n601;
    assign response_live[9] = n619;
    assign response_live[10] = n620;
    assign response_live[11] = n621;
    assign response_live[12] = n640;
    assign response_live[13] = n641;
    assign response_live[14] = n642;
    assign response_live[15] = n643;
    assign response_live[16] = n644;
    assign response_live[17] = n645;
    assign response_live[18] = n646;
    assign response_live[19] = n647;
    assign response_live[20] = n655;
    assign response_live[21] = n656;
    assign response_live[22] = n657;
    assign response_live[23] = n658;
    assign response_live[24] = n661;

    misr #(.NUM_INPUTS(25)) u_misr (
        .clk            (clk),
        .rst_n          (rst_n),
        .enable         (enable),
        .response       (response_live),
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

    reg primed;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) primed <= 1'b0;
        else if (enable) primed <= 1'b1;
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
