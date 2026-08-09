// tb_misr.v
// Self-checking testbench: tb/vectors/misr_stimulus.hex 를 response로 주입하고
// 매 사이클 signature를 misr_expected.hex(Python MISR로 생성)와 비교한다.

`timescale 1ns/1ps

module tb_misr;
    localparam NUM_INPUTS = 228;
    localparam N          = 300;

    reg clk = 0;
    reg rst_n;
    reg enable;
    reg [NUM_INPUTS-1:0] response;
    wire [15:0] signature;
    wire [15:0] next_signature;

    misr #(.NUM_INPUTS(NUM_INPUTS)) dut (
        .clk(clk), .rst_n(rst_n), .enable(enable),
        .response(response),
        .signature(signature), .next_signature(next_signature)
    );

    always #5 clk = ~clk;

    reg [NUM_INPUTS-1:0] stim     [0:N-1];
    reg [15:0]           expected [0:N-1];
    integer i;
    integer errors;

    initial begin
        $readmemh("tb/vectors/misr_stimulus.hex", stim);
        $readmemh("tb/vectors/misr_expected.hex", expected);

        rst_n = 0; enable = 0; response = {NUM_INPUTS{1'b0}};
        @(posedge clk); @(posedge clk);
        @(negedge clk);
        rst_n = 1;

        errors = 0;
        for (i = 0; i < N; i = i + 1) begin
            @(negedge clk);
            response = stim[i];
            enable = 1;   // response와 같은 negedge에서 세팅: enable=1이 먼저 걸린 채
                           // 낡은(stale) response로 posedge를 맞는 phantom 사이클 방지
            @(posedge clk);
            #1;
            if (signature !== expected[i]) begin
                errors = errors + 1;
                if (errors <= 5)
                    $display("[tb_misr] MISMATCH cycle %0d: got=%h expected=%h", i, signature, expected[i]);
            end
        end
        enable = 0;

        if (errors == 0)
            $display("[tb_misr] PASS: %0d cycles matched Python reference", N);
        else
            $display("[tb_misr] FAIL: %0d/%0d cycles mismatched", errors, N);
        $finish;
    end
endmodule
