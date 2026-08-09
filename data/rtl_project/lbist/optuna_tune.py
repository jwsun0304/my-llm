#!/usr/bin/env python3
"""
optuna_tune.py
--------------
Optuna(TPE, Bayesian) 기반으로 AdaptiveTController의 하이퍼파라미터
(T_init, delta_T, alpha, K, W, calib_multiplier)를 탐색한다.

tune_adaptive.py(random search)를 대체하지 않고 별도 스크립트로 공존시켜,
기존 baseline/random-search 코드와 결과를 그대로 보존한다.

목적함수 (단일 스칼라, maximize):
    score = avg_final_coverage(4개 ISCAS'89 회로 평균, %)
            - SPEED_EPSILON * avg_speed_frac

    avg_speed_frac = 각 회로의 patterns_to_reach(target)/num_patterns 평균
    (0~1, 작을수록 빠름). target은 회로별 Fixed-T(256) 최종 커버리지를
    1회만 계산해 모든 trial에 공통으로 재사용한다 (trial마다 값이 바뀌는
    자기 자신의 최종 커버리지를 목표로 삼으면 척도가 흔들리기 때문).

    SPEED_EPSILON은 아주 작게 잡아(0.01) coverage(0~100 스케일)가 압도적
    우선순위를 갖고, coverage가 사실상 동률일 때만 속도가 순위를 가르도록
    한다 ("동률 시 수렴 속도 우선"의 실용적 구현).

T_max는 탐색 대상에서 제외하고 1024(논문 스펙)로 고정한다 — 기존
tune_adaptive.py의 관례를 그대로 따름.

Optuna study는 SQLite에 저장해(--n-trials로 여러 번 나눠 실행해도) trial
번호가 이어진다. 첫 실행은 --n-trials 1로 시간을 재보고, 이후
--n-trials 29 로 이어서 30개를 채운 뒤 --finalize로 요약/시각화를 만든다.

사용법:
    python3 optuna_tune.py --n-trials 1        # 첫 trial 시간 측정
    python3 optuna_tune.py --n-trials 29        # 이어서 나머지 실행
    python3 optuna_tune.py --finalize           # 저장된 study로 요약/시각화만 생성
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from experiment import LBISTExperiment
from adaptive_controller import FixedTController, AdaptiveTController

import optuna
from optuna.samplers import TPESampler

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


OUTDIR = "results"
STUDY_DB = os.path.join(OUTDIR, "optuna_study.db")
STUDY_NAME = "adaptive_tperiod"
TRIAL_LOG = "trial_log.md"
BASELINE_CACHE = os.path.join(OUTDIR, "optuna_baseline_cache.json")
TARGET_CACHE = os.path.join(OUTDIR, "optuna_targets_cache.json")

SEED = 0xACE1
T_MAX = 1024
SPEED_EPSILON = 0.01
N_STARTUP_TRIALS = 10  # 30 trial 중 초반 10개는 랜덤 탐색, 이후 20개는 TPE 대리모델 기반

CIRCUITS = [
    ("s1494",  "benchmarks/s1494.bench",  6000, 100),
    ("s5378",  "benchmarks/s5378.bench",  6000, 100),
    ("s9234",  "benchmarks/s9234.bench",  3000, 100),
    ("s13207", "benchmarks/s13207.bench", 2000, 100),
]

BASELINE_CONFIG = dict(T_init=128, delta_T=128, alpha=0.95, K=3, W=16, calib_multiplier=1.5)

SEARCH_SPACE = {
    "T_init": (32, 256),
    "delta_T": (32, 256),
    "alpha": (0.70, 0.99),
    "K": (1, 6),
    "W": (4, 48),
    "calib_multiplier": (1.0, 3.0),
}

_experiments = {}  # circuit name -> LBISTExperiment, 프로세스당 1회만 파싱/결함리스트 구성


def get_experiment(name, path):
    if name not in _experiments:
        _experiments[name] = LBISTExperiment(path, seed=SEED, fault_model="collapsed", verbose=False)
    return _experiments[name]


def make_controller(cfg):
    return AdaptiveTController(
        T_init=cfg["T_init"], T_max=T_MAX, delta_T=cfg["delta_T"],
        K=cfg["K"], W=cfg["W"], alpha=cfg["alpha"],
        calibration_patterns=int(cfg["T_init"] * cfg["calib_multiplier"]),
    )


def load_or_compute_targets():
    """회로별 Fixed-T(256) 최종 커버리지 = patterns_to_reach의 공통 목표값."""
    if os.path.exists(TARGET_CACHE):
        with open(TARGET_CACHE) as f:
            return json.load(f)
    targets = {}
    for name, path, num_patterns, record_every in CIRCUITS:
        exp = get_experiment(name, path)
        res = exp.run(FixedTController(T=256), num_patterns, record_every=record_every, seed=SEED)
        targets[name] = res["final_coverage"]
    os.makedirs(OUTDIR, exist_ok=True)
    with open(TARGET_CACHE, "w") as f:
        json.dump(targets, f, indent=2)
    return targets


def evaluate_cfg(cfg, targets):
    per_circuit = {}
    for name, path, num_patterns, record_every in CIRCUITS:
        exp = get_experiment(name, path)
        ctrl = make_controller(cfg)
        res = exp.run(ctrl, num_patterns, record_every=record_every, seed=SEED)
        p2r = exp.patterns_to_reach(res, targets[name])
        speed_frac = (p2r if p2r is not None else num_patterns) / num_patterns
        per_circuit[name] = {
            "final_coverage": res["final_coverage"],
            "patterns_to_reach": p2r,
            "speed_frac": speed_frac,
            "num_transitions": len(res["transitions"]),
        }
    avg_coverage = sum(v["final_coverage"] for v in per_circuit.values()) / len(per_circuit)
    avg_speed_frac = sum(v["speed_frac"] for v in per_circuit.values()) / len(per_circuit)
    score = avg_coverage - SPEED_EPSILON * avg_speed_frac
    return per_circuit, avg_coverage, avg_speed_frac, score


def load_or_compute_baseline(targets):
    if os.path.exists(BASELINE_CACHE):
        with open(BASELINE_CACHE) as f:
            return json.load(f)
    per_circuit, avg_cov, avg_speed, score = evaluate_cfg(BASELINE_CONFIG, targets)
    out = {"config": BASELINE_CONFIG, "per_circuit": per_circuit,
           "avg_coverage": avg_cov, "avg_speed_frac": avg_speed, "score": score}
    with open(BASELINE_CACHE, "w") as f:
        json.dump(out, f, indent=2)
    return out


def _param_distance(cfg_a, cfg_b):
    """탐색공간 범위로 정규화한 유클리드 거리 (대략 0~1대 스케일)."""
    total = 0.0
    for k, (lo, hi) in SEARCH_SPACE.items():
        span = (hi - lo) or 1.0
        total += ((cfg_a[k] - cfg_b[k]) / span) ** 2
    return total ** 0.5


def classify_explore_exploit(trial, cfg, score, study):
    """Optuna는 '왜 이 영역을 시도했는지' 텍스트로 알려주지 않으므로,
    (1) 아직 TPE 대리모델이 없는 랜덤 스타트업 구간인지,
    (2) 있다면 지금까지 최고 trial과 파라미터 공간에서 가까운지
    로 근사 분류한다. 엄밀한 Optuna 내부 로직이 아니라 사후 해석용 근사치."""
    if trial.number < N_STARTUP_TRIALS:
        return f"exploration (초기 랜덤 샘플링, trial {trial.number} < n_startup_trials={N_STARTUP_TRIALS})"
    completed = [t for t in study.trials
                 if t.state == optuna.trial.TrialState.COMPLETE and t.number < trial.number]
    if not completed:
        return "exploration (비교할 이전 completed trial 없음)"
    best_so_far = max(completed, key=lambda t: t.value)
    dist = _param_distance(cfg, best_so_far.params)
    improved = score > best_so_far.value
    tag = "exploitation (현재까지 최고 영역 근처 샘플링)" if dist < 0.15 else "exploration (TPE가 미개척 영역을 시도)"
    outcome = "→ 개선 성공" if improved else "→ 기존 최고 대비 미개선"
    return f"{tag} {outcome} (best-so-far 대비 정규화거리={dist:.3f})"


def append_trial_log(trial, cfg, per_circuit, avg_cov, avg_speed, score, note, elapsed):
    os.makedirs(OUTDIR, exist_ok=True)
    is_new = not os.path.exists(TRIAL_LOG)
    with open(TRIAL_LOG, "a", encoding="utf-8") as f:
        if is_new:
            f.write("# Optuna Trial Log — LBIST Adaptive T-period\n\n")
            f.write(f"목적함수: `score = avg_final_coverage - {SPEED_EPSILON} * avg_speed_frac` "
                    f"(coverage 우선, 사실상 동률일 때만 speed_frac이 tie-break)\n\n")
        f.write(f"## Trial {trial.number}\n")
        f.write(f"- 시각: {datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"- 소요 시간: {elapsed:.1f}s\n")
        f.write(f"- 파라미터: `{cfg}`\n")
        f.write(f"- Optuna 판단(근사): {note}\n")
        f.write(f"- 결과: avg_coverage={avg_cov:.4f}%  avg_speed_frac={avg_speed:.4f}  score={score:.4f}\n")
        f.write("- 회로별 상세:\n\n")
        f.write("  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |\n")
        f.write("  |---|---|---|---|---|\n")
        for name, v in per_circuit.items():
            f.write(f"  | {name} | {v['final_coverage']:.3f} | {v['patterns_to_reach']} | "
                    f"{v['speed_frac']:.3f} | {v['num_transitions']} |\n")
        f.write("\n")


def make_objective(targets):
    def objective(trial):
        cfg = {
            "T_init": trial.suggest_int("T_init", *SEARCH_SPACE["T_init"]),
            "delta_T": trial.suggest_int("delta_T", *SEARCH_SPACE["delta_T"]),
            "alpha": trial.suggest_float("alpha", *SEARCH_SPACE["alpha"]),
            "K": trial.suggest_int("K", *SEARCH_SPACE["K"]),
            "W": trial.suggest_int("W", *SEARCH_SPACE["W"]),
            "calib_multiplier": trial.suggest_float("calib_multiplier", *SEARCH_SPACE["calib_multiplier"]),
        }
        t0 = time.time()
        per_circuit, avg_cov, avg_speed, score = evaluate_cfg(cfg, targets)
        elapsed = time.time() - t0

        note = classify_explore_exploit(trial, cfg, score, trial.study)

        for name, v in per_circuit.items():
            trial.set_user_attr(f"{name}_coverage", v["final_coverage"])
            trial.set_user_attr(f"{name}_speed_frac", v["speed_frac"])
        trial.set_user_attr("avg_coverage", avg_cov)
        trial.set_user_attr("avg_speed_frac", avg_speed)
        trial.set_user_attr("elapsed_sec", elapsed)

        append_trial_log(trial, cfg, per_circuit, avg_cov, avg_speed, score, note, elapsed)
        print(f"[trial {trial.number}] score={score:.4f} avg_cov={avg_cov:.3f}% "
              f"avg_speed_frac={avg_speed:.3f} elapsed={elapsed:.1f}s  cfg={cfg}")
        return score
    return objective


def finalize(study, baseline):
    os.makedirs(OUTDIR, exist_ok=True)
    best = study.best_trial

    try:
        importance = optuna.importance.get_param_importances(study)
    except Exception:
        importance = {}

    delta_cov = best.user_attrs.get("avg_coverage", 0.0) - baseline["avg_coverage"]

    lines = []
    lines.append("# Optuna 최적화 결과 요약\n\n")
    lines.append(f"- 총 trial 수: {len(study.trials)}\n")
    lines.append(f"- Best trial: #{best.number}, score={best.value:.4f}\n")
    lines.append(f"- Best params: `{best.params}`\n")
    lines.append(f"- Best avg_coverage: {best.user_attrs.get('avg_coverage'):.4f}%\n")
    lines.append(f"- Best avg_speed_frac: {best.user_attrs.get('avg_speed_frac'):.4f}\n\n")
    lines.append("## Baseline(논문 기본값) 대비 개선폭\n\n")
    lines.append(f"- Baseline config: `{baseline['config']}`\n")
    lines.append(f"- Baseline avg_coverage: {baseline['avg_coverage']:.4f}%\n")
    lines.append(f"- Baseline avg_speed_frac: {baseline['avg_speed_frac']:.4f}\n")
    lines.append(f"- 개선폭: {delta_cov:+.4f}%p (avg coverage)\n\n")
    lines.append("## Parameter Importance (Optuna fANOVA)\n\n")
    for k, v in sorted(importance.items(), key=lambda x: -x[1]):
        lines.append(f"- {k}: {v:.4f}\n")

    summary_path = os.path.join(OUTDIR, "optuna_summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # -------- 시각화 1: coverage vs trial 진행 --------
    trials_sorted = sorted(
        [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE],
        key=lambda t: t.number)
    xs = [t.number for t in trials_sorted]
    covs = [t.user_attrs.get("avg_coverage") for t in trials_sorted]
    running_best_val = -1e9
    running_best_cov = []
    best_cov_so_far = None
    for t in trials_sorted:
        if t.value > running_best_val:
            running_best_val = t.value
            best_cov_so_far = t.user_attrs.get("avg_coverage")
        running_best_cov.append(best_cov_so_far)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.scatter(xs, covs, color="tab:blue", alpha=0.6, label="trial avg coverage(%)")
    ax.plot(xs, running_best_cov, color="tab:red", linewidth=2, label="best-so-far avg coverage(%)")
    ax.axhline(baseline["avg_coverage"], color="tab:gray", linestyle="--", label="baseline avg coverage(%)")
    ax.set_xlabel("Trial")
    ax.set_ylabel("Avg Fault Coverage (%) across 4 ISCAS'89 circuits")
    ax.set_title("Optuna(TPE) Optimization Progress")
    ax.legend()
    ax.grid(alpha=0.3)
    fig_path = os.path.join(OUTDIR, "optuna_coverage_progress.png")
    plt.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {fig_path}")

    # -------- 시각화 2: parameter importance --------
    if importance:
        fig2, ax2 = plt.subplots(figsize=(7, 4))
        keys = list(importance.keys())
        vals = [importance[k] for k in keys]
        order = sorted(range(len(keys)), key=lambda i: vals[i])
        keys = [keys[i] for i in order]
        vals = [vals[i] for i in order]
        ax2.barh(keys, vals, color="tab:purple")
        ax2.set_xlabel("Importance (fANOVA)")
        ax2.set_title("Optuna Hyperparameter Importance")
        ax2.grid(axis="x", alpha=0.3)
        fig2_path = os.path.join(OUTDIR, "optuna_param_importance.png")
        plt.savefig(fig2_path, dpi=150, bbox_inches="tight")
        plt.close(fig2)
        print(f"[saved] {fig2_path}")

    print("".join(lines))
    print(f"[saved] {summary_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-trials", type=int, default=0, help="이번 실행에서 새로 돌릴 trial 수")
    ap.add_argument("--finalize", action="store_true", help="저장된 study로 요약/시각화 생성")
    ap.add_argument("--rng-seed", type=int, default=42, help="TPE sampler 재현성용 시드")
    args = ap.parse_args()

    os.makedirs(OUTDIR, exist_ok=True)
    targets = load_or_compute_targets()
    baseline = load_or_compute_baseline(targets)
    print(f"[baseline] avg_coverage={baseline['avg_coverage']:.4f}%  "
          f"avg_speed_frac={baseline['avg_speed_frac']:.4f}  score={baseline['score']:.4f}")

    storage = f"sqlite:///{STUDY_DB}"
    sampler = TPESampler(seed=args.rng_seed, n_startup_trials=N_STARTUP_TRIALS)
    study = optuna.create_study(study_name=STUDY_NAME, storage=storage,
                                 direction="maximize", sampler=sampler, load_if_exists=True)

    if args.n_trials > 0:
        t0 = time.time()
        study.optimize(make_objective(targets), n_trials=args.n_trials)
        elapsed = time.time() - t0
        print(f"[batch] {args.n_trials} trial(s) in {elapsed:.1f}s "
              f"({elapsed/args.n_trials:.1f}s/trial avg)")

    if args.finalize:
        finalize(study, baseline)


if __name__ == "__main__":
    main()
