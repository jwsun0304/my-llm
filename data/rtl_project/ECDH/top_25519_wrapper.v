`timescale 1ns / 1ns
module top_x25519_wrapper (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,      // 입력을 시작하라는 신호
    input  wire [63:0] din,        // 64비트 입력 버스 (Scalar -> Base 순서)
    output wire [63:0] dout,       // 64비트 출력 버스
    output wire        out_valid,  // 결과가 나가는 4클럭 동안 즉시 High
    output reg         busy        // 모듈 동작 중 표시
);

    // FSM 상태 정의
    localparam IDLE        = 3'd0;
    localparam LOAD_SCALAR = 3'd1; // Scalar 64bit x 4클럭 로드
    localparam LOAD_BASE   = 3'd2; // Base   64bit x 4클럭 로드
    localparam CALC        = 3'd3; // 내부 Core 연산 대기
    localparam UNLOAD      = 3'd4; // 결과 64bit x 4클럭 출력

    reg [2:0]   state;
    reg [1:0]   cnt;               // 4클럭 카운터
    reg [255:0] scalar_reg;
    reg [255:0] base_reg;
    reg [255:0] result_reg;

    // 내부 엔진(top_x25519) 연결 신호
    reg         engine_start;
    wire        engine_done;
    wire [255:0] engine_out;

    // --- 기존 계층 구조 유지: u_top 호출 ---
    top_x25519 u_top (
        .clk(clk),
        .rst_n(rst_n),
        .start(engine_start),
        .scalar_in(scalar_reg),
        .base_in(base_reg),
        .done(engine_done),
        .result_x(engine_out)
    );

    // UNLOAD 상태가 되는 즉시 1이 됨
    assign out_valid = (state == UNLOAD);

    // 카운터 0일 때 즉시 첫 조각 출력
    assign dout = (state == UNLOAD) ? (
                  (cnt == 2'd0) ? result_reg[63:0]   :
                  (cnt == 2'd1) ? result_reg[127:64] :
                  (cnt == 2'd2) ? result_reg[191:128]: result_reg[255:192]
                 ) : 64'd0;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state        <= IDLE;
            cnt          <= 0;
            busy         <= 0;
            engine_start <= 0;
            scalar_reg   <= 0;
            base_reg     <= 0;
            result_reg   <= 0;
        end else begin
            engine_start <= 0; // Pulse 유지

            case (state)
                IDLE: begin
                    if (start) begin
                        state <= LOAD_SCALAR;
                        cnt <= 0;
                        busy <= 1;
                        scalar_reg[63:0] <= din; // 첫 번째 64비트 즉시 로드
                    end else begin
                        busy <= 0;
                    end
                end

                LOAD_SCALAR: begin
                    cnt <= cnt + 1;
                    if (cnt == 2'd0) scalar_reg[127:64]  <= din;
                    if (cnt == 2'd1) scalar_reg[191:128] <= din;
                    if (cnt == 2'd2) begin 
                        scalar_reg[255:192] <= din;
                        state <= LOAD_BASE;
                        cnt <= 0;
                    end
                end

                LOAD_BASE: begin
                    if (cnt == 2'd0) base_reg[63:0]    <= din;
                    if (cnt == 2'd1) base_reg[127:64]  <= din;
                    if (cnt == 2'd2) base_reg[191:128] <= din;
                    if (cnt == 2'd3) begin 
                        base_reg[255:192] <= din;
                        state <= CALC;
                        engine_start <= 1; // 연산 시작!
                        cnt <= 0;
                    end else begin
                        cnt <= cnt + 1;
                    end
                end

                CALC: begin
                    if (engine_done) begin
                        result_reg <= engine_out; // 연산 결과 저장
                        state <= UNLOAD;
                        cnt <= 0;
                    end
                end

                UNLOAD: begin
                    // 4클럭 동안 dout에 데이터 조각이 실리고 out_valid는 wire에 의해 계속 High
                    if (cnt == 2'd3) begin
                        state <= IDLE;
                        busy <= 0;
                        cnt <= 0;
                    end else begin
                        cnt <= cnt + 1;
                    end
                end

                default: state <= IDLE;
            endcase
        end
    end
endmodule