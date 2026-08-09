// misr.v
// ------
// 16-bit Multiple-Input Signature Register.
// src/prpg_misr.py 의 MISR.compress() 를 그대로 옮김:
//   1) 내부 16-bit 상태를 LFSR(taps=0xB400)처럼 한 스텝 전진 (shifted)
//   2) NUM_INPUTS-bit response를 16개 채널로 XOR-fold (채널 k = i % 16)
//   3) 새 signature = shifted ^ fold
//
// signature: 등록된(=이전 사이클까지 반영된) 현재 시그니처.
// next_signature: 이번 사이클에 enable이면 signature가 될 값(조합 출력).
// 상위(top)에서 "새 시그니처 vs 이전 시그니처"의 Hamming Distance를
// 같은 사이클에 조합적으로 계산해 controller에 넣어야 하므로 둘 다 노출한다.

module misr #(
    parameter NUM_INPUTS   = 16,
    parameter [15:0] TAPS  = 16'hB400
)(
    input  wire                    clk,
    input  wire                    rst_n,
    input  wire                    enable,
    input  wire [NUM_INPUTS-1:0]   response,
    output reg  [15:0]             signature,
    output wire [15:0]             next_signature
);

    wire        lsb          = signature[0];
    wire [15:0] shifted_raw  = signature >> 1;
    wire [15:0] shifted      = lsb ? (shifted_raw ^ TAPS) : shifted_raw;

    reg [15:0] fold;
    integer i;
    always @* begin
        fold = 16'b0;
        for (i = 0; i < NUM_INPUTS; i = i + 1)
            fold[i % 16] = fold[i % 16] ^ response[i];
    end

    assign next_signature = shifted ^ fold;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            signature <= 16'b0;
        else if (enable)
            signature <= next_signature;
    end

endmodule
