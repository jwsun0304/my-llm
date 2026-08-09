`timescale 1ns / 1ns
module mont_ladder (
    input  wire         clk, rst_n, start,
    input  wire [254:0] scalar_key,
    output reg          done,
    output reg  [3:0]   mux_sel_a, mux_sel_b,
    output reg  [1:0]   alu_op,
    output reg  [7:0]   reg_we,
    output reg          cswap, alu_start,
    input  wire         alu_done
);

    reg [5:0] state;
    reg [5:0] next_state;
    
    reg [7:0] bit_cnt;
    reg       prev_bit;

    localparam S_IDLE = 6'd0, S_CSWAP_PRE = 6'd1, S_LOOP_CHK = 6'd40, S_CSWAP_POST = 6'd41;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE; bit_cnt <= 8'd254; prev_bit <= 1'b0;
        end else begin
            state <= next_state;
            if (state == S_IDLE && start) begin bit_cnt <= 8'd254; prev_bit <= 1'b0; end
            else if (state == S_LOOP_CHK) begin bit_cnt <= bit_cnt - 1; prev_bit <= scalar_key[bit_cnt]; end
        end
    end

    always @(*) begin
        next_state = state; done = 0; cswap = 0; alu_start = 0; reg_we = 0; mux_sel_a = 0; mux_sel_b = 0; alu_op = 0;

        case (state)
            S_IDLE: if (start) next_state = S_CSWAP_PRE;
            S_CSWAP_PRE: begin cswap = prev_bit ^ scalar_key[bit_cnt]; next_state = 6'd2; end

            // 1. T1 = X1 + Z1
            6'd2: begin mux_sel_a=0; mux_sel_b=1; alu_op=0; alu_start=1; next_state=6'd3; end
            6'd3: begin mux_sel_a=0; mux_sel_b=1; alu_op=0; if(alu_done) begin reg_we=8'b00010000; next_state=6'd4; end end
            // 2. T2 = X1 - Z1
            6'd4: begin mux_sel_a=0; mux_sel_b=1; alu_op=1; alu_start=1; next_state=6'd5; end
            6'd5: begin mux_sel_a=0; mux_sel_b=1; alu_op=1; if(alu_done) begin reg_we=8'b00100000; next_state=6'd6; end end
            // 3. T3 = X2 + Z2
            6'd6: begin mux_sel_a=2; mux_sel_b=3; alu_op=0; alu_start=1; next_state=6'd7; end
            6'd7: begin mux_sel_a=2; mux_sel_b=3; alu_op=0; if(alu_done) begin reg_we=8'b01000000; next_state=6'd8; end end
            // 4. T4 = X2 - Z2
            6'd8: begin mux_sel_a=2; mux_sel_b=3; alu_op=1; alu_start=1; next_state=6'd9; end
            6'd9: begin mux_sel_a=2; mux_sel_b=3; alu_op=1; if(alu_done) begin reg_we=8'b10000000; next_state=6'd10; end end
            // 5. T4 = T4 * T1 (DA)
            6'd10: begin mux_sel_a=7; mux_sel_b=4; alu_op=2; alu_start=1; next_state=6'd11; end
            6'd11: begin mux_sel_a=7; mux_sel_b=4; alu_op=2; if(alu_done) begin reg_we=8'b10000000; next_state=6'd12; end end
            // 6. T3 = T3 * T2 (CB)
            6'd12: begin mux_sel_a=6; mux_sel_b=5; alu_op=2; alu_start=1; next_state=6'd13; end
            6'd13: begin mux_sel_a=6; mux_sel_b=5; alu_op=2; if(alu_done) begin reg_we=8'b01000000; next_state=6'd14; end end
            // 7. X2 = T4 + T3 (DA+CB)
            6'd14: begin mux_sel_a=7; mux_sel_b=6; alu_op=0; alu_start=1; next_state=6'd15; end
            6'd15: begin mux_sel_a=7; mux_sel_b=6; alu_op=0; if(alu_done) begin reg_we=8'b00000100; next_state=6'd16; end end
            // 8. Z2 = T4 - T3 (DA-CB)
            6'd16: begin mux_sel_a=7; mux_sel_b=6; alu_op=1; alu_start=1; next_state=6'd17; end
            6'd17: begin mux_sel_a=7; mux_sel_b=6; alu_op=1; if(alu_done) begin reg_we=8'b00001000; next_state=6'd18; end end
            // 9. X2 = X2^2
            6'd18: begin mux_sel_a=2; mux_sel_b=2; alu_op=2; alu_start=1; next_state=6'd19; end
            6'd19: begin mux_sel_a=2; mux_sel_b=2; alu_op=2; if(alu_done) begin reg_we=8'b00000100; next_state=6'd20; end end
            // 10. Z2 = Z2^2
            6'd20: begin mux_sel_a=3; mux_sel_b=3; alu_op=2; alu_start=1; next_state=6'd21; end
            6'd21: begin mux_sel_a=3; mux_sel_b=3; alu_op=2; if(alu_done) begin reg_we=8'b00001000; next_state=6'd22; end end
            // 11. Z2 = Z2 * base_u
            6'd22: begin mux_sel_a=3; mux_sel_b=8; alu_op=2; alu_start=1; next_state=6'd23; end
            6'd23: begin mux_sel_a=3; mux_sel_b=8; alu_op=2; if(alu_done) begin reg_we=8'b00001000; next_state=6'd24; end end
            // 12. T1 = T1^2 (AA)
            6'd24: begin mux_sel_a=4; mux_sel_b=4; alu_op=2; alu_start=1; next_state=6'd25; end
            6'd25: begin mux_sel_a=4; mux_sel_b=4; alu_op=2; if(alu_done) begin reg_we=8'b00010000; next_state=6'd26; end end
            // 13. T2 = T2^2 (BB)
            6'd26: begin mux_sel_a=5; mux_sel_b=5; alu_op=2; alu_start=1; next_state=6'd27; end
            6'd27: begin mux_sel_a=5; mux_sel_b=5; alu_op=2; if(alu_done) begin reg_we=8'b00100000; next_state=6'd28; end end
            // 14. X1 = AA * BB
            6'd28: begin mux_sel_a=4; mux_sel_b=5; alu_op=2; alu_start=1; next_state=6'd29; end
            6'd29: begin mux_sel_a=4; mux_sel_b=5; alu_op=2; if(alu_done) begin reg_we=8'b00000001; next_state=6'd30; end end
            // 15. T3 = AA - BB (E)
            6'd30: begin mux_sel_a=4; mux_sel_b=5; alu_op=1; alu_start=1; next_state=6'd31; end
            6'd31: begin mux_sel_a=4; mux_sel_b=5; alu_op=1; if(alu_done) begin reg_we=8'b01000000; next_state=6'd32; end end
            // 16. T4 = E * 121665
            6'd32: begin mux_sel_a=6; mux_sel_b=9; alu_op=2; alu_start=1; next_state=6'd33; end
            6'd33: begin mux_sel_a=6; mux_sel_b=9; alu_op=2; if(alu_done) begin reg_we=8'b10000000; next_state=6'd34; end end
            // 17. T4 = AA + T4
            6'd34: begin mux_sel_a=4; mux_sel_b=7; alu_op=0; alu_start=1; next_state=6'd35; end
            6'd35: begin mux_sel_a=4; mux_sel_b=7; alu_op=0; if(alu_done) begin reg_we=8'b10000000; next_state=6'd36; end end
            // 18. Z1 = E * T4
            6'd36: begin mux_sel_a=6; mux_sel_b=7; alu_op=2; alu_start=1; next_state=6'd37; end
            6'd37: begin mux_sel_a=6; mux_sel_b=7; alu_op=2; if(alu_done) begin reg_we=8'b00000010; next_state=S_LOOP_CHK; end end

            S_LOOP_CHK: if (bit_cnt == 0) next_state = S_CSWAP_POST; else next_state = S_CSWAP_PRE;
            S_CSWAP_POST: begin cswap = scalar_key[0] ^ 1'b0; done = 1; next_state = S_IDLE; end
            default: next_state = S_IDLE;
        endcase
    end
endmodule