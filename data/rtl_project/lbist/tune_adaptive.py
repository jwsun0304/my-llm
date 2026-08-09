#!/usr/bin/env python3
"""
tune_adaptive.py
-----------------
Adaptive-T 컨트롤러의 하이퍼파라미터(T_init, delta_T, alpha, K, W,
calibration 배율)를 random search로 자동 탐색한다.

왜 grid search가 아니라 random search인가:
    탐색 공간이 5차원이라 완전 grid는 조합 폭발이 심하다(수백~수천 회).
    Bergstra & Bengio(2012) 등에서 보이듯, 같은 평가 횟수 예산에서는
    random search가 grid search보다 평균적으로 더 좋은(또는 비슷한)
    최적해를 찾는 경향이 있어, 제한된 시간 예산 안에서 실용적이다.

목적함수:
    LBISTExperiment.coverage_auc() — 기록된 coverage 곡선의 평균값.
    "얼마나 빨리, 얼마나 높이 커버리지가 오르는가"를 하나의 스칼라로
    요약한 값이며, 값이 클수록 좋다. 여러 시드로 반복 평가한 뒤 평균을
    취해 특정 PRPG 시퀀스에 대한 과적합(overfitting)을 방지한다.

2단계 절차:
    1) Search 단계: 작은 패턴 수(--search-patterns) x 적은 시드 수
       (--search-seeds)로 다수의 후보(--trials)를 빠르게 스크리닝한다.
    2) Validation 단계: 상위 top-k 후보만 큰 패턴 수(--val-patterns) x
       더 많은 시드(--val-seeds)로 재평가하여, 작은 표본에서 우연히
       좋아 보인 후보(overfitting)를 걸러내고 최종 승자를 가린다.

사용법:
    python3 tune_adaptive.py
    python3 tune_adaptive.py --trials 25 --search-patterns 2500 --val-patterns 6000
"""

import argparse
import csv
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from experiment import LBISTExperiment
from adaptive_controller import FixedTController, AdaptiveTController

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------
# 탐색 공간 정의
# ---------------------------------------------------------------------
SEARCH_SPACE = {
    "T_init": [64, 96, 128, 192],
    "delta_T": [64, 96, 128, 192, 256],
    "alpha": [0.80, 0.85, 0.90, 0.95, 0.98],
    "K": [2, 3, 4, 5],
    "W": [8, 12, 16, 24, 32],
    "calib_multiplier": [1.2, 1.5, 2.0, 3.0],  # calibration_patterns = T_init * multiplier
}

DEFAULT_CONFIG = {  # run_experiment.py가 지금까지 써온 기본값 (비교 기준선)
    "T_init": 128, "delta_T": 128, "alpha": 0.95, "K": 3, "W": 16,
    "calib_multiplier": 1.5,
}

T_MAX = 1024  # 논문 스펙 고정


FIXED_T_SWEEP = [32, 64, 128, 256, 512, 1024]


def sample_config(rng: random.Random) -> dict:
    return {k: rng.choice(v) for k, v in SEARCH_SPACE.items()}


def make_controller(cfg: dict) -> AdaptiveTController:
    return AdaptiveTController(
        T_init=cfg["T_init"], T_max=T_MAX, delta_T=cfg["delta_T"],
        K=cfg["K"], W=cfg["W"], alpha=cfg["alpha"],
        calibration_patterns=int(cfg["T_init"] * cfg["calib_multiplier"]),
    )


def evaluate_config(exp: LBISTExperiment, cfg: dict, num_patterns: int,
                     seeds: list, record_every: int):
    """cfg를 여러 seed로 평가해 (평균 AUC, 평균 final coverage, 각 run 결과) 반환."""
    aucs, finals = [], []
    for sd in seeds:
        ctrl = make_controller(cfg)
        res = exp.run(ctrl, num_patterns, record_every=record_every, seed=sd)
        aucs.append(exp.coverage_auc(res))
        finals.append(res["final_coverage"])
    return sum(aucs) / len(aucs), sum(finals) / len(finals)


