#!/usr/bin/env python3
"""
gen_controller_dataset.py
--------------------------
AdaptiveTController(src/adaptive_controller.py)를 4개 ISCAS'89 벤치마크 x
여러 시드 x 여러 하이퍼파라미터 config로 실제 LBIST 파이프라인(PRPG->
스캔그룹->결함시뮬레이터->MISR->controller) 위에서 반복 실행하면서, 매
controller.update(hd) 호출 시점의 특징과 두 종류의 레이블을 기록해 신경망
학습용 데이터셋을 만든다.

기존 코드는 전혀 수정하지 않는다 — experiment.py의 run() 루프를 그대로
재현하되, exp.run()이 내부적으로 감춰버리는 매 패턴 단위의 controller
내부 상태(hd_window, baseline, n_seen 등)를 이 스크립트에서 직접
들여다볼 수 있도록 루프를 풀어썼다.

왜 config를 하나가 아니라 여러 개 섞는가:
    Optuna 최적 config(alpha=0.841)만 쓰면 threshold=alpha*baseline이 낮아서
    (=민감도가 낮아서) 실제 회로에서 정체 판정 자체가 극히 드물게 나온다
    (1차 조사 결과: 4개 회로 중 3개가 0건). trial_log.md에 기록된 30개
    Optuna trial 중 alpha가 상대적으로 큰(=threshold가 baseline에 더 가까워
    민감도가 높은) config들을 같이 섞으면, "정체로 판정되는 상황"의 예시를
    더 많이 확보할 수 있다. 각 row에 어떤 config로 생성됐는지(config_id와
    실제 파라미터 값)를 그대로 남겨서, 이후 모델 설계 단계에서 이 정보를
    특징으로 쓸지, 그냥 데이터 증강으로만 쓸지는 선택할 수 있게 했다.

특징 (요청받은 4개 + config 파라미터 컬럼):
    hd_window_mean       : hd_window(길이 W)의 평균 = controller가 실제로
                            threshold와 비교하는 avg_hd 그 자체
    hd_window_trend_slope: hd_window 내부의 단순 최소자승 선형회귀 기울기
    hd_window_variance    : hd_window의 (모)분산
    n_seen                : 지금까지 처리한 총 update() 호출 수

레이블 (둘 다 기록 - 무엇으로 학습할지는 모델 설계 단계에서 결정):
    label_T_increased     = 1 : 이번 호출에서 stalled==True (K연속+임계값
                                 미만이 모두 만족돼 T가 실제로 증가한 순간).
                                 복합 이벤트라 여전히 드물다.
    label_below_threshold = 1 : avg_hd < threshold (K-카운터가 증가하는
                                 원자적 단일 조건). 더 자주 발생한다.

설계 결정 - calibration 구간 제외:
    calibration 구간에는 baseline이 아직 없어 controller가 애초에 threshold
    판정을 하지 않는다(update()가 항상 False). 이 구간은 "결정 근거 없는
    자동 negative"라 데이터셋에서 제외했다.

사용법:
    python ml/gen_controller_dataset.py
    python ml/gen_controller_dataset.py --seeds 2 --top-alpha 6 --outdir ml/dataset
"""

import argparse
import ast
import csv
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bench_parser import parse_bench
from fault_sim import ParallelFaultSimulator
from fault_collapse import build_fault_list_collapsed
from prpg_misr import PhaseShifterPRPG, MISR, hamming_distance
from scan_groups import ScanGroupController
from adaptive_controller import AdaptiveTController

T_MAX = 1024   # 논문 스펙 고정 (모든 config 공통, 프로젝트 관례)

# Optuna(TPE) best trial (RTL에도 반영된 config) - "canonical" 기준
BEST_CONFIG = dict(T_init=33, delta_T=193, alpha=0.8410895754890528, K=3, W=34,
                    calib_multiplier=2.183035341991451)

CIRCUITS = [
    ("s1494",  "benchmarks/s1494.bench",  15000),
    ("s5378",  "benchmarks/s5378.bench",  15000),
    ("s9234",  "benchmarks/s9234.bench",  8000),
    ("s13207", "benchmarks/s13207.bench", 6000),
]


