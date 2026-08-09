// tb_adaptive_controller.v
// Self-checking testbench: tb/vectors/ctrl_hd.hex 시퀀스를 그대로
// adaptive_controller에 주입하고, 매 사이클 current_T/stalled를
// AdaptiveTController(Python, 동일 파라미터/동일 hd 시퀀스)의 기대값과 비교한다.
// (파라미터는 모듈 기본값 = Optuna 최적값을 그대로 사용)

`timescale 1ns/1ps

module tb_adaptive_controller;
    localparam N = 600;
    localparam MISR_WIDTH = 16;
    localparam HD_WIDTH = 5;
    localparam T_MAX = 1024;
    localparam T_WIDTH = 11;

    reg clk = 0;
    reg rst_n;
    reg update;
    reg [HD_WIDTH-1:0] hd;
    wire [T_WIDTH-1:0] current_T;
    wire stalled;

    adaptive_controller dut (
        .clk(clk), .rst_n(rst_n), .update(update),
        .hd(hd), .current_T(current_T), .stalled(stalled)
    );

    always #5 clk = ~clk;

    reg [7:0] hd_seq       [0:N-1];   // ctrl_hd.hex: 2 hex digits/line
    reg [11:0] expected_T   [0:N-1];  // ctrl_expected_T.hex: 3 hex digits/line
    reg [3:0]  expected_st  [0:N-1];  // ctrl_expected_stalled.hex: 1 hex digit/line
    integer i;
    integer errors_T, errors_st;
    integer transitions_seen;

    initial begin
        $readmemh("tb/vectors/ctrl_hd.hex", hd_seq);
        $readmemh("tb/vectors/ctrl_expected_T.hex", expected_T);
        $readmemh("tb/vectors/ctrl_expected_stalled.hex", expected_st);

        rst_n = 0; update = 0; hd = 0;
        @(posedge clk); @(posedge clk);
        @(negedge clk);
        rst_n = 1;

        errors_T = 0; errors_st = 0; transitions_seen = 0;
        for (i = 0; i < N; i = i + 1) begin
            @(negedge clk);
            hd = hd_seq[i][HD_WIDTH-1:0];
            update = 1;   // hd와 같은 negedge에서 세팅 (phantom 사이클 방지)
            @(posedge clk);
            #1;
            if (current_T !== expected_T[i][T_WIDTH-1:0]) begin
                errors_T = errors_T + 1;
                if (errors_T <= 10)
                    $display("[tb_ctrl] T MISMATCH cycle %0d: got=%0d expected=%0d",
                              i, current_T, expected_T[i]);
            end
            if (stalled !== expected_st[i][0]) begin
                errors_st = errors_st + 1;
                if (errors_st <= 10)
                    $display("[tb_ctrl] stalled MISMATCH cycle %0d: got=%0d expected=%0d",
                              i, stalled, expected_st[i][0]);
            end
            if (stalled)
                transitions_seen = transitions_seen + 1;
        end

        $display("[tb_ctrl] observed %0d T-transitions, final current_T=%0d", transitions_seen, current_T);

        if (errors_T == 0 && errors_st == 0)
            $display("[tb_ctrl] PASS: %0d cycles matched Python AdaptiveTController reference", N);
        else
            $display("[tb_ctrl] FAIL: T mismatches=%0d, stalled mismatches=%0d", errors_T, errors_st);
        $finish;
    end
endmodule
