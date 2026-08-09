#!/usr/bin/env python3
"""
gen_cut_verilog.py
-------------------
src/bench_parser.py로 ISCAS'89 .bench 넷리스트를 파싱해서, 합성 가능한
gate-level Verilog 모듈로 그대로 옮긴다 (게이트 하나하나를 Verilog
내장 primitive(and/or/nand/nor/not/buf/xor/xnor)로 인스턴스화 — 별도
논리 최적화나 매핑 없이 원본 넷리스트 구조를 1:1로 보존한다).

신호선 번호 N은 Verilog 식별자 규칙(숫자로 시작 불가)을 지키기 위해
n<N> 으로 이름 붙인다. src/fault_sim.py의 _eval_gate()가 지원하는
게이트 타입(AND/NAND/OR/NOR/NOT/BUFF/XOR/XNOR)과 정확히 동일한
의미로 매핑한다.

사용법:
    python rtl/gen_cut_verilog.py benchmarks/s1494.bench rtl/s1494_cut.v s1494
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bench_parser import parse_bench

GATE_PRIM = {
    "AND": "and", "NAND": "nand",
    "OR": "or", "NOR": "nor",
    "NOT": "not", "BUFF": "buf", "BUF": "buf",
    "XOR": "xor", "XNOR": "xnor",
}

# 실험적으로 확인된 이유로 built-in gate primitive(and/or/not 등) 대신
# assign 기반 boolean 연산식을 쓴다: 수백 단 길이의 primitive 체인을
# prpg(순차 레지스터)->misr(순차 레지스터) 사이 순수 조합 경로에 두면,
# 같은 클록 엣지 안에서 misr이 완전히 settle되지 않은 중간값을 캡처하는
# 것으로 보이는 시뮬레이션 딜타사이클 이슈가 재현됐다(단독 misr 테스트는
# 정상, 647-게이트 CUT을 통과시키면 신호가 어긋남). assign 연산자
# 기반으로 바꾸니 문제가 사라져 이 방식을 기본으로 채택했다.
GATE_EXPR = {
    "AND": lambda args: " & ".join(args),
    "NAND": lambda args: "~(" + " & ".join(args) + ")",
    "OR": lambda args: " | ".join(args),
    "NOR": lambda args: "~(" + " | ".join(args) + ")",
    "NOT": lambda args: "~" + args[0],
    "BUFF": lambda args: args[0],
    "BUF": lambda args: args[0],
    "XOR": lambda args: " ^ ".join(args),
    "XNOR": lambda args: "~(" + " ^ ".join(args) + ")",
}


def sig(line):
    return f"n{line}"


def to_verilog(circuit, module_name):
    output_set = set(circuit.outputs)
    lines = []

    lines.append(f"// {module_name}_cut.v")
    lines.append(f"// gen_cut_verilog.py로 {module_name}.bench에서 자동 생성 "
                  f"(inputs={circuit.num_inputs}, outputs={circuit.num_outputs}, "
                  f"gates={circuit.num_gates}). 게이트 구조를 그대로 옮긴 gate-level netlist.")
    lines.append(f"module {module_name}_cut (")
    port_list = [sig(i) for i in circuit.inputs] + [sig(o) for o in circuit.outputs]
    lines.append("    " + ",\n    ".join(port_list))
    lines.append(");")
    lines.append("")

    for i in circuit.inputs:
        lines.append(f"    input  {sig(i)};")
    for o in circuit.outputs:
        lines.append(f"    output {sig(o)};")
    lines.append("")

    internal = [l for l in circuit.order if l not in output_set]
    if internal:
        # 한 줄에 다 몰아넣으면 매우 길어지니 8개씩 끊어서 wire 선언
        chunk = 8
        for i in range(0, len(internal), chunk):
            group = internal[i:i + chunk]
            lines.append("    wire " + ", ".join(sig(l) for l in group) + ";")
    lines.append("")

    for idx, line in enumerate(circuit.order):
        gtype, fanins = circuit.gates[line]
        if gtype not in GATE_EXPR:
            raise ValueError(f"Unsupported gate type for Verilog mapping: {gtype} (line {line})")
        args = [sig(f) for f in fanins]
        expr = GATE_EXPR[gtype](args)
        lines.append(f"    assign {sig(line)} = {expr};")

    lines.append("")
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bench_path")
    ap.add_argument("out_path")
    ap.add_argument("module_name")
    args = ap.parse_args()

    circuit = parse_bench(args.bench_path)
    verilog = to_verilog(circuit, args.module_name)
    with open(args.out_path, "w", encoding="utf-8") as f:
        f.write(verilog)
    print(f"[gen_cut_verilog] {args.bench_path} -> {args.out_path}")
    print(f"  {circuit.summary()}")


if __name__ == "__main__":
    main()