def load_trial_configs(path="trial_log.md"):
    """trial_log.md에서 '- 파라미터: `{...}`' 라인을 전부 파싱해 dict 리스트로."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    dicts = re.findall(r"- 파라미터: `(\{.*?\})`", text)
    configs = []
    seen = set()
    for d in dicts:
        cfg = ast.literal_eval(d)
        key = tuple(sorted(cfg.items()))
        if key not in seen:
            seen.add(key)
            configs.append(cfg)
    return configs


def select_configs(top_alpha_n):
    """alpha가 가장 큰(=threshold가 민감한) 상위 N개 trial config + best config."""
    trials = load_trial_configs()
    trials_sorted = sorted(trials, key=lambda c: c["alpha"], reverse=True)
    chosen = []
    chosen_keys = set()

    best_key = tuple(sorted(BEST_CONFIG.items()))
    chosen.append(("best", BEST_CONFIG))
    chosen_keys.add(best_key)

    for cfg in trials_sorted:
        if len(chosen) - 1 >= top_alpha_n:   # best 제외하고 top_alpha_n개
            break
        key = tuple(sorted(cfg.items()))
        if key in chosen_keys:
            continue
        chosen_keys.add(key)
        chosen.append((f"high_alpha_{cfg['alpha']:.3f}", cfg))
    return chosen


def linear_slope(values):
    """단순 최소자승 선형회귀 기울기 (x=0..n-1, y=values)."""
    n = len(values)
    if n < 2:
        return 0.0
    xbar = (n - 1) / 2.0
    ybar = sum(values) / n
    num = sum((i - xbar) * (v - ybar) for i, v in enumerate(values))
    den = sum((i - xbar) ** 2 for i in range(n))
    return num / den if den else 0.0


def variance(values):
    n = len(values)
    if n == 0:
        return 0.0
    m = sum(values) / n
    return sum((v - m) ** 2 for v in values) / n


def run_one(bench_path, num_patterns, seed, cfg):
    """experiment.py의 run() 루프를 그대로 재현하되, 매 패턴마다 controller의
    내부 상태를 들여다봐서 (steady-state 구간만) 특징/레이블 row를 뽑는다."""
    circuit = parse_bench(bench_path)
    faults = build_fault_list_collapsed(circuit, verbose=False)
    sim = ParallelFaultSimulator(circuit, faults)
    prpg = PhaseShifterPRPG(num_bits=circuit.num_inputs, seed=seed)
    misr = MISR(num_inputs=circuit.num_outputs)
    scan_ctrl = ScanGroupController(circuit.inputs, num_groups=4)
    calibration_patterns = int(cfg["T_init"] * cfg["calib_multiplier"])
    ctrl = AdaptiveTController(T_init=cfg["T_init"], T_max=T_MAX, delta_T=cfg["delta_T"],
                                K=cfg["K"], W=cfg["W"], alpha=cfg["alpha"],
                                calibration_patterns=calibration_patterns)

    prev_sig = None
    rows = []
    for p in range(1, num_patterns + 1):
        candidate = prpg.next_pattern()
        applied = scan_ctrl.apply_new_pattern(candidate)
        good_outputs = sim.simulate_pattern(applied)
        sig = misr.compress(good_outputs)
        hd = 0 if prev_sig is None else hamming_distance(sig, prev_sig)
        prev_sig = sig

        T_before = ctrl.current_T()
        stalled = ctrl.update(hd, misr_width=misr.width, pattern_index=p)
        T_after = ctrl.current_T()
        scan_ctrl.maybe_switch_group(T_after)

        if ctrl._baseline is not None:   # steady-state 구간만 기록 (calibration 제외)
            window = list(ctrl.hd_window)
            hd_window_mean = sum(window) / len(window) if window else 0.0
            threshold = cfg["alpha"] * ctrl._baseline
            rows.append({
                "pattern_index": p,
                "hd": hd,
                "n_seen": ctrl._n_seen,
                "hd_window_mean": hd_window_mean,
                "hd_window_trend_slope": linear_slope(window),
                "hd_window_variance": variance(window),
                "baseline": ctrl._baseline,
                "threshold": threshold,
                "consecutive_low": ctrl.consecutive_low,
                "T_before": T_before,
                "T_after": T_after,
                "label_T_increased": 1 if stalled else 0,
                "label_below_threshold": 1 if hd_window_mean < threshold else 0,
                "cfg_T_init": cfg["T_init"],
                "cfg_delta_T": cfg["delta_T"],
                "cfg_alpha": cfg["alpha"],
                "cfg_K": cfg["K"],
                "cfg_W": cfg["W"],
                "cfg_calib_multiplier": cfg["calib_multiplier"],
            })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=2, help="config x 회로당 시드 개수")
    ap.add_argument("--top-alpha", type=int, default=6,
                     help="best config 외에 alpha 상위 몇 개 trial config를 더 섞을지")
    ap.add_argument("--outdir", default="ml/dataset")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    seed_pool = [0xACE1 + i * 0x1111 for i in range(args.seeds)]

    configs = select_configs(args.top_alpha)
    print("=== 사용할 config들 (alpha 내림차순, best 포함) ===")
    for cid, cfg in configs:
        print(f"  [{cid:16s}] alpha={cfg['alpha']:.4f} T_init={cfg['T_init']:>4} "
              f"delta_T={cfg['delta_T']:>4} K={cfg['K']} W={cfg['W']:>2} "
              f"calib_x={cfg['calib_multiplier']:.3f}")

    fieldnames = ["circuit", "seed", "config_id", "pattern_index", "hd", "n_seen",
                  "hd_window_mean", "hd_window_trend_slope", "hd_window_variance",
                  "baseline", "threshold", "consecutive_low",
                  "T_before", "T_after", "label_T_increased", "label_below_threshold",
                  "cfg_T_init", "cfg_delta_T", "cfg_alpha", "cfg_K", "cfg_W",
                  "cfg_calib_multiplier"]

    out_path = os.path.join(args.outdir, "controller_dataset.csv")
    total_rows = 0
    total_pos_T = 0
    total_pos_thr = 0
    per_config_stats = []

    t0 = time.time()
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for cid, cfg in configs:
            cfg_rows = 0
            cfg_pos_T = 0
            cfg_pos_thr = 0
            tcfg0 = time.time()
            for name, path, num_patterns in CIRCUITS:
                for seed in seed_pool:
                    rows = run_one(path, num_patterns, seed, cfg)
                    for r in rows:
                        r2 = dict(r)
                        r2["circuit"] = name
                        r2["seed"] = f"0x{seed:04X}"
                        r2["config_id"] = cid
                        writer.writerow(r2)
                    cfg_rows += len(rows)
                    cfg_pos_T += sum(r["label_T_increased"] for r in rows)
                    cfg_pos_thr += sum(r["label_below_threshold"] for r in rows)
            elapsed = time.time() - tcfg0
            total_rows += cfg_rows
            total_pos_T += cfg_pos_T
            total_pos_thr += cfg_pos_thr
            per_config_stats.append((cid, cfg["alpha"], cfg_rows, cfg_pos_T, cfg_pos_thr, elapsed))
            print(f"[{cid}] alpha={cfg['alpha']:.4f} -> {cfg_rows} rows, "
                  f"T_increased={cfg_pos_T}, below_threshold={cfg_pos_thr}  ({elapsed:.1f}s)")

    total_elapsed = time.time() - t0
    total_neg_T = total_rows - total_pos_T
    total_neg_thr = total_rows - total_pos_thr

    print(f"\n[saved] {out_path}")
    print(f"\n=== 데이터셋 요약 ({total_elapsed:.1f}s, {len(configs)} configs x "
          f"{len(CIRCUITS)} circuits x {args.seeds} seeds) ===")
    print(f"총 샘플 수: {total_rows}")
    print(f"[label_T_increased]     positive={total_pos_T}  ({100*total_pos_T/total_rows:.3f}%)  "
          f"negative={total_neg_T}  " +
          (f"불균형={total_neg_T/total_pos_T:.1f}:1" if total_pos_T else "positive 0개"))
    print(f"[label_below_threshold] positive={total_pos_thr}  ({100*total_pos_thr/total_rows:.3f}%)  "
          f"negative={total_neg_thr}  " +
          (f"불균형={total_neg_thr/total_pos_thr:.1f}:1" if total_pos_thr else "positive 0개"))

    print("\nconfig별 (alpha 내림차순):")
    for cid, alpha, rows, pos_T, pos_thr, elapsed in per_config_stats:
        print(f"  [{cid:16s}] alpha={alpha:.4f} rows={rows:6d}  "
              f"T_increased={pos_T:4d} ({100*pos_T/rows:.2f}%)  "
              f"below_threshold={pos_thr:5d} ({100*pos_thr/rows:.2f}%)  ({elapsed:.1f}s)")


if __name__ == "__main__":
    main()
