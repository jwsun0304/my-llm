`timescale 1ns / 1ns

module shared_alu_25519 (
    input  wire         clk, rst_n, start,
    input  wire [1:0]   op,
    input  wire [254:0] in_a, in_b,
    output reg          done, 
    output reg [254:0]  out
);
    localparam [254:0] P = 255'h7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFED;
    
    // 상태 정의: S5가 추가되었고, WAIT_MUL은 6으로 밀려났습니다. (3비트로 충분히 표현 가능)
    localparam IDLE=3'd0, S1=3'd1, S2=3'd2, S3=3'd3, S4=3'd4, S5=3'd5, WAIT_MUL=3'd6;
    
    reg [2:0]   state;
    reg [254:0] a_reg, b_reg; 
    reg [127:0] low_res; 

    // ==========================================
    // 툴 속성(max_fanout 등)을 제거한 순수 레지스터 선언
    // (물리적 최적화는 Vivado의 phys_opt_design에 맡깁니다)
    // ==========================================
    reg carry_out;
    reg op_sub;
    
    reg [254:0] res_raw;      // A +/- B 의 순수 결과
    reg         final_carry;  // 255비트 연산의 최종 올림/내림수
    reg [255:0] res_adj;      // P를 더하거나 뺀 보정값

    reg [127:0] adj_low;
    reg         adj_carry;

    // 모듈러 곱셈기 연결
    reg mul_start; wire mul_done; wire [254:0] mul_out;
    mult_mod_25519 mul_inst (
        .clk(clk), .rst_n(rst_n), .start(mul_start),
        .in_a(a_reg), .in_b(b_reg), .done(mul_done), .out(mul_out)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin 
            state <= IDLE; done <= 0; out <= 0; mul_start <= 0;
            a_reg <= 0; b_reg <= 0; low_res <= 0; 
            carry_out <= 0; op_sub <= 0; res_raw <= 0; 
            final_carry <= 0; res_adj <= 0;
            adj_low <= 0; adj_carry <= 0;
        end else begin
            done <= 0; mul_start <= 0;
            case (state)
                IDLE: if (start) begin
                    a_reg <= in_a; b_reg <= in_b; op_sub <= op[0];
                    if (op == 2'd2) begin mul_start <= 1; state <= WAIT_MUL; end
                    else            state <= S1;
                end
                
                S1: begin // [1단계] 하위 128비트 연산
                    if (!op_sub) {carry_out, low_res} <= a_reg[127:0] + b_reg[127:0];
                    else         {carry_out, low_res} <= a_reg[127:0] - b_reg[127:0];
                    state <= S2;
                end

                S2: begin // [2단계] 상위 127비트 연산 및 결과 통합
                    if (!op_sub) {final_carry, res_raw[254:128]} <= a_reg[254:128] + b_reg[254:128] + carry_out;
                    else         {final_carry, res_raw[254:128]} <= a_reg[254:128] - b_reg[254:128] - carry_out;
                    res_raw[127:0] <= low_res;
                    state <= S3;
                end

                S3: begin // [3단계] 보정값 계산을 반으로 쪼갬 (하위 128비트 먼저)
                    // 덧셈 시 19 더하기, 뺄셈 시 P 더하기
                    if (!op_sub) {adj_carry, adj_low} <= res_raw[127:0] + 128'd19; 
                    else         {adj_carry, adj_low} <= res_raw[127:0] + P[127:0];
                    state <= S4;
                end

                S4: begin // [4단계] 보정값 계산 마무리 (상위 127비트 + 캐리)
                    if (!op_sub) res_adj[255:128] <= {1'b0, res_raw[254:128]} + adj_carry; // 19의 상위 비트는 0이므로 생략
                    else         res_adj[255:128] <= {1'b0, res_raw[254:128]} + {1'b0, P[254:128]} + adj_carry;
                    
                    res_adj[127:0] <= adj_low; // 하위 비트 합치기
                    state <= S5;
                end

                S5: begin // [5단계] 최종 선택
                    if (!op_sub) begin
                        // 덧셈 결과 선택 (res_adj[255]는 res_adj가 256'h80...0 이상인지 확인하는 것과 동일)
                        if (final_carry || res_adj[255]) 
                             out <= res_adj[254:0];
                        else out <= res_raw;
                    end else begin
                        // 뺄셈 결과 선택: 결과가 음수(final_carry==1)면 보정값, 아니면 원본
                        if (final_carry) out <= res_adj[254:0];
                        else             out <= res_raw;
                    end
                    done <= 1; state <= IDLE;
                end

                WAIT_MUL: if (mul_done) begin out <= mul_out; done <= 1; state <= IDLE; end
                
                default: state <= IDLE;
            endcase
        end
    end
endmodule