def evaluate_fixed_T(exp: LBISTExperiment, T: int, num_patterns: int,
                      seeds: list, record_every: int):
    aucs, finals = [], []
    for sd in seeds:
        res = exp.run(FixedTController(T=T), num_patterns, record_every=record_every, seed=sd)
        aucs.append(exp.coverage_auc(res))
        finals.append(res["final_coverage"])
    return sum(aucs) / len(aucs), sum(finals) / len(finals)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default="benchmarks/s5378.bench")
    ap.add_argument("--trials", type=int, default=12, help="random search 후보 개수")
    ap.add_argument("--search-patterns", type=int, default=2000)
    ap.add_argument("--search-seeds", type=int, default=2)
    ap.add_argument("--search-record-every", type=int, default=100)
    ap.add_argument("--top-k", type=int, default=3, help="validation 단계로 넘길 상위 후보 수")
    ap.add_argument("--val-patterns", type=int, default=5000)
    ap.add_argument("--val-seeds", type=int, default=2)
    ap.add_argument("--val-record-every", type=int, default=50)
    ap.add_argument("--sweep-seeds", type=int, default=2, help="Fixed-T 스윕에 쓸 시드 수")
    ap.add_argument("--rng-seed", type=int, default=42, help="random search 자체의 재현성용 시드")
    ap.add_argument("--outdir", default="results")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    rng = random.Random(args.rng_seed)

    # 시드 풀: search/validation/sweep 단계에서 재사용할 PRPG 시드들
    max_seeds_needed = max(args.search_seeds, args.val_seeds, args.sweep_seeds)
    seed_pool = [0xACE1 + i * 0x1111 for i in range(max_seeds_needed + 1)]
    search_seeds = seed_pool[:args.search_seeds]
    val_seeds = seed_pool[:args.val_seeds]
    sweep_seeds = seed_pool[:args.sweep_seeds]

    exp = LBISTExperiment(args.bench, verbose=True)

    # -------------------- 0) 기본값(default) baseline 평가 --------------------
    print(f"\n[baseline] default config = {DEFAULT_CONFIG}")
    base_auc, base_final = evaluate_config(exp, DEFAULT_CONFIG, args.search_patterns,
                                            search_seeds, args.search_record_every)
    print(f"[baseline] search-scale AUC={base_auc:.3f}  final_cov(avg)={base_final:.3f}%")

    # -------------------- 1) Search 단계: random search --------------------
    print(f"\n=== Random Search: {args.trials} trials, "
          f"{args.search_patterns} patterns x {args.search_seeds} seeds each ===")

    candidates = [dict(DEFAULT_CONFIG)]  # 기본값도 후보 풀에 포함 (항상 비교 가능하게)
    for _ in range(args.trials):
        candidates.append(sample_config(rng))

    search_rows = []
    t_search0 = time.time()
    for i, cfg in enumerate(candidates):
        auc, final = evaluate_config(exp, cfg, args.search_patterns, search_seeds,
                                      args.search_record_every)
        tag = "DEFAULT" if cfg == DEFAULT_CONFIG else f"trial_{i}"
        print(f"  [{tag:10s}] T_init={cfg['T_init']:>4} delta_T={cfg['delta_T']:>4} "
              f"alpha={cfg['alpha']:.2f} K={cfg['K']} W={cfg['W']:>2} "
              f"calib_x={cfg['calib_multiplier']:.1f}  ->  AUC={auc:.3f}  final={final:.3f}%")
        row = dict(cfg)
        row.update({"tag": tag, "auc": auc, "final_coverage": final})
        search_rows.append(row)
    print(f"[search phase elapsed] {time.time()-t_search0:.1f}s")

    search_rows.sort(key=lambda r: r["auc"], reverse=True)

    search_csv = os.path.join(args.outdir, "tuning_search_results.csv")
    with open(search_csv, "w", newline="") as f:
        fieldnames = ["tag", "T_init", "delta_T", "alpha", "K", "W",
                      "calib_multiplier", "auc", "final_coverage"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in search_rows:
            w.writerow({k: row[k] for k in fieldnames})
    print(f"[saved] {search_csv}")

    # -------------------- 2) Validation 단계: 상위 top-k 재평가 --------------------
    top_candidates = search_rows[:args.top_k]
    # DEFAULT가 top-k 밖이면 비교 기준으로 강제 포함
    if not any(r["tag"] == "DEFAULT" for r in top_candidates):
        default_row = next(r for r in search_rows if r["tag"] == "DEFAULT")
        top_candidates.append(default_row)

    print(f"\n=== Validation: top-{len(top_candidates)} candidates, "
          f"{args.val_patterns} patterns x {args.val_seeds} seeds each ===")

    val_rows = []
    t_val0 = time.time()
    for row in top_candidates:
        cfg = {k: row[k] for k in SEARCH_SPACE}
        auc, final = evaluate_config(exp, cfg, args.val_patterns, val_seeds,
                                      args.val_record_every)
        print(f"  [{row['tag']:10s}] validation AUC={auc:.3f}  final_cov(avg)={final:.3f}%")
        val_rows.append({**cfg, "tag": row["tag"], "val_auc": auc, "val_final_coverage": final})
    print(f"[validation phase elapsed] {time.time()-t_val0:.1f}s")

    val_rows.sort(key=lambda r: r["val_auc"], reverse=True)
    best = val_rows[0]

    val_csv = os.path.join(args.outdir, "tuning_validation_results.csv")
    with open(val_csv, "w", newline="") as f:
        fieldnames = ["tag", "T_init", "delta_T", "alpha", "K", "W",
                      "calib_multiplier", "val_auc", "val_final_coverage"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in val_rows:
            w.writerow({k: row[k] for k in fieldnames})
    print(f"[saved] {val_csv}")

    print(f"\n>>> BEST ADAPTIVE CONFIG (of the trials searched): {best['tag']} <<<")
    for k in SEARCH_SPACE:
        print(f"    {k} = {best[k]}")
    print(f"    validation AUC = {best['val_auc']:.3f}, "
          f"final coverage(avg over {args.val_seeds} seeds) = {best['val_final_coverage']:.3f}%")

    # -------------------- 2b) 정직한 비교: Fixed-T 값도 함께 스윕 --------------------
    # Adaptive 튜닝이 진짜 의미가 있으려면, "가장 좋은 고정 T"보다도 나아야 한다.
    # 그렇지 않다면 (즉 어떤 고정 T 하나가 항상 이긴다면) 이 패턴 수 규모에서는
    # 그냥 그 고정 T를 쓰는 것이 더 간단하고 좋다는 뜻이며, 이는 그 자체로
    # 유효하고 정직한 엔지니어링 결론이다.
    print(f"\n=== Fixed-T sweep for honest comparison: {FIXED_T_SWEEP} ===")
    fixed_rows = []
    for T in FIXED_T_SWEEP:
        auc, final = evaluate_fixed_T(exp, T, args.val_patterns, sweep_seeds, args.val_record_every)
        print(f"  [Fixed-T={T:>4}] validation AUC={auc:.3f}  final_cov(avg)={final:.3f}%")
        fixed_rows.append({"T": T, "val_auc": auc, "val_final_coverage": final})
    best_fixed = max(fixed_rows, key=lambda r: r["val_auc"])

    fixed_csv = os.path.join(args.outdir, "fixed_T_sweep_results.csv")
    with open(fixed_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["T", "val_auc", "val_final_coverage"])
        w.writeheader()
        for row in fixed_rows:
            w.writerow(row)
    print(f"[saved] {fixed_csv}")

    verdict = "ADAPTIVE WINS" if best["val_auc"] > best_fixed["val_auc"] else "BEST-FIXED-T WINS"
    print(f"\n>>> Best Adaptive AUC={best['val_auc']:.3f}  vs  "
          f"Best Fixed-T(T={best_fixed['T']}) AUC={best_fixed['val_auc']:.3f}  =>  {verdict}")

    # -------------------- 3) 최종 확인: best vs default vs Fixed-T 곡선 비교 --------------------
    plot_seed = val_seeds[0]
    best_cfg = {k: best[k] for k in SEARCH_SPACE}

    res_default = exp.run(make_controller(DEFAULT_CONFIG), args.val_patterns,
                           record_every=args.val_record_every, seed=plot_seed)
    res_best = exp.run(make_controller(best_cfg), args.val_patterns,
                        record_every=args.val_record_every, seed=plot_seed)
    res_f256 = exp.run(FixedTController(T=256), args.val_patterns,
                        record_every=args.val_record_every, seed=plot_seed)
    res_f1024 = exp.run(FixedTController(T=1024), args.val_patterns,
                         record_every=args.val_record_every, seed=plot_seed)
    res_fbest = exp.run(FixedTController(T=best_fixed["T"]), args.val_patterns,
                         record_every=args.val_record_every, seed=plot_seed)

    plt.figure(figsize=(8, 5))
    plt.plot(res_f256["pattern_idx"], res_f256["coverage"], "--", color="tab:blue",
              alpha=0.6, label="Fixed-T (T=256)")
    plt.plot(res_f1024["pattern_idx"], res_f1024["coverage"], "--", color="tab:gray",
              alpha=0.6, label="Fixed-T (T=1024)")
    plt.plot(res_fbest["pattern_idx"], res_fbest["coverage"], "-", color="tab:green",
              linewidth=2, label=f"Best Fixed-T (T={best_fixed['T']}, sweep winner)")
    plt.plot(res_default["pattern_idx"], res_default["coverage"], "-", color="tab:orange",
              label="Adaptive-T (default params)")
    plt.plot(res_best["pattern_idx"], res_best["coverage"], "-", linewidth=2.5, color="tab:red",
              label=f"Adaptive-T (tuned: {best['tag']})")
    plt.xlabel("Test Patterns")
    plt.ylabel("Fault Coverage (%)")
    plt.title(f"Tuned Adaptive-T vs Best Fixed-T (s5378, N={args.val_patterns}, seed=0x{plot_seed:04X})")
    plt.legend(fontsize=8)
    plt.grid(alpha=0.3)
    fig_path = os.path.join(args.outdir, "tuned_vs_default_comparison.png")
    plt.savefig(fig_path, dpi=150, bbox_inches="tight")
    print(f"[saved] {fig_path}")

    summary_csv = os.path.join(args.outdir, "tuning_summary.csv")
    with open(summary_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Condition", "Final coverage (%)", "Detected", "Total"])
        for name, res in [("Fixed-T(256)", res_f256), ("Fixed-T(1024)", res_f1024),
                           (f"Best Fixed-T (sweep, T={best_fixed['T']})", res_fbest),
                           ("Adaptive-T (default params)", res_default),
                           (f"Adaptive-T (tuned: {best['tag']})", res_best)]:
            w.writerow([name, f"{res['final_coverage']:.3f}",
                        res["detected_faults"], res["total_faults"]])
        w.writerow([])
        w.writerow(["Verdict:", verdict])
        w.writerow([])
        w.writerow(["Best tuned adaptive hyperparameters:"])
        for k in SEARCH_SPACE:
            w.writerow([k, best_cfg[k]])
    print(f"[saved] {summary_csv}")

    print("\n=== Done ===")
    print(f"Default Adaptive-T final coverage : {res_default['final_coverage']:.3f}%")
    print(f"Tuned   Adaptive-T final coverage : {res_best['final_coverage']:.3f}%")
    print(f"Best Fixed-T (T={best_fixed['T']}) final coverage: {res_fbest['final_coverage']:.3f}%")
    print(f"\nVerdict for this circuit/pattern-budget: {verdict}")
    print("(patterns 수를 늘리면(--val-patterns 30000 등) 결과가 달라질 수 있습니다 — "
          "README의 '한계 및 확장' 섹션 참고)")


if __name__ == "__main__":
    main()
