module x25519_core (
    input  wire         clk, rst_n, start,
    input  wire [254:0] base_u, scalar_key,
    output wire         done,    
    output wire [254:0] out_X,
    output wire [254:0] out_Z
);
    // 내부 신호
    wire [3:0]   mux_sel_a, mux_sel_b;
    wire [1:0]   alu_op;
    wire [7:0]   reg_we;
    wire         cswap, alu_start, alu_done_raw, done_raw;
    wire [254:0] alu_out_raw;
    
    reg [254:0] X1, Z1, X2, Z2, T1, T2, T3, T4;
    reg [254:0] alu_in_a, alu_in_b;

    // --- 파이프라인 레지스터 (dont_touch 삭제) ---
    reg [7:0]   we_pipe;
    reg         cswap_pipe;
    reg [254:0] alu_out_pipe;
    reg         alu_done_pipe;
    reg         alu_start_pipe;
    reg         done_pipe;

    // 1. 파이프라인 동기화
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            we_pipe        <= 8'h0;
            cswap_pipe     <= 1'b0;
            alu_start_pipe <= 1'b0;
            alu_out_pipe   <= 255'd0;
            alu_done_pipe  <= 1'b0;
            done_pipe      <= 1'b1; // 초기 상태는 작업 없음
        end else begin
            we_pipe        <= reg_we;
            cswap_pipe     <= cswap;
            alu_start_pipe <= alu_start;
            alu_out_pipe   <= alu_out_raw;
            alu_done_pipe  <= alu_done_raw;
            done_pipe      <= done_raw;
        end
    end

    // 2. 메인 데이터 레지스터 업데이트
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            {X1, Z1, X2, Z2, T1, T2, T3, T4} <= 2040'd0; // 한 번에 초기화
        end else if (start) begin
            X1 <= 255'd1; Z1 <= 255'd0; X2 <= base_u; Z2 <= 255'd1;
            {T1, T2, T3, T4} <= 1020'd0;
        end else begin
            // 툴은 여기서 pipe 신호들이 쓰이는 것을 보고 최적화에서 제외합니다.
            // CSWAP 로직
            if (cswap_pipe) begin
                X1 <= X2; X2 <= X1;
                Z1 <= Z2; Z2 <= Z1;
            end else begin
                // Write Enable 로직
                if (we_pipe[0]) X1 <= alu_out_pipe;
                if (we_pipe[1]) Z1 <= alu_out_pipe;
                if (we_pipe[2]) X2 <= alu_out_pipe;
                if (we_pipe[3]) Z2 <= alu_out_pipe;
            end
            
            if (we_pipe[4]) T1 <= alu_out_pipe;
            if (we_pipe[5]) T2 <= alu_out_pipe;
            if (we_pipe[6]) T3 <= alu_out_pipe;
            if (we_pipe[7]) T4 <= alu_out_pipe;
        end
    end

    // 3. ALU 입력 MUX (동기화된 값 사용)
    always @(*) begin
        case (mux_sel_a)
            4'd0: alu_in_a = X1; 4'd1: alu_in_a = Z1; 4'd2: alu_in_a = X2;
            4'd3: alu_in_a = Z2; 4'd4: alu_in_a = T1; 4'd5: alu_in_a = T2;
            4'd6: alu_in_a = T3; 4'd7: alu_in_a = T4; default: alu_in_a = 255'd0;
        endcase
        case (mux_sel_b)
            4'd0: alu_in_b = X1; 4'd1: alu_in_b = Z1; 4'd2: alu_in_b = X2;
            4'd3: alu_in_b = Z2; 4'd4: alu_in_b = T1; 4'd5: alu_in_b = T2;
            4'd6: alu_in_b = T3; 4'd7: alu_in_b = T4; 4'd8: alu_in_b = base_u;
            4'd9: alu_in_b = 255'd121665; default: alu_in_b = 255'd0;
        endcase
    end

    // 하위 모듈 연결
    mont_ladder ctrl_inst (
        .clk(clk), .rst_n(rst_n), .start(start), .scalar_key(scalar_key),
        .done(done_raw),
        .mux_sel_a(mux_sel_a), .mux_sel_b(mux_sel_b), .alu_op(alu_op),
        .reg_we(reg_we), .cswap(cswap), 
        .alu_start(alu_start),
        .alu_done(alu_done_pipe) // 지연된 신호를 피드백
    );

    shared_alu_25519 alu_inst (
        .clk(clk), .rst_n(rst_n), 
        .start(alu_start_pipe), // 지연된 신호로 시작
        .op(alu_op), .in_a(alu_in_a), .in_b(alu_in_b), 
        .done(alu_done_raw), .out(alu_out_raw)
    );

    assign done  = done_pipe;
    assign out_X = X1;
    assign out_Z = Z1;

endmodule