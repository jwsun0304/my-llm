module mult_mod_25519 (
    input  wire         clk, rst_n, start,
    input  wire [254:0] in_a, in_b,
    output reg          done, 
    output reg [254:0]  out
);
    // 비교기 제거를 위해 파이프라인을 1단 더 늘려 RED4_C 추가
    localparam IDLE        = 5'd0, 
               CALC        = 5'd1, 
               ADD1_A      = 5'd2, 
               ADD1_B      = 5'd3, 
               ADD2_A      = 5'd4,
               ADD2_B      = 5'd5,
               RED1_A      = 5'd6, 
               RED1_A_HIGH = 5'd7, 
               RED1_B      = 5'd8, 
               RED1_C      = 5'd9, 
               RED2_A      = 5'd10, 
               RED2_B      = 5'd11, 
               RED3_A      = 5'd12, 
               RED3_B      = 5'd13,  
               RED3_C      = 5'd14, 
               RED4_A      = 5'd15, 
               RED4_B      = 5'd16,
               RED4_C      = 5'd17;
               
    localparam [254:0] P = 255'h7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFED;
    
    reg [4:0] state;
    reg [7:0]   count;
    reg [509:0] acc_s, acc_c, shift_a;
    reg [254:0] shift_b;
    reg [509:0] final_acc;
    
    reg [127:0] sum_add1, sum_add2, sum_red1a, sum_red1b, sum_red2, sum_red3;
    reg         cy_add1,  cy_add2,  cy_red1a,  cy_red1b,  cy_red2,  cy_red3;

    reg [254:0] final_acc_low;
    reg         final_acc_carry;

    reg [259:0] red_prod_tmp;   
    reg [259:0] red_prod;
    reg [260:0] wide_sum;
    reg [255:0] final_sum_reg;
    reg [11:0]  red_tmp_mul;
    
    reg [127:0] sub_low_reg;
    reg         sub_borrow_reg;
    reg [127:0] sub_high_reg;
    reg         final_borrow;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE; done <= 0; out <= 0;
            {acc_s, acc_c, shift_a, shift_b, count, red_prod, wide_sum, final_sum_reg, 
             final_acc, final_acc_low, final_acc_carry, red_prod_tmp, red_tmp_mul} <= 0;
            {sum_add1, sum_add2, sum_red1a, sum_red1b, sum_red2, sum_red3} <= 0;
            {cy_add1, cy_add2, cy_red1a, cy_red1b, cy_red2, cy_red3} <= 0;
            // 초기화 추가
            {sub_borrow_reg, sub_low_reg, sub_high_reg, final_borrow} <= 0;
        end else begin
            done <= 1'b0;
            case (state)
                IDLE: if (start) begin
                    acc_s <= 0; acc_c <= 0; count <= 0;
                    shift_a <= {255'd0, in_a}; shift_b <= in_b;
                    state <= CALC;
                end

                CALC: begin
                    if (shift_b[0]) begin
                        acc_s <= acc_s ^ acc_c ^ shift_a;
                        acc_c <= ((acc_s & acc_c) | (acc_c & shift_a) | (shift_a & acc_s)) << 1;
                    end
                    shift_a <= shift_a << 1; 
                    shift_b <= shift_b >> 1;
                    if (count == 8'd254) state <= ADD1_A;
                    else                 count <= count + 1'b1;
                end

                ADD1_A: begin 
                    {cy_add1, sum_add1} <= acc_s[127:0] + acc_c[127:0]; 
                    state <= ADD1_B; 
                end

                ADD1_B: begin
                    {final_acc_carry, final_acc_low[254:128]} <= acc_s[254:128] + acc_c[254:128] + cy_add1;
                    final_acc_low[127:0] <= sum_add1;
                    state <= ADD2_A;
                end

                ADD2_A: begin
                    {cy_add2, sum_add2} <= acc_s[382:255] + acc_c[382:255] + final_acc_carry;
                    state <= ADD2_B;
                end

                ADD2_B: begin
                    final_acc[509:383] <= acc_s[509:383] + acc_c[509:383] + cy_add2;
                    final_acc[382:255] <= sum_add2;
                    final_acc[254:0]   <= final_acc_low;
                    state <= RED1_A;
                end

                RED1_A: begin 
                    {cy_red1a, sum_red1a} <= {final_acc[378:255], 4'd0} + {final_acc[381:255], 1'd0};
                    state <= RED1_A_HIGH;
                end

                RED1_A_HIGH: begin
                    red_prod_tmp[259:128] <= {1'b0, final_acc[509:379]} + {4'd0, final_acc[509:382]} + cy_red1a;
                    red_prod_tmp[127:0]   <= sum_red1a;
                    state <= RED1_B;
                end

                RED1_B: begin
                    {cy_red1b, sum_red1b} <= red_prod_tmp[127:0] + final_acc[382:255];
                    state <= RED1_C;
                end

                RED1_C: begin
                    red_prod[259:128] <= red_prod_tmp[259:128] + final_acc[509:383] + cy_red1b;
                    red_prod[127:0]   <= sum_red1b;
                    state <= RED2_A; 
                end

                RED2_A: begin 
                    {cy_red2, sum_red2} <= red_prod[127:0] + final_acc[127:0]; 
                    state <= RED2_B; 
                end
                
                RED2_B: begin 
                    wide_sum[260:128] <= {1'b0, red_prod[259:128]} + final_acc[254:128] + cy_red2; 
                    wide_sum[127:0]   <= sum_red2;
                    state <= RED3_A; 
                end
                
                RED3_A: begin
                    red_tmp_mul <= wide_sum[260:255] * 5'd19;
                    state <= RED3_B;
                end

                RED3_B: begin
                    {cy_red3, sum_red3} <= wide_sum[127:0] + red_tmp_mul;
                    state <= RED3_C;
                end

                RED3_C: begin
                    final_sum_reg[255:128] <= wide_sum[254:128] + cy_red3;
                    final_sum_reg[127:0]   <= sum_red3;
                    state <= RED4_A;
                end


                RED4_A: begin
                    // 1단계: 하위 128비트 뺄셈
                    {sub_borrow_reg, sub_low_reg} <= {1'b0, final_sum_reg[127:0]} - {1'b0, P[127:0]};
                    state <= RED4_B;
                end

                RED4_B: begin
                    // 2단계: 상위 128비트 뺄셈
                    {final_borrow, sub_high_reg} <= {1'b0, final_sum_reg[255:128]} - {2'b00, P[254:128]} - sub_borrow_reg;
                    state <= RED4_C;
                end

                RED4_C: begin
                    // 3단계: 비교기 없이 MUX만으로 결과 도출!
                    if (!final_borrow) begin
                        out <= {sub_high_reg[126:0], sub_low_reg}; // 총 255비트
                    end else begin
                        out <= final_sum_reg[254:0];
                    end
                    done <= 1'b1;
                    state <= IDLE;
                end

                default: state <= IDLE;
            endcase
        end
    end
endmodule
