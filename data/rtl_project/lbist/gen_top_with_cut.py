#!/usr/bin/env python3
"""
gen_top_with_cut.py
---------------------
lbist_top.v(PRPG->MISR 루프백, CUT 없음)과 나란히 두는 실제-CUT 버전을
생성한다. s1494_cut.v(gen_cut_verilog.py가 만든 gate-level netlist)의
포트가 n<line> 형태로 개별 이름을 갖고 있어서, PRPG의 pattern[13:0]
버스 / MISR의 response[24:0] 버스와 올바른 순서(circuit.inputs /
circuit.outputs 순서 그대로)로 연결하는 배선을 실수 없이 만들기 위해
Python으로 생성한다.

기존 lbist_top.v는 건드리지 않는다 - 새 파일만 만든다.

사용법:
    python rtl/gen_top_with_cut.py benchmarks/s1494.bench s1494 rtl/lbist_top_with_cut.v
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bench_parser import parse_bench


def sig(line):
    return f"n{line}"


def generate(circuit, module_name, cut_module_name):
    ni, no = circuit.num_inputs, circuit.num_outputs
    lines = []
    lines.append(f"// lbist_top_with_cut.v")
    lines.append(f"// gen_top_with_cut.py로 자동 생성. {cut_module_name}(={module_name}.bench, "
                  f"inputs={ni}, outputs={no})를 실제 CUT으로 MISR에 물린 버전.")
    lines.append("// lbist_top.v(루프백, CUT 없음)는 그대로 보존하고 이 파일만 추가된 것.")
    lines.append("//")
    lines.append("// 매 enable 사이클: prpg가 pattern[NUM_INPUTS-1:0] 생성 -> CUT의 각 입력핀에")
    lines.append("// (bench 파일에 등장한 순서 그대로) 연결 -> CUT의 각 출력핀을 (역시 등장 순서")
    lines.append("// 그대로) response[NUM_OUTPUTS-1:0]로 모아 MISR에 입력 -> HD 계산 ->")
    lines.append("// adaptive_controller.update(). experiment.py의 한 패턴 루프와 동일한 순서.")
    lines.append("")
    lines.append("module lbist_top_with_cut #(")
    lines.append("    parameter [15:0] SEED       = 16'hACE1,")
    lines.append("    parameter T_INIT            = 33,")
    lines.append("    parameter T_MAX              = 1024,")
    lines.append("    parameter DELTA_T            = 193,")
    lines.append("    parameter K                  = 3,")
    lines.append("    parameter W                  = 34,")
    lines.append("    parameter CALIB_PATTERNS     = 72,")
    lines.append("    parameter ALPHA_FRAC_BITS    = 24,")
    lines.append("    parameter ALPHA_FIXED        = 14111141")
    lines.append(")(")
    lines.append("    input  wire                            clk,")
    lines.append("    input  wire                            rst_n,")
    lines.append("    input  wire                            enable,")
    lines.append(f"    output reg  [{ni - 1}:0]                     pattern,   // 등록본(관측용)")
    lines.append(f"    output reg  [{no - 1}:0]                     response,  // 등록본(관측용)")
    lines.append("    output wire [15:0]                     signature,")
    lines.append("    output wire [$clog2(T_MAX + 1) - 1:0]  current_T,")
    lines.append("    output wire                            stalled")
    lines.append(");")
    lines.append("")

    # CUT 입출력 핀에 대응하는 개별 wire 선언 (포트 이름과 동일하게 n<line>)
    lines.append("    // CUT(게이트레벨 netlist)의 개별 핀 wire - 이름은 bench 라인 번호 그대로")
    io_lines = list(circuit.inputs) + list(circuit.outputs)
    chunk = 8
    for i in range(0, len(io_lines), chunk):
        group = io_lines[i:i + chunk]
        lines.append("    wire " + ", ".join(sig(l) for l in group) + ";")
    lines.append("")

    lines.append("    wire [15:0] next_signature;")
    lines.append(f"    wire [{ni - 1}:0] next_pattern;")
    lines.append(f"    wire [{no - 1}:0] response_live;   // CUT 출력을 모은 조합 버스 (misr이 same-edge로 소비)")
    lines.append("")

    lines.append(f"    prpg #(.NUM_BITS({ni}), .SEED(SEED)) u_prpg (")
    lines.append("        .clk          (clk),")
    lines.append("        .rst_n        (rst_n),")
    lines.append("        .enable       (enable),")
    lines.append("        .pattern      (),")
    lines.append("        .next_pattern (next_pattern),")
    lines.append("        .lfsr_state   ()")
    lines.append("    );")
    lines.append("")
    lines.append("    // CUT/MISR은 same-edge 시야를 위해 next_pattern/response_live(조합, 계속")
    lines.append("    // 바뀜)을 직접 쓴다. 반면 top의 pattern/response 출력은 이 값이 '패턴 P에")
    lines.append("    // 대한 결과'로 안정적으로 유지돼야(=레지스터여야) 외부에서 post-edge에")
    lines.append("    // 샘플링해도 어긋나지 않는다 - live wire를 그대로 노출하면 이 엣지가")
    lines.append("    // 지나가자마자 '다음 패턴'의 미리보기 값으로 계속 바뀌어버린다.")
    lines.append("    always @(posedge clk or negedge rst_n) begin")
    lines.append("        if (!rst_n) begin")
    lines.append(f"            pattern  <= {{{ni}{{1'b0}}}};")
    lines.append(f"            response <= {{{no}{{1'b0}}}};")
    lines.append("        end else if (enable) begin")
    lines.append("            pattern  <= next_pattern;")
    lines.append("            response <= response_live;")
    lines.append("        end")
    lines.append("    end")
    lines.append("")

    # pattern 버스 -> CUT 입력핀 (circuit.inputs 순서 = pattern[j]가 j번째 입력)
    for j, l in enumerate(circuit.inputs):
        lines.append(f"    assign {sig(l)} = next_pattern[{j}];")
    lines.append("")

    # CUT 인스턴스 (named port connection, 이름이 곧 wire 이름과 같아 .n<L>(n<L>) 형태)
    lines.append(f"    {cut_module_name} u_cut (")
    port_conns = [f".{sig(l)}({sig(l)})" for l in io_lines]
    lines.append("        " + ",\n        ".join(port_conns))
    lines.append("    );")
    lines.append("")

    # CUT 출력핀 -> response_live 버스 (circuit.outputs 순서 = response_live[i]가 i번째 출력)
    for i, l in enumerate(circuit.outputs):
        lines.append(f"    assign response_live[{i}] = {sig(l)};")
    lines.append("")

    lines.append(f"    misr #(.NUM_INPUTS({no})) u_misr (")
    lines.append("        .clk            (clk),")
    lines.append("        .rst_n          (rst_n),")
    lines.append("        .enable         (enable),")
    lines.append("        .response       (response_live),")
    lines.append("        .signature      (signature),")
    lines.append("        .next_signature (next_signature)")
    lines.append("    );")
    lines.append("")

    lines.append("    function [4:0] popcount16;")
    lines.append("        input [15:0] v;")
    lines.append("        integer b;")
    lines.append("        begin")
    lines.append("            popcount16 = 5'd0;")
    lines.append("            for (b = 0; b < 16; b = b + 1)")
    lines.append("                popcount16 = popcount16 + v[b];")
    lines.append("        end")
    lines.append("    endfunction")
    lines.append("")
    lines.append("    reg primed;")
    lines.append("    always @(posedge clk or negedge rst_n) begin")
    lines.append("        if (!rst_n) primed <= 1'b0;")
    lines.append("        else if (enable) primed <= 1'b1;")
    lines.append("    end")
    lines.append("")
    lines.append("    wire [4:0] hd_raw = popcount16(next_signature ^ signature);")
    lines.append("    wire [4:0] hd     = primed ? hd_raw : 5'd0;")
    lines.append("")

    lines.append("    adaptive_controller #(")
    lines.append("        .T_INIT         (T_INIT),")
    lines.append("        .T_MAX          (T_MAX),")
    lines.append("        .DELTA_T        (DELTA_T),")
    lines.append("        .K              (K),")
    lines.append("        .W              (W),")
    lines.append("        .CALIB_PATTERNS (CALIB_PATTERNS),")
    lines.append("        .MISR_WIDTH     (16),")
    lines.append("        .ALPHA_FRAC_BITS(ALPHA_FRAC_BITS),")
    lines.append("        .ALPHA_FIXED    (ALPHA_FIXED)")
    lines.append("    ) u_ctrl (")
    lines.append("        .clk        (clk),")
    lines.append("        .rst_n      (rst_n),")
    lines.append("        .update     (enable),")
    lines.append("        .hd         (hd),")
    lines.append("        .current_T  (current_T),")
    lines.append("        .stalled    (stalled)")
    lines.append("    );")
    lines.append("")
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bench_path")
    ap.add_argument("cut_module_base")   # e.g. "s1494" -> CUT module is s1494_cut
    ap.add_argument("out_path")
    args = ap.parse_args()

    circuit = parse_bench(args.bench_path)
    verilog = generate(circuit, args.cut_module_base, f"{args.cut_module_base}_cut")
    with open(args.out_path, "w", encoding="utf-8") as f:
        f.write(verilog)
    print(f"[gen_top_with_cut] {args.bench_path} -> {args.out_path}")
    print(f"  {circuit.summary()}")


if __name__ == "__main__":
    main()
