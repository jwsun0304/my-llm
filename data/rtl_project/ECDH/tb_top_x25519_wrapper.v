`timescale 1ns / 1ns

module tb_top_x25519_wrapper;

    reg         clk;
    reg         rst_n;
    reg         start;
    reg  [63:0] din;
    wire [63:0] dout;
    wire        out_valid;
    wire        busy;

    // --- RFC 8037 Appendix A.6 표준 테스트 벡터 ---
    reg [255:0] test_scalar = 256'h77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a;
    reg [255:0] test_base   = 256'hde9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f;
    reg [255:0] expected    = 256'h4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742;
    reg [255:0] actual_res;

    // 설계 모듈 연결
    top_x25519_wrapper uut (
        .clk(clk),
        .rst_n(rst_n),
        .start(start),
        .din(din),
        .dout(dout),
        .out_valid(out_valid),
        .busy(busy)
    );

    // --- 클럭 생성: 주기 2ns (500MHz) ---
    // #1마다 반전시키면 High 1ns + Low 1ns = 총 2ns가 됩니다.
    always #1 clk = ~clk;

    initial begin
        // 초기화
        clk = 0; rst_n = 0; start = 0; din = 0; actual_res = 0;
        
        // 리셋 기간 (클럭 주기에 맞춰 조정)
        #10 rst_n = 1;
        #10;

        // --- STEP 1: Scalar 입력 (64bit x 4클럭) ---
        @(posedge clk);
        start = 1;
        din = test_scalar[63:0];
        
        @(posedge clk);
        start = 0;
        din = test_scalar[127:64];
        
        @(posedge clk);
        din = test_scalar[191:128];
        
        @(posedge clk);
        din = test_scalar[255:192];

        // --- STEP 2: Base 입력 (64bit x 4클럭) ---
        @(posedge clk);
        din = test_base[63:0];
        
        @(posedge clk);
        din = test_base[127:64];
        
        @(posedge clk);
        din = test_base[191:128];
        
        @(posedge clk);
        din = test_base[255:192];

        @(posedge clk);
        din = 0;

        // --- STEP 3: 연산 대기 ---
        $display("[%t] 500MHz (2ns) RFC Test Started...", $time);
        wait(out_valid == 1);
        
        // --- STEP 4: 결과 수집 (64bit x 4클럭) ---
        @(posedge clk); // out_valid 확인 후 첫 번째 데이터 래치
        actual_res[63:0] = dout;
        
        @(posedge clk);
        actual_res[127:64] = dout;
        
        @(posedge clk);
        actual_res[191:128] = dout;
        
        @(posedge clk);
        actual_res[255:192] = dout;

        // --- STEP 5: 최종 검증 ---
        #4;
        $display("\n========================================================");
        $display("RFC 8037 X25519 ECDH-ES Verification (@500MHz)");
        $display("--------------------------------------------------------");
        $display("Expected Z: %h", expected);
        $display("Actual   Z: %h", actual_res);
        $display("--------------------------------------------------------");
        
        if (actual_res === expected) begin
            $display(">>> [SUCCESS] Result matches RFC 8037!");
        end else begin
            $display(">>> [FAILURE] Mismatched! Check timing or logic.");
        end
        $display("========================================================\n");

        #20;
        $finish;
    end

endmodule