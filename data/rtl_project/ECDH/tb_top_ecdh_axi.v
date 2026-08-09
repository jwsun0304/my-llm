`timescale 1ns / 1ns

module tb_top_ecdh_axi;

    reg          clk = 0;
    reg          rst_n = 0;
    reg  [63:0]  in = 0;
    reg          in_valid = 0;
    reg          in_last = 0;
    wire         in_ready;
    wire [63:0]  out;
    wire         out_valid;
    wire         out_last;
    reg          out_ready = 1;
    wire         done;
    reg          mode = 1;

    reg [255:0] test_scalar = 256'h77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a;
    reg [255:0] test_base   = 256'hde9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f;
    reg [255:0] expected    = 256'h4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742;
    reg [255:0] actual_res  = 0;

    integer i; // 데이터 수집용 인덱스

    top_ecdh_axi uut (
        .clk(clk), .rst_n(rst_n), .in(in), .in_valid(in_valid), .in_last(in_last),
        .in_ready(in_ready), .out(out), .out_valid(out_valid), .out_last(out_last),
        .out_ready(out_ready), .done(done), .mode(mode)
    );

    always #1 clk = ~clk;

    initial begin
        $display("[%0t] Simulation Started...", $time);
        
        // 1. 리셋
        #10 rst_n = 1;
        
        // =====================================================================
        // STEP 1: 입력 (가속기가 in_ready를 켤 때까지 대기)
        // =====================================================================
        while (in_ready == 0) @(posedge clk); // [핵심] 리셋 후 ready 뜰 때까지 대기
        
        in_valid = 1;
        in = test_scalar[63:0];   @(posedge clk);
        in = test_scalar[127:64]; @(posedge clk);
        in = test_scalar[191:128];@(posedge clk);
        in = test_scalar[255:192];@(posedge clk);
        
        in = test_base[63:0];     @(posedge clk);
        in = test_base[127:64];   @(posedge clk);
        in = test_base[191:128];  @(posedge clk);
        in = test_base[255:192];  in_last = 1; 
        @(posedge clk);
        
        in_valid = 0; in_last = 0; in = 0;

        // =====================================================================
        // STEP 2: 연산 결과 수집 (Mismatch 해결을 위한 AXI-Stream 정석 루프)
        // =====================================================================
        i = 0;
        while (i < 4) begin
            @(posedge clk);
            if (out_valid && out_ready) begin
                if (i == 0) actual_res[63:0]   = out;
                if (i == 1) actual_res[127:64] = out;
                if (i == 2) actual_res[191:128]= out;
                if (i == 3) actual_res[255:192]= out;
                i = i + 1; // 1개 받을 때마다 카운트업
            end
        end

        // =====================================================================
        // STEP 3: 최종 검증
        // =====================================================================
        wait(done == 1);
        #10;
        
        $display("\n========================================================");
        $display("Expected: %h", expected);
        $display("Actual  : %h", actual_res);
        $display("--------------------------------------------------------");
        if (actual_res === expected) 
            $display(">>> [SUCCESS] Result matches perfectly!");
        else                         
            $display(">>> [FAILURE] Mismatch occurred.");
        $display("========================================================\n");
        
        #100 $finish;
    end

    // 타임아웃 안전장치
    initial begin
        #5_000_000;
        $display("\n[TIMEOUT] Simulation took too long. Force quitting.");
        $finish;
    end

endmodule
