// tb_lbist_top_with_cut.v
// Self-checking testbench for lbist_top_with_cut.v + a real injected
// stuck-at fault. Instantiates the integrated top TWICE (golden / faulty)
// sharing the same PRPG seed so pattern streams are bit-identical; forces
// n446 (an internal AND-gate output inside s1494_cut, per
// tb/gen_cut_fault_vectors.py) stuck-at-0 only in the faulty instance.
//
// Checks, every cycle, against tb/vectors/cut_fault/*.hex (Python golden
// reference, itself cross-validated against src/fault_sim.py):
//   - golden/faulty CUT response vectors
//   - golden/faulty MISR signatures
//   - per-pattern "detected" flag (response vectors differ)
// and reports the first pattern where detection occurs, compared against
// the Python reference's first_detected_pattern.

`timescale 1ns/1ps

module tb_lbist_top_with_cut;
    localparam NI = 14;
    localparam NO = 25;
    localparam N  = 150;
    localparam T_WIDTH = 11;

    reg clk = 0;
    reg rst_n;
    reg enable;

    wire [NI-1:0] g_pattern, f_pattern;
    wire [NO-1:0] g_response, f_response;
    wire [15:0]   g_signature, f_signature;
    wire [T_WIDTH-1:0] g_T, f_T;
    wire g_stalled, f_stalled;

    lbist_top_with_cut golden_top (
        .clk(clk), .rst_n(rst_n), .enable(enable),
        .pattern(g_pattern), .response(g_response),
        .signature(g_signature), .current_T(g_T), .stalled(g_stalled)
    );

    lbist_top_with_cut faulty_top (
        .clk(clk), .rst_n(rst_n), .enable(enable),
        .pattern(f_pattern), .response(f_response),
        .signature(f_signature), .current_T(f_T), .stalled(f_stalled)
    );

    // 영구 stuck-at-0 결함 주입: faulty_top 내부 CUT의 n446 (AND 게이트 출력)만.
    // golden_top은 건드리지 않아 정상 동작.
    initial begin
        force faulty_top.u_cut.n446 = 1'b0;
    end

    always #5 clk = ~clk;

    reg [NO-1:0] exp_golden_resp [0:N-1];
    reg [NO-1:0] exp_faulty_resp [0:N-1];
    reg [15:0]   exp_golden_sig  [0:N-1];
    reg [15:0]   exp_faulty_sig  [0:N-1];
    reg [3:0]    exp_detected    [0:N-1];

    integer i;
    integer errors_resp_g, errors_resp_f, errors_sig_g, errors_sig_f, errors_det;
    integer first_detected_rtl;

    initial begin
        $readmemh("tb/vectors/cut_fault/golden_response.hex", exp_golden_resp);
        $readmemh("tb/vectors/cut_fault/faulty_response.hex", exp_faulty_resp);
        $readmemh("tb/vectors/cut_fault/golden_sig.hex", exp_golden_sig);
        $readmemh("tb/vectors/cut_fault/faulty_sig.hex", exp_faulty_sig);
        $readmemh("tb/vectors/cut_fault/detected.hex", exp_detected);

        rst_n = 0; enable = 0;
        @(posedge clk); @(posedge clk);
        @(negedge clk);
        rst_n = 1;
        @(negedge clk);
        enable = 1;

        errors_resp_g = 0; errors_resp_f = 0; errors_sig_g = 0; errors_sig_f = 0; errors_det = 0;
        first_detected_rtl = -1;

        for (i = 0; i < N; i = i + 1) begin
            @(posedge clk);
            #1;

            if (g_response !== exp_golden_resp[i]) begin
                errors_resp_g = errors_resp_g + 1;
                if (errors_resp_g <= 5)
                    $display("[tb_cut] GOLDEN RESPONSE MISMATCH cycle %0d: got=%h expected=%h",
                              i, g_response, exp_golden_resp[i]);
            end
            if (f_response !== exp_faulty_resp[i]) begin
                errors_resp_f = errors_resp_f + 1;
                if (errors_resp_f <= 5)
                    $display("[tb_cut] FAULTY RESPONSE MISMATCH cycle %0d: got=%h expected=%h",
                              i, f_response, exp_faulty_resp[i]);
            end
            if (g_signature !== exp_golden_sig[i]) begin
                errors_sig_g = errors_sig_g + 1;
                if (errors_sig_g <= 5)
                    $display("[tb_cut] GOLDEN SIG MISMATCH cycle %0d: got=%h expected=%h",
                              i, g_signature, exp_golden_sig[i]);
            end
            if (f_signature !== exp_faulty_sig[i]) begin
                errors_sig_f = errors_sig_f + 1;
                if (errors_sig_f <= 5)
                    $display("[tb_cut] FAULTY SIG MISMATCH cycle %0d: got=%h expected=%h",
                              i, f_signature, exp_faulty_sig[i]);
            end

            begin : detect_check
                reg rtl_detected;
                rtl_detected = (g_response !== f_response);
                if (rtl_detected !== exp_detected[i][0]) begin
                    errors_det = errors_det + 1;
                    if (errors_det <= 5)
                        $display("[tb_cut] DETECTED-FLAG MISMATCH cycle %0d: got=%0d expected=%0d",
                                  i, rtl_detected, exp_detected[i][0]);
                end
                if (rtl_detected && first_detected_rtl == -1)
                    first_detected_rtl = i + 1;   // 1-based, Python 쪽과 동일한 기준
            end
        end
        enable = 0;

        $display("\n[tb_cut] RTL first detected at pattern (1-based): %0d", first_detected_rtl);
        $display("[tb_cut] final golden signature=%h  faulty signature=%h  %s",
                  g_signature, f_signature,
                  (g_signature !== f_signature) ? "DIFFER (fault visible in final signature)"
                                                  : "SAME (aliased)");

        if (errors_resp_g == 0 && errors_resp_f == 0 && errors_sig_g == 0 &&
            errors_sig_f == 0 && errors_det == 0 && first_detected_rtl == 50)
            $display("[tb_cut] PASS: %0d cycles matched Python golden/faulty reference (cross-checked against fault_sim.py)", N);
        else
            $display("[tb_cut] FAIL: resp_g=%0d resp_f=%0d sig_g=%0d sig_f=%0d det=%0d mismatches, first_detected_rtl=%0d (expected 50)",
                      errors_resp_g, errors_resp_f, errors_sig_g, errors_sig_f, errors_det,
                      first_detected_rtl);
        $finish;
    end
endmodule
