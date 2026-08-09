#!/usr/bin/env python3
"""
run_experiment.py
------------------
Fixed-T(256), Fixed-T(1024), Adaptive-T 세 조건을 s5378 벤치마크에서
비교 실행하고, 논문 그림3/표2/표3에 대응하는 결과(coverage curve,
주요 지표 표, TAT 비교 표)를 results/ 에 저장한다.

사용법:
    python3 run_experiment.py --patterns 6000
    python3 run_experiment.py --patterns 30000   # 논문과 동일 규모 (약 2~3분 소요)
"""

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from experiment import LBISTExperiment
from adaptive_controller import FixedTController, AdaptiveTController

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default="benchmarks/s5378.bench")
    ap.add_argument("--patterns", type=int, default=6000,
                     help="총 인가 패턴(사이클) 수. 논문은 30000 사용.")
    ap.add_argument("--record-every", type=int, default=25)
    ap.add_argument("--seed", type=lambda x: int(x, 0), default=0xACE1)
    ap.add_argument("--outdir", default="results")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    exp = LBISTExperiment(args.bench, seed=args.seed, verbose=True)

    print("\n=== Fixed-T(T=256) ===")
    res_256 = exp.run(FixedTController(T=256), args.patterns, args.record_every)

    print("\n=== Fixed-T(T=1024) ===")
    res_1024 = exp.run(FixedTController(T=1024), args.patterns, args.record_every)

    print("\n=== Adaptive-T (T_INIT=128 -> T_MAX=1024) ===")
    res_adapt = exp.run(
        AdaptiveTController(T_init=128, T_max=1024, delta_T=128, K=3, W=16, alpha=0.95),
        args.patterns, args.record_every
    )

    # ---------------- 그림 3 재현: coverage curve 비교 ----------------
    plt.figure(figsize=(8, 5))
    plt.plot(res_256["pattern_idx"], res_256["coverage"], "--", label="Fixed-T (T=256)")
    plt.plot(res_1024["pattern_idx"], res_1024["coverage"], "--", label="Fixed-T (T=1024)")
    plt.plot(res_adapt["pattern_idx"], res_adapt["coverage"], "-", linewidth=2,
              label="Adaptive-T", color="tab:orange")
    for (p, oldT, newT) in res_adapt["transitions"]:
        plt.axvline(p, color="tab:orange", alpha=0.2, linestyle=":")
    plt.xlabel("Test Patterns")
    plt.ylabel("Fault Coverage (%)")
    plt.title(f"Fault Coverage Comparison (s5378, N={args.patterns})")
    plt.legend()
    plt.grid(alpha=0.3)
    fig_path = os.path.join(args.outdir, "coverage_comparison.png")
    plt.savefig(fig_path, dpi=150, bbox_inches="tight")
    print(f"\n[saved] {fig_path}")

    # ---------------- 그림 4 재현: T 전환 이력 ----------------
    plt.figure(figsize=(8, 3))
    plt.step(res_adapt["pattern_idx"], res_adapt["T_history"], where="post", color="tab:blue")
    for (p, oldT, newT) in res_adapt["transitions"]:
        plt.axvline(p, color="red", alpha=0.3, linestyle=":")
    plt.xlabel("Test Patterns")
    plt.ylabel("current_T")
    plt.title("Adaptive-T: T-period Evolution")
    plt.grid(alpha=0.3)
    fig_path2 = os.path.join(args.outdir, "adaptive_T_evolution.png")
    plt.savefig(fig_path2, dpi=150, bbox_inches="tight")
    print(f"[saved] {fig_path2}")

    # ---------------- 표 2: 주요 지표 비교 ----------------
    table2_path = os.path.join(args.outdir, "table2_main_metrics.csv")
    with open(table2_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Parameter", "Fixed-T(T=256)", "Fixed-T(T=1024)", "Adaptive-T"])
        w.writerow(["Final coverage (%)",
                    f"{res_256['final_coverage']:.3f}",
                    f"{res_1024['final_coverage']:.3f}",
                    f"{res_adapt['final_coverage']:.3f}"])
        w.writerow(["Detected faults",
                    res_256["detected_faults"], res_1024["detected_faults"], res_adapt["detected_faults"]])
        w.writerow(["Total faults", res_256["total_faults"], res_1024["total_faults"], res_adapt["total_faults"]])
        w.writerow(["T transitions", 0, 0, len(res_adapt["transitions"])])
        w.writerow(["Elapsed sec",
                    f"{res_256['elapsed_sec']:.1f}", f"{res_1024['elapsed_sec']:.1f}", f"{res_adapt['elapsed_sec']:.1f}"])
    print(f"[saved] {table2_path}")

    # ---------------- 표 3: TAT(목표 커버리지 도달 패턴 수) 비교 ----------------
    target = res_256["final_coverage"]  # Fixed-T(256) 최종 커버리지를 목표로 설정 (논문과 동일한 방식)
    p256 = exp.patterns_to_reach(res_256, target)
    p1024 = exp.patterns_to_reach(res_1024, target)
    padapt = exp.patterns_to_reach(res_adapt, target)

    table3_path = os.path.join(args.outdir, "table3_tat_comparison.csv")
    with open(table3_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Condition", "# patterns to reach target", "Change vs Fixed-T(256) (%)"])
        base = p256 if p256 else args.patterns
        for name, p in [("Fixed-T(T=256)", p256), ("Fixed-T(T=1024)", p1024), ("Adaptive-T", padapt)]:
            if p is None:
                w.writerow([name, f"not reached within {args.patterns}", "-"])
            else:
                change = (p - base) / base * 100.0
                w.writerow([name, p, f"{change:+.2f}"])
    print(f"[saved] {table3_path}")

    # ---------------- raw 커버리지 로그 저장 (재plot/분석용) ----------------
    for name, res in [("fixed256", res_256), ("fixed1024", res_1024), ("adaptive", res_adapt)]:
        raw_path = os.path.join(args.outdir, f"coverage_log_{name}.csv")
        with open(raw_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["pattern", "coverage_percent", "current_T", "misr_hd"])
            for p, c, t, hd in zip(res["pattern_idx"], res["coverage"], res["T_history"], res["hd_history"]):
                w.writerow([p, f"{c:.4f}", t, hd])

    print("\n=== Summary ===")
    print(f"Target coverage (Fixed-T256 final) = {target:.3f}%")
    print(f"  Fixed-T(256)  reaches it at pattern {p256}")
    print(f"  Fixed-T(1024) reaches it at pattern {p1024}")
    print(f"  Adaptive-T    reaches it at pattern {padapt}")
    print(f"Adaptive-T transitions: {res_adapt['transitions']}")


if __name__ == "__main__":
    main()
