#!/usr/bin/env python3
"""
run_multi_circuit.py
---------------------
동일한 LBIST 파이프라인(Fixed-T256 / Fixed-T1024 / Adaptive-T)을
서로 다른 규모의 ISCAS'89 회로 여러 개에 그대로 적용해, 특정 회로
하나에만 맞춰진 결과가 아니라는 것을 확인한다.

원 논문도 "V. 결론 및 향후 연구"에서 "다양한 ISCAS'89 벤치마크 회로와
더 큰 규모의 순차 회로에 동일한 절차를 적용해 결과의 일반성을 검증할
필요가 있다"고 명시한 부분을 직접 확장한 것이다.

사용 회로 (모두 실제 ISCAS'89 공개 벤치마크):
    s1494  : 14 PI, 25 PO, 647 gates   (소형)
    s5378  : 214 PI, 228 PO, 2794 gates (본 프로젝트 기본 회로)
    s9234  : 247 PI, 250 PO, 5597 gates (중형)
    s13207 : 700 PI, 790 PO, 7951 gates (대형)

각 회로는 크기가 다르므로 --patterns 인자 하나로 통일하지 않고,
회로별로 적절한 패턴 수를 CIRCUITS 리스트에서 지정한다
(대형 회로일수록 패턴당 시뮬레이션 시간이 길어지기 때문).

Adaptive-T는 tune_adaptive.py로 s5378에서 찾은 튜닝된 파라미터
(T_init=64, delta_T=96, alpha=0.85, K=2, W=32)를 그대로 사용한다 —
"한 회로에서 찾은 파라미터가 다른 회로에서도 여전히 잘 작동하는가"
까지 함께 검증하기 위함이다.
"""

import csv
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from experiment import LBISTExperiment
from adaptive_controller import FixedTController, AdaptiveTController

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# (bench 파일, 이 회로에 사용할 패턴 수, record_every)
CIRCUITS = [
    ("s1494",  "benchmarks/s1494.bench",  6000, 100),
    ("s5378",  "benchmarks/s5378.bench",  6000, 100),
    ("s9234",  "benchmarks/s9234.bench",  3000, 100),
    ("s13207", "benchmarks/s13207.bench", 2000, 100),
]

# tune_adaptive.py가 s5378에서 찾아낸 최적 파라미터 (README 참고)
TUNED_ADAPTIVE_CFG = dict(T_init=64, T_max=1024, delta_T=96, alpha=0.85, K=2, W=32,
                           calibration_patterns=int(64 * 1.5))


def make_tuned_adaptive():
    return AdaptiveTController(**TUNED_ADAPTIVE_CFG)


def main():
    outdir = "results"
    os.makedirs(outdir, exist_ok=True)

    all_rows = []
    plot_data = {"circuit": [], "condition": [], "coverage": []}

    for name, path, num_patterns, record_every in CIRCUITS:
        print(f"\n{'='*70}\n{name}  ({num_patterns} patterns, collapsed fault model)\n{'='*70}")
        exp = LBISTExperiment(path, fault_model="collapsed", verbose=True)

        conditions = [
            ("Fixed-T(256)", FixedTController(T=256)),
            ("Fixed-T(1024)", FixedTController(T=1024)),
            ("Adaptive-T(tuned)", make_tuned_adaptive()),
        ]

        for cond_name, ctrl in conditions:
            t0 = time.time()
            res = exp.run(ctrl, num_patterns, record_every=record_every)
            elapsed = time.time() - t0
            print(f"  [{cond_name:18s}] final coverage = {res['final_coverage']:.3f}%  "
                  f"({res['detected_faults']}/{res['total_faults']} faults, {elapsed:.1f}s)")

            all_rows.append({
                "circuit": name,
                "num_inputs": exp.circuit.num_inputs,
                "num_gates": exp.circuit.num_gates,
                "num_faults_collapsed": res["total_faults"],
                "condition": cond_name,
                "num_patterns": num_patterns,
                "final_coverage": res["final_coverage"],
                "detected_faults": res["detected_faults"],
            })
            plot_data["circuit"].append(name)
            plot_data["condition"].append(cond_name)
            plot_data["coverage"].append(res["final_coverage"])

    # ---------------- CSV 저장 ----------------
    csv_path = os.path.join(outdir, "multi_circuit_results.csv")
    with open(csv_path, "w", newline="") as f:
        fieldnames = ["circuit", "num_inputs", "num_gates", "num_faults_collapsed",
                      "condition", "num_patterns", "final_coverage", "detected_faults"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in all_rows:
            w.writerow(row)
    print(f"\n[saved] {csv_path}")

    # ---------------- 그룹 막대그래프 ----------------
    circuits = [c[0] for c in CIRCUITS]
    conditions = ["Fixed-T(256)", "Fixed-T(1024)", "Adaptive-T(tuned)"]
    colors = {"Fixed-T(256)": "tab:blue", "Fixed-T(1024)": "tab:gray",
              "Adaptive-T(tuned)": "tab:red"}

    x = range(len(circuits))
    width = 0.25
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, cond in enumerate(conditions):
        vals = []
        for c in circuits:
            match = [r["final_coverage"] for r in all_rows
                     if r["circuit"] == c and r["condition"] == cond]
            vals.append(match[0] if match else 0)
        offsets = [xi + (i - 1) * width for xi in x]
        ax.bar(offsets, vals, width=width, label=cond, color=colors[cond])

    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{c}\n({[c2[2] for c2 in CIRCUITS if c2[0]==c][0]} patterns)"
                         for c in circuits])
    ax.set_ylabel("Final Fault Coverage (%)")
    ax.set_title("Cross-Circuit Generalization: Fixed-T vs Tuned Adaptive-T\n"
                  "(ISCAS'89 benchmarks, collapsed fault model)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig_path = os.path.join(outdir, "multi_circuit_comparison.png")
    plt.savefig(fig_path, dpi=150, bbox_inches="tight")
    print(f"[saved] {fig_path}")

    # ---------------- 요약 출력 ----------------
    print("\n=== Summary ===")
    for name, _, num_patterns, _ in CIRCUITS:
        rows = [r for r in all_rows if r["circuit"] == name]
        best = max(rows, key=lambda r: r["final_coverage"])
        print(f"  {name:8s} (gates={rows[0]['num_gates']:5d}, "
              f"faults={rows[0]['num_faults_collapsed']:5d}) "
              f"-> best: {best['condition']} @ {best['final_coverage']:.2f}%")


if __name__ == "__main__":
    main()
