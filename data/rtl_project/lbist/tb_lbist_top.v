// tb_lbist_top.v
// Self-checking testbench for the integrated top module. No external
// stimulus is needed (MISR response is looped back from PRPG inside
// lbist_top), so this just free-runs the DUT and compares its internal
// signature / current_T / stalled streams against a Python "shadow model"
// that runs the exact same PRPG -> MISR -> HD -> AdaptiveTController flow
// (see tb/gen_reference_vectors.py: gen_top_ref()).

`timescale 1ns/1ps

module tb_lbist_top;
    localparam WIDTH  = 63;   // 16의 배수 아님 - gen_reference_vectors.py의 TOP_WIDTH와 동일 이유로 맞춤
    localparam N      = 600;
    localparam T_WIDTH = 11;

    reg clk = 0;
    reg rst_n;
    reg enable;
    wire [WIDTH-1:0] pattern;
    wire [15:0] signature;
    wire [T_WIDTH-1:0] current_T;
    wire stalled;

    lbist_top #(.WIDTH(WIDTH)) dut (
        .clk(clk), .rst_n(rst_n), .enable(enable),
        .pattern(pattern), .signature(signature),
        .current_T(current_T), .stalled(stalled)
    );

    always #5 clk = ~clk;

    reg [15:0] expected_sig [0:N-1];
    reg [11:0] expected_T   [0:N-1];
    reg [3:0]  expected_st  [0:N-1];
    integer i;
    integer errors_sig, errors_T, errors_st;
    integer transitions_seen;

    initial begin
        $readmemh("tb/vectors/top_expected_sig.hex", expected_sig);
        $readmemh("tb/vectors/top_expected_T.hex", expected_T);
        $readmemh("tb/vectors/top_expected_stalled.hex", expected_st);

        rst_n = 0; enable = 0;
        @(posedge clk); @(posedge clk);
        @(negedge clk);
        rst_n = 1;
        @(negedge clk);
        enable = 1;   // negedge에서 세팅 후 계속 high (레이스/phantom 사이클 방지)

        errors_sig = 0; errors_T = 0; errors_st = 0; transitions_seen = 0;
        for (i = 0; i < N; i = i + 1) begin
            @(posedge clk);
            #1;
            if (signature !== expected_sig[i]) begin
                errors_sig = errors_sig + 1;
                if (errors_sig <= 10)
                    $display("[tb_top] SIG MISMATCH cycle %0d: got=%h expected=%h", i, signature, expected_sig[i]);
            end
            if (current_T !== expected_T[i][T_WIDTH-1:0]) begin
                errors_T = errors_T + 1;
                if (errors_T <= 10)
                    $display("[tb_top] T MISMATCH cycle %0d: got=%0d expected=%0d", i, current_T, expected_T[i]);
            end
            if (stalled !== expected_st[i][0]) begin
                errors_st = errors_st + 1;
                if (errors_st <= 10)
                    $display("[tb_top] stalled MISMATCH cycle %0d: got=%0d expected=%0d", i, stalled, expected_st[i][0]);
            end
            if (stalled)
                transitions_seen = transitions_seen + 1;
        end
        enable = 0;

        $display("[tb_top] observed %0d T-transitions, final current_T=%0d, final signature=%h",
                  transitions_seen, current_T, signature);

        if (errors_sig == 0 && errors_T == 0 && errors_st == 0)
            $display("[tb_top] PASS: %0d cycles matched Python end-to-end reference", N);
        else
            $display("[tb_top] FAIL: sig=%0d T=%0d stalled=%0d mismatches", errors_sig, errors_T, errors_st);
        $finish;
    end
endmodule
