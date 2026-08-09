#!/usr/bin/env python3
"""
gen_cut_fault_vectors.py
--------------------------
s1494 CUT에 stuck-at 결함 하나(FAULT_LINE, FAULT_SA)를 주입해서, RTL
self-checking testbench(tb_lbist_top_with_cut.v)가 쓸 golden(결함없음)
vs faulty(결함있음) 레퍼런스를 만든다.

이중 교차검증 (요청사항 5번 - fault_sim.py와 비교):
    1) 이 스크립트 안의 독립적인 scalar 게이트 평가기(eval_circuit)로
       golden/faulty 출력을 직접 계산한다. gate 평가 규칙은 src/fault_sim.py
       의 _eval_gate()/_apply_overrides()와 동일한 의미로 작성했다(같은
       AND/OR/NOT 진리표, override는 게이트 평가 "이후"에 라인 값을
       강제로 덮어씀).
    2) src/fault_sim.py의 실제 ParallelFaultSimulator에 동일한 결함
       [Fault(FAULT_LINE, FAULT_SA)] 하나를 넣고 동일한 PRPG 시퀀스로
       돌려서, 최초 검출 패턴과 최종 검출 여부가 (1)의 결과와 정확히
       일치하는지 확인한다. 다르면 AssertionError로 즉시 중단한다.
    두 경로가 일치해야만 RTL 비교용 레퍼런스로 채택한다 - "이 결과를
    Python의 fault_sim.py 결과와 비교해서 일치하는지 확인"을 레퍼런스
    생성 시점에 이미 만족시켜 놓는 것.

출력 (tb/vectors/cut_fault/):
    golden_response.hex, faulty_response.hex : 매 패턴 CUT 출력벡터(25bit)
    golden_sig.hex, faulty_sig.hex           : 매 패턴 MISR 시그니처(16bit)
    detected.hex                              : 매 패턴 "이 패턴에서 두 출력이
                                                 다른가"(fault_sim의 detection
                                                 정의와 동일), 1 hex digit
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bench_parser import parse_bench
from fault_sim import Fault, ParallelFaultSimulator
from prpg_misr import PhaseShifterPRPG, MISR

BENCH_PATH = os.path.join(os.path.dirname(__file__), "..", "benchmarks", "s1494.bench")
VECDIR = os.path.join(os.path.dirname(__file__), "vectors", "cut_fault")
SEED = 0xACE1
N = 150

FAULT_LINE = 446   # circuit.order 중간쯤의 AND 게이트 출력선 (사전 조사: 패턴 50에서 검출됨)
FAULT_SA = 0


def eval_circuit(circuit, input_bits, force_line=None, force_val=None):
    """fault_sim._eval_gate/_apply_overrides와 동일한 의미의 scalar(단일 머신) 평가."""
    values = dict(input_bits)
    for line in circuit.order:
        gtype, fanins = circuit.gates[line]
        vals = [values[f] for f in fanins]
        if gtype == "AND":
            v = 1
            for x in vals:
                v &= x
        elif gtype == "NAND":
            v = 1
            for x in vals:
                v &= x
            v = 1 - v
        elif gtype == "OR":
            v = 0
            for x in vals:
                v |= x
        elif gtype == "NOR":
            v = 0
            for x in vals:
                v |= x
            v = 1 - v
        elif gtype == "NOT":
            v = 1 - vals[0]
        elif gtype in ("BUFF", "BUF"):
            v = vals[0]
        elif gtype == "XOR":
            v = 0
            for x in vals:
                v ^= x
        elif gtype == "XNOR":
            v = 0
            for x in vals:
                v ^= x
            v = 1 - v
        else:
            raise ValueError(f"unsupported gate {gtype}")

        if force_line is not None and line == force_line:
            v = force_val
        values[line] = v
    return [values[o] for o in circuit.outputs]


def bits_to_int(bits):
    v = 0
    for i, b in enumerate(bits):
        if b:
            v |= (1 << i)
    return v


def hexdump(path, values, nibbles):
    with open(path, "w") as f:
        for v in values:
            f.write(f"{v:0{nibbles}x}\n")


def main():
    circuit = parse_bench(BENCH_PATH)
    assert FAULT_LINE in circuit.gates, f"FAULT_LINE {FAULT_LINE} must be an internal gate output"
    print(f"[circuit] {circuit.summary()}")
    print(f"[fault] line={FAULT_LINE} ({circuit.gates[FAULT_LINE]}) stuck-at-{FAULT_SA}")

    # ---- 경로 1: 이 스크립트의 독립 scalar 평가기 ----
    prpg_g = PhaseShifterPRPG(num_bits=circuit.num_inputs, seed=SEED)
    prpg_f = PhaseShifterPRPG(num_bits=circuit.num_inputs, seed=SEED)
    misr_g = MISR(num_inputs=circuit.num_outputs)
    misr_f = MISR(num_inputs=circuit.num_outputs)

    golden_resp, faulty_resp = [], []
    golden_sig, faulty_sig = [], []
    detected_flags = []
    first_detected_custom = None

    for p in range(1, N + 1):
        bits_g = prpg_g.next_pattern()
        bits_f = prpg_f.next_pattern()
        assert bits_g == bits_f, "golden/faulty PRPG streams diverged - seed mismatch bug"
        input_bits = {line: b for line, b in zip(circuit.inputs, bits_g)}

        out_g = eval_circuit(circuit, input_bits)
        out_f = eval_circuit(circuit, input_bits, force_line=FAULT_LINE, force_val=FAULT_SA)

        golden_resp.append(bits_to_int(out_g))
        faulty_resp.append(bits_to_int(out_f))
        golden_sig.append(misr_g.compress(out_g))
        faulty_sig.append(misr_f.compress(out_f))

        diff = (out_g != out_f)
        detected_flags.append(1 if diff else 0)
        if diff and first_detected_custom is None:
            first_detected_custom = p

    print(f"[custom evaluator] first detected at pattern: {first_detected_custom}")
    print(f"[custom evaluator] final golden signature={golden_sig[-1]:04x}  "
          f"faulty signature={faulty_sig[-1]:04x}  "
          f"{'DIFFER' if golden_sig[-1] != faulty_sig[-1] else 'SAME (aliased!)'}")

    # ---- 경로 2: 실제 fault_sim.py의 ParallelFaultSimulator로 교차검증 ----
    faults = [Fault(FAULT_LINE, FAULT_SA)]
    sim = ParallelFaultSimulator(circuit, faults)
    prpg_x = PhaseShifterPRPG(num_bits=circuit.num_inputs, seed=SEED)
    for p in range(1, N + 1):
        bits = prpg_x.next_pattern()
        input_bits = {line: b for line, b in zip(circuit.inputs, bits)}
        sim.simulate_pattern(input_bits)

    first_detected_faultsim = sim.first_detected_at[0]
    detected_faultsim = sim.num_detected() == 1

    print(f"[fault_sim.py]     first detected at pattern: {first_detected_faultsim}")
    print(f"[fault_sim.py]     coverage={sim.coverage()*100:.1f}% "
          f"({sim.num_detected()}/{sim.num_faults} detected)")

    # ---- 교차검증: 두 경로가 반드시 일치해야 함 ----
    assert first_detected_custom == first_detected_faultsim, (
        f"MISMATCH: custom evaluator detected at {first_detected_custom}, "
        f"fault_sim.py detected at {first_detected_faultsim}")
    assert (first_detected_custom is not None) == detected_faultsim, "detected flag mismatch"
    print("[cross-check] custom evaluator == fault_sim.py (일치 확인됨)")

    os.makedirs(VECDIR, exist_ok=True)
    resp_nibbles = (circuit.num_outputs + 3) // 4
    hexdump(os.path.join(VECDIR, "golden_response.hex"), golden_resp, resp_nibbles)
    hexdump(os.path.join(VECDIR, "faulty_response.hex"), faulty_resp, resp_nibbles)
    hexdump(os.path.join(VECDIR, "golden_sig.hex"), golden_sig, 4)
    hexdump(os.path.join(VECDIR, "faulty_sig.hex"), faulty_sig, 4)
    hexdump(os.path.join(VECDIR, "detected.hex"), detected_flags, 1)

    meta_path = os.path.join(VECDIR, "meta.txt")
    with open(meta_path, "w") as f:
        f.write(f"FAULT_LINE={FAULT_LINE}\nFAULT_SA={FAULT_SA}\nN={N}\nSEED=0x{SEED:04X}\n"
                f"NUM_INPUTS={circuit.num_inputs}\nNUM_OUTPUTS={circuit.num_outputs}\n"
                f"first_detected_pattern={first_detected_custom}\n")

    print(f"\n[saved] {VECDIR}")


if __name__ == "__main__":
    main()
