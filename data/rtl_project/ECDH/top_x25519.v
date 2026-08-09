module top_x25519 (
    input  wire         clk, rst_n, start,
    input  wire [255:0] scalar_in, base_in,
    output reg          done,
    output wire [255:0] result_x 
);

    // 1. 입력 래칭 및 바이트 스왑
    reg [255:0] s_reg, b_reg;
    wire [255:0] key_rev, base_rev;
    genvar i;
    generate
        for (i=0; i<32; i=i+1) begin : rev_in
            assign key_rev[i*8 +: 8]  = s_reg[(31-i)*8 +: 8];
            assign base_rev[i*8 +: 8] = b_reg[(31-i)*8 +: 8];
        end
    endgenerate

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin 
            s_reg <= 0; 
            b_reg <= 0; 
        end else if (start) begin 
            s_reg <= scalar_in; 
            b_reg <= base_in; 
        end
    end

    // 기존 wire clamped_key를 reg로 변경하여 한 클럭 파이프라이닝을 수행
    reg [254:0] clamped_key_reg;
    wire [254:0] clamped_key_wire = {1'b1, key_rev[253:3], 3'b000};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) 
            clamped_key_reg <= 0;
        else 
            clamped_key_reg <= clamped_key_wire;
    end
    // ------------------------------------------

    // 2. 하위 모듈 연결
    reg [3:0] state;
    reg core_start, inv_start, mul_start;
    wire core_done, inv_done, mul_done;
    wire [254:0] core_X, core_Z, inv_Z_out, mul_out;

    x25519_core u_core (
        .clk(clk),
        .rst_n(rst_n),
        .start(core_start),
        .scalar_key(clamped_key_reg), // 파이프라인된 레지스터 전달
        .base_u(base_rev[254:0]),
        .done(core_done),
        .out_X(core_X),
        .out_Z(core_Z)
    );

    inversion_25519 u_invert (
        .clk(clk),
        .rst_n(rst_n),
        .start(inv_start),
        .Z_in(core_Z),
        .done(inv_done),
        .Z_inv_out(inv_Z_out)
    );

    mult_mod_25519 u_final_mul (
        .clk(clk),
        .rst_n(rst_n),
        .start(mul_start),
        .in_a(core_X),
        .in_b(inv_Z_out),
        .done(mul_done),
        .out(mul_out)
    );

    // 3. 출력 바이트 뒤집기
    wire [255:0] full_res = {1'b0, mul_out};
    generate
        for (i=0; i<32; i=i+1) begin : rev_out
            assign result_x[(31-i)*8 +: 8] = full_res[i*8 +: 8];
        end
    endgenerate

    // 4. FSM 제어
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin 
            state <= 0; 
            done <= 0; 
            {core_start, inv_start, mul_start} <= 0; 
        end else begin
            {core_start, inv_start, mul_start} <= 0; 
            done <= 1'b0;
            case (state)
                4'd0: if (start) state <= 4'd1;
                4'd1: begin 
                    core_start <= 1; 
                    state <= 4'd2; 
                end
                
                4'd2: if (!core_done) state <= 4'd3;
                4'd3: if (core_done)  state <= 4'd4;
                
                4'd4: begin 
                    inv_start <= 1; 
                    state <= 4'd5; 
                end
                
                4'd5: if (!inv_done) state <= 4'd6;
                4'd6: if (inv_done)  state <= 4'd7;
                
                4'd7: begin 
                    mul_start <= 1; 
                    state <= 4'd8; 
                end
                
                4'd8: if (!mul_done) state <= 4'd9;
                
                4'd9: if (mul_done) begin 
                    done <= 1; 
                    state <= 4'd0; 
                end
                
                default: state <= 4'd0;
            endcase
        end
    end
endmodule