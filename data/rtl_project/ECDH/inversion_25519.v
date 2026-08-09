`timescale 1ns / 1ns

module inversion_25519 (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         start,
    input  wire [254:0] Z_in,
    output reg          done,
    output reg  [254:0] Z_inv_out
);

    localparam [254:0] P_MINUS_2 = 255'h7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEB;

    // FSM States
    localparam IDLE  = 3'd0;
    localparam SQR   = 3'd1;
    localparam WAIT1 = 3'd2;
    localparam MUL   = 3'd3;
    localparam WAIT2 = 3'd4;
    localparam NEXT  = 3'd5;

    reg [2:0]   state;
    reg [7:0]   bit_idx; // 254 ~ 0
    reg [254:0] base_reg;
    reg [254:0] result_reg;

    // 모듈러 곱셈기 제어 신호
    reg         mul_start;
    wire        mul_done;
    reg [254:0] mul_in_a;
    reg [254:0] mul_in_b;
    wire [254:0] mul_out;

    // 곱셈기 인스턴스화 (재사용)
    mult_mod_25519 inv_mult (
        .clk   (clk),
        .rst_n (rst_n),
        .start (mul_start),
        .in_a  (mul_in_a),
        .in_b  (mul_in_b),
        .done  (mul_done),
        .out   (mul_out)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state      <= IDLE;
            bit_idx    <= 8'd254;
            base_reg   <= 255'd0;
            result_reg <= 255'd1;
            done       <= 1'b0;
            Z_inv_out  <= 255'd0;
            mul_start  <= 1'b0;
            
            mul_in_a   <= 255'd0;
            mul_in_b   <= 255'd0;
        end else begin
            done      <= 1'b0;
            mul_start <= 1'b0;

            case (state)
                IDLE: begin
                    if (start) begin
                        base_reg   <= Z_in;
                        result_reg <= 255'd1;
                        bit_idx    <= 8'd254; // MSB부터 시작
                        state      <= SQR;
                    end
                end

                SQR: begin
                    mul_in_a  <= result_reg;
                    mul_in_b  <= result_reg; // 제곱
                    mul_start <= 1'b1;
                    state     <= WAIT1;
                end

                WAIT1: begin
                    if (mul_done) begin
                        result_reg <= mul_out;
                        // 현재 비트가 1이면 곱하기 단계로, 0이면 다음 비트로
                        if (P_MINUS_2[bit_idx]) state <= MUL;
                        else                    state <= NEXT;
                    end
                end

                MUL: begin
                    mul_in_a  <= result_reg;
                    mul_in_b  <= base_reg;   // 기존 Z_in 값 곱하기
                    mul_start <= 1'b1;
                    state     <= WAIT2;
                end

                WAIT2: begin
                    if (mul_done) begin
                        result_reg <= mul_out;
                        state      <= NEXT;
                    end
                end

                NEXT: begin
                    if (bit_idx == 8'd0) begin
                        Z_inv_out <= result_reg;
                        done      <= 1'b1;
                        state     <= IDLE;
                    end else begin
                        bit_idx <= bit_idx - 1'b1;
                        state   <= SQR;
                    end
                end
            endcase
        end
    end
endmodule