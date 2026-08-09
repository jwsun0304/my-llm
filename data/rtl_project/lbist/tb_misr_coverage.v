// tb_misr_coverage.v
// -------------------
// rtl/misr.v를 위한 커버리지 주도 검증 루프.
//
// Icarus Verilog는 SystemVerilog covergroup/coverpoint 구문을 지원하지
// 않는다 (-g2012로도 syntax error로 확인됨 - tb/probe_covergroup.sv로
// 사전 테스트). 그래서 카운터/플래그 기반 수동 커버리지 트래킹으로 대체.
//
// 커버포인트:
//   cp_resp_all_zero   : response == 0 이 한 번이라도 적용됨
//   cp_resp_all_one    : response == all-1 이 한 번이라도 적용됨
//   cp_sig_lsb_0/1     : misr 내부 signature 레지스터의 lsb(=shift 분기
//                        결정 비트)가 0/1인 상태에서 update가 한 번이라도 일어남
//   cp_fold_channel[k] : fold의 16개 채널(k=0..15) 각각에, 그 채널로 XOR-in
//                        되는 response 비트 중 최소 하나가 1인 적이 있음
//   cp_rst_mid_enable  : enable=1로 동작 중에 rst_n이 걸리는(우선순위) 케이스
//
// 기존 self-checking 비교(Python MISR 레퍼런스와 시그니처 bit-exact 일치)는
// 그대로 유지한 채 커버리지 샘플링만 얹었다.
//
// 자극은 tb/gen_misr_coverage_stimulus.py가 생성하는
// tb/vectors/misr_cov_stimulus.hex / misr_cov_expected.hex 를 쓴다
// (기존 tb_misr.v/misr_stimulus.hex 단위테스트는 별도로 그대로 둔다).

`timescale 1ns/1ps

module tb_misr_coverage;
    localparam NUM_INPUTS = 228;
    localparam N          = 305;   // gen_misr_coverage_stimulus.py 출력 N과 동기화 필요
    localparam RESET_AT_INDEX = 302;   // 위 스크립트의 reset_at_index와 동기화 필요 (-1: 없음)

    reg clk = 0;
    reg rst_n;
    reg enable;
    reg [NUM_INPUTS-1:0] response;
    wire [15:0] signature;
    wire [15:0] next_signature;

    misr #(.NUM_INPUTS(NUM_INPUTS)) dut (
        .clk(clk), .rst_n(rst_n), .enable(enable),
        .response(response), .signature(signature), .next_signature(next_signature)
    );

    always #5 clk = ~clk;

    reg [NUM_INPUTS-1:0] stim     [0:N-1];
    reg [15:0]           expected [0:N-1];
    integer i, k;
    integer errors;

    // ---- 커버리지 상태 ----
    reg cp_resp_all_zero, cp_resp_all_one;
    reg cp_sig_lsb_0, cp_sig_lsb_1;
    reg [15:0] cp_fold_channel;
    reg cp_rst_mid_enable;

    task sample_coverage;
        integer b;
        begin
            if (response == {NUM_INPUTS{1'b0}}) cp_resp_all_zero = 1'b1;
            if (response == {NUM_INPUTS{1'b1}}) cp_resp_all_one  = 1'b1;
            for (b = 0; b < NUM_INPUTS; b = b + 1)
                if (response[b]) cp_fold_channel[b % 16] = 1'b1;
            if (dut.signature[0]) cp_sig_lsb_1 = 1'b1;
            else                  cp_sig_lsb_0 = 1'b1;
        end
    endtask

    task report_coverage;
        integer hit_count;
        begin
            hit_count = 0;
            $display("");
            $display("=== Coverage Report ===");
            $display("cp_resp_all_zero    : %s", cp_resp_all_zero ? "HIT" : "MISS");
            $display("cp_resp_all_one     : %s", cp_resp_all_one  ? "HIT" : "MISS");
            $display("cp_sig_lsb_0        : %s", cp_sig_lsb_0     ? "HIT" : "MISS");
            $display("cp_sig_lsb_1        : %s", cp_sig_lsb_1     ? "HIT" : "MISS");
            for (k = 0; k < 16; k = k + 1) begin
                $display("cp_fold_channel[%0d]%s: %s", k, (k < 10) ? " " : "", cp_fold_channel[k] ? "HIT" : "MISS");
                if (cp_fold_channel[k]) hit_count = hit_count + 1;
            end
            $display("cp_rst_mid_enable   : %s", cp_rst_mid_enable ? "HIT" : "MISS");
            $display("fold channels hit: %0d/16", hit_count);
        end
    endtask

    initial begin
        $readmemh("tb/vectors/misr_cov_stimulus.hex", stim);
        $readmemh("tb/vectors/misr_cov_expected.hex", expected);

        cp_resp_all_zero = 1'b0; cp_resp_all_one = 1'b0;
        cp_sig_lsb_0 = 1'b0; cp_sig_lsb_1 = 1'b0;
        cp_fold_channel = 16'b0; cp_rst_mid_enable = 1'b0;

        rst_n = 0; enable = 0; response = {NUM_INPUTS{1'b0}};
        @(posedge clk); @(posedge clk);
        @(negedge clk);
        rst_n = 1;

        errors = 0;
        for (i = 0; i < N; i = i + 1) begin
            @(negedge clk);
            response = stim[i];
            enable = 1;
            if (i == RESET_AT_INDEX) begin
                // cp_rst_mid_enable: enable=1로 동작 중인데 rst_n이 겹쳐 걸리는 케이스.
                // misr.v는 `if(!rst_n) signature<=0; else if(enable) ...`라 rst_n이
                // enable보다 우선해야 한다 - 이 사이클의 기대값은 0 (gen_misr_coverage_
                // stimulus.py의 compute_expected와 동일한 시나리오).
                rst_n = 1'b0;
                cp_rst_mid_enable = 1'b1;
            end
            sample_coverage;   // 이번 엣지에서 실제 쓰일 response/signature[0] 기준
            @(posedge clk);
            #1;
            if (i == RESET_AT_INDEX)
                rst_n = 1'b1;   // 다음 사이클부터는 정상 동작 재개
            if (signature !== expected[i]) begin
                errors = errors + 1;
                if (errors <= 5)
                    $display("[tb_misr_cov] MISMATCH cycle %0d: got=%h expected=%h",
                              i, signature, expected[i]);
            end
        end
        enable = 0;

        if (errors == 0)
            $display("[tb_misr_cov] SELF-CHECK PASS: %0d cycles matched Python reference", N);
        else
            $display("[tb_misr_cov] SELF-CHECK FAIL: %0d/%0d cycles mismatched", errors, N);

        report_coverage;
        $finish;
    end
endmodule
