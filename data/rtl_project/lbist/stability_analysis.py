#!/usr/bin/env python3
"""
stability_analysis.py
-----------------------
동일한 조건을 여러 PRPG 시드로 반복 실행하여, 지금까지 보여드린 결과가
"우연히 잘 나온 한 번"이 아니라 안정적으로 재현되는지 통계적으로
확인한다.

원 논문 "향후 연구" 섹션의 다음 문장을 직접 구현한 것이다:
    "확률 기반 탐색의 안정성을 추가로 분석할 필요가 있다. ... 반복
    실험을 통해 평균 커버리지, 최대 커버리지, 결과 분산 및 재현성을
    함께 측정하면 성능뿐만 아니라 재현성까지 평가할 수 있다."

대상 조건 4가지 (s5378, collapsed fault model):
    - Fixed-T(256)
    - Fixed-T(1024)
    - Adaptive-T (default params)
    - Adaptive-T (tuned params, tune_adaptive.py 결과)

각 조건을 N_SEEDS개의 서로 다른 시드로 반복 실행하고,
평균 / 표준편차 / 최솟값 / 최댓값을 계산해 에러바 그래프와 표로
저장한다.
"""

import csv
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from experiment import LBISTExperiment
from adaptive_controller import FixedTController, AdaptiveTController

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

N_SEEDS = 8
NUM_PATTERNS = 5000
RECORD_EVERY = 100
BENCH = "benchmarks/s5378.bench"

TUNED_ADAPTIVE_CFG = dict(T_init=64, T_max=1024, delta_T=96, alpha=0.85, K=2, W=32,
                           calibration_patterns=int(64 * 1.5))
DEFAULT_ADAPTIVE_CFG = dict(T_init=128, T_max=1024, delta_T=128, alpha=0.95, K=3, W=16,
                             calibration_patterns=int(128 * 1.5))


def make_controller(name):
    if name == "Fixed-T(256)":
        return FixedTController(T=256)
    if name == "Fixed-T(1024)":
        return FixedTController(T=1024)
    if name == "Adaptive-T (default)":
        return AdaptiveTController(**DEFAULT_ADAPTIVE_CFG)
    if name == "Adaptive-T (tuned)":
        return AdaptiveTController(**TUNED_ADAPTIVE_CFG)
    raise ValueError(name)


def main():
    outdir = "results"
    os.makedirs(outdir, exist_ok=True)

    exp = LBISTExperiment(BENCH, fault_model="collapsed", verbose=True)
    seed_pool = [0xACE1 + i * 0x2222 for i in range(N_SEEDS)]

    conditions = ["Fixed-T(256)", "Fixed-T(1024)", "Adaptive-T (default)", "Adaptive-T (tuned)"]

    raw_rows = []
    stats = {}

    for cond in conditions:
        print(f"\n=== {cond}: {N_SEEDS} seeds x {NUM_PATTERNS} patterns ===")
        finals = []
        t0 = time.time()
        for sd in seed_pool:
            ctrl = make_controller(cond)
            res = exp.run(ctrl, NUM_PATTERNS, record_every=RECORD_EVERY, seed=sd)
            finals.append(res["final_coverage"])
            raw_rows.append({"condition": cond, "seed": hex(sd), "final_coverage": res["final_coverage"]})
        elapsed = time.time() - t0

        mean = statistics.mean(finals)
        std = statistics.pstdev(finals)
        mn, mx = min(finals), max(finals)
        stats[cond] = {"mean": mean, "std": std, "min": mn, "max": mx, "values": finals}
        print(f"  mean={mean:.3f}%  std={std:.3f}  min={mn:.3f}%  max={mx:.3f}%  "
              f"(range={mx-mn:.3f}%p, {elapsed:.1f}s)")

    # ---------------- CSV 저장 ----------------
    raw_csv = os.path.join(outdir, "stability_raw_runs.csv")
    with open(raw_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["condition", "seed", "final_coverage"])
        w.writeheader()
        for row in raw_rows:
            w.writerow(row)
    print(f"\n[saved] {raw_csv}")

    summary_csv = os.path.join(outdir, "stability_summary.csv")
    with open(summary_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Condition", "Mean(%)", "Std(%)", "Min(%)", "Max(%)", "Range(%p)", "N_seeds"])
        for cond in conditions:
            s = stats[cond]
            w.writerow([cond, f"{s['mean']:.3f}", f"{s['std']:.3f}", f"{s['min']:.3f}",
                        f"{s['max']:.3f}", f"{s['max']-s['min']:.3f}", N_SEEDS])
    print(f"[saved] {summary_csv}")

    # ---------------- 에러바 막대그래프 ----------------
    fig, ax = plt.subplots(figsize=(8, 5))
    xs = range(len(conditions))
    means = [stats[c]["mean"] for c in conditions]
    stds = [stats[c]["std"] for c in conditions]
    colors = ["tab:blue", "tab:gray", "tab:orange", "tab:red"]
    ax.bar(xs, means, yerr=stds, capsize=6, color=colors, alpha=0.85)

    # 개별 시드 결과도 점으로 흩뿌려서 실제 분포를 보여준다
    for i, cond in enumerate(conditions):
        vals = stats[cond]["values"]
        ax.scatter([i] * len(vals), vals, color="black", s=15, zorder=5, alpha=0.6)

    ax.set_xticks(list(xs))
    ax.set_xticklabels(conditions, rotation=15, ha="right")
    ax.set_ylabel("Final Fault Coverage (%)")
    ax.set_title(f"Stability Across {N_SEEDS} Seeds (s5378, N={NUM_PATTERNS} patterns)\n"
                  f"bar=mean±std, dots=individual seed results")
    ax.grid(axis="y", alpha=0.3)
    fig_path = os.path.join(outdir, "stability_analysis.png")
    plt.savefig(fig_path, dpi=150, bbox_inches="tight")
    print(f"[saved] {fig_path}")

    print("\n=== Summary Table ===")
    print(f"{'Condition':<24s} {'Mean':>8s} {'Std':>7s} {'Min':>8s} {'Max':>8s} {'Range':>8s}")
    for cond in conditions:
        s = stats[cond]
        print(f"{cond:<24s} {s['mean']:>7.3f}% {s['std']:>6.3f} {s['min']:>7.3f}% "
              f"{s['max']:>7.3f}% {s['max']-s['min']:>7.3f}p")


if __name__ == "__main__":
    main()
