`timescale 1ns / 1ns

module tb_top_x25519;

    // --------------------------------------------------------------------
    // 1. 신호 정의
    // --------------------------------------------------------------------
    reg         clk;
    reg         rst_n;
    reg         start;
    reg  [63:0] scalar_in;
    reg  [63:0] base_in;

    wire        done;
    wire [255:0] result_x;

    // 테스트를 위한 256비트 전체 데이터 (RFC 7748 테스트 벡터)
    reg [255:0] scalar_key_full;
    reg [255:0] base_x_full;
    reg [255:0] expected_result;

    // --------------------------------------------------------------------
    // 2. Unit Under Test (UUT) 인스턴스화
    // --------------------------------------------------------------------
    top_x25519 uut (
        .clk        (clk),
        .rst_n      (rst_n),
        .start      (start),
        .scalar_in  (scalar_in),
        .base_in    (base_in),
        .done       (done),
        .result_x   (result_x)
    );

    // --------------------------------------------------------------------
    // 3. 클럭 생성 (Period = 2ns, Frequency = 500MHz)
    // --------------------------------------------------------------------
    always #1 clk = ~clk; // 1ns마다 반전 -> 주기 2ns

    // --------------------------------------------------------------------
    // 4. 테스트 시나리오
    // --------------------------------------------------------------------
    integer i;

    initial begin
        // --- 초기화 ---
        clk       = 0;
        rst_n     = 0;
        start     = 0;
        scalar_in = 0;
        base_in   = 0;

        // RFC 7748 테스트 데이터 (Alice's Private Key & Bob's Public Key)
        scalar_key_full = 256'h77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a;
        base_x_full     = 256'hde9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f;
        expected_result = 256'h4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742;

        // --- 리셋 공정 (10클럭 유지) ---
        #20;
        rst_n = 1;
        #10;
        @(posedge clk);

        // --- 데이터 주입 (64-bit x 4 Cycles) ---
        $display("--------------------------------------------------");
        $display("[TB] Start Loading 256-bit Data (64-bit per cycle)");
        $display("--------------------------------------------------");
        
        // 4클럭 동안 데이터를 64비트씩 쪼개서 주입
        for (i = 0; i < 4; i = i + 1) begin
            start     <= 1; // Non-blocking으로 클럭 엣지에 맞춰 신호 인가
            scalar_in <= scalar_key_full[(3-i)*64 +: 64]; // MSB부터 주입
            base_in   <= base_x_full[(3-i)*64 +: 64];
            @(posedge clk);
        end

        // 데이터 주입 완료 후 신호 해제
        start     <= 0;
        scalar_in <= 0;
        base_in   <= 0;

        // --- 연산 완료 대기 ---
        $display("[TB] Data Loaded. Waiting for 'done' signal...");
        wait(done);
        
        // 결과 확인을 위해 약간의 지연
        #10;

        // --- 결과 검증 (Self-Checking) ---
        $display("==================================================");
        $display("X25519 Operation Completed!");
        $display("Expected : %x", expected_result);
        $display("Actual   : %x", result_x);
        
        if (result_x === expected_result) begin
            $display(">>> RESULT: [SUCCESS] Shared Secret Matched! <<<");
        end else begin
            $display(">>> RESULT: [FAILURE] Shared Secret Mismatched! <<<");
        end
        $display("==================================================");

        // 시뮬레이션 종료
        #100;
        $finish;
    end

    // --------------------------------------------------------------------
    // 5. 파형 덤프 및 모니터링
    // --------------------------------------------------------------------
    initial begin
        $dumpfile("tb_x25519_500mhz.vcd");
        $dumpvars(0, tb_top_x25519);
        
        // 시간 흐름 모니터링 (디버깅용)
        $monitor("Time: %t | State: %d | Done: %b", $time, uut.state, done);
    end

endmodule
