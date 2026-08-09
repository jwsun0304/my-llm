// tb_prpg.v
// Self-checking testbench: prpg의 pattern 출력을 tb/vectors/prpg_ref.hex
// (Python PhaseShifterPRPG로 생성한 골든 레퍼런스)와 매 사이클 비교한다.

`timescale 1ns/1ps

module tb_prpg;
    localparam NUM_BITS = 214;
    localparam N        = 300;

    reg clk = 0;
    reg rst_n;
    reg enable;
    wire [NUM_BITS-1:0] pattern;
    wire [15:0] lfsr_state;

    prpg #(.NUM_BITS(NUM_BITS), .SEED(16'hACE1)) dut (
        .clk(clk), .rst_n(rst_n), .enable(enable),
        .pattern(pattern), .lfsr_state(lfsr_state)
    );

    always #5 clk = ~clk;

    reg [NUM_BITS-1:0] expected [0:N-1];
    integer i;
    integer errors;

    initial begin
        $readmemh("tb/vectors/prpg_ref.hex", expected);

        rst_n = 0; enable = 0;
        @(posedge clk); @(posedge clk);
        @(negedge clk);
        rst_n = 1;
        @(negedge clk);
        enable = 1;   // negedge에서 세팅: DUT의 posedge always 블록과 레이스 방지

        errors = 0;
        for (i = 0; i < N; i = i + 1) begin
            @(posedge clk);
            #1;
            if (pattern !== expected[i]) begin
                errors = errors + 1;
                if (errors <= 5)
                    $display("[tb_prpg] MISMATCH cycle %0d: got=%h expected=%h", i, pattern, expected[i]);
            end
        end
        enable = 0;

        if (errors == 0)
            $display("[tb_prpg] PASS: %0d cycles matched Python reference", N);
        else
            $display("[tb_prpg] FAIL: %0d/%0d cycles mismatched", errors, N);
        $finish;
    end
endmodule
