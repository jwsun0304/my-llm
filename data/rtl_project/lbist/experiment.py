"""
experiment.py
-------------
Fixed-T(256), Fixed-T(1024), Adaptive-T 세 조건에 대해 LBIST 시뮬레이션을
수행하고, 패턴 수에 따른 fault coverage 곡선 및 T 전환 이력을 산출한다.

한 사이클(=한 패턴)의 흐름:
    1. PRPG가 16-bit LFSR을 전진시켜 새 후보 스캔 패턴(214-bit) 생성
    2. ScanGroupController가 "현재 활성 그룹"만 새 값으로 갱신,
       나머지 그룹은 이전 값 유지 (GSS 동작 모사)
    3. 합성된 214-bit 패턴을 ParallelFaultSimulator에 인가
       -> good-machine 출력(228-bit) + 결함 검출 갱신
    4. MISR이 good-machine 출력을 16-bit 시그니처로 압축
    5. 직전 시그니처와의 Hamming Distance 계산 -> T controller에 전달
    6. T controller가 (Adaptive-T의 경우) 필요 시 T를 증가
    7. ScanGroupController가 현재 T를 기준으로 그룹 전환 여부 판단
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

from bench_parser import parse_bench
from fault_sim import build_fault_list, ParallelFaultSimulator
from fault_collapse import build_fault_list_collapsed
from prpg_misr import PhaseShifterPRPG, MISR, hamming_distance
from scan_groups import ScanGroupController
from adaptive_controller import FixedTController, AdaptiveTController


class LBISTExperiment:
    def __init__(self, bench_path: str, seed: int = 0xACE1, num_groups: int = 4,
                 verbose: bool = True, fault_model: str = "collapsed"):
        """
        fault_model: "collapsed"(기본값, fault_collapse.py의 등가 결함
                     collapsing 적용 — 더 빠르고 표준적인 결함 수 사용) 또는
                     "full"(전체 line-level SA0/SA1, collapsing 없음 —
                     이전 세션에서 검증했던 수치와 동일하게 재현하고 싶을 때).
        """
        self.verbose = verbose
        t0 = time.time()
        self.circuit = parse_bench(bench_path)
        if verbose:
            print(f"[circuit] {self.circuit.summary()}  (parsed in {time.time()-t0:.2f}s)")

        if fault_model == "collapsed":
            self.faults = build_fault_list_collapsed(self.circuit, verbose=verbose)
        else:
            self.faults = build_fault_list(self.circuit)
            if verbose:
                print(f"[faults] total stuck-at faults = {len(self.faults)}")

        self.fault_model = fault_model
        self.seed = seed
        self.num_groups = num_groups

    def _fresh_engines(self, seed=None):
        """매 실험 조건(Fixed-256 / Fixed-1024 / Adaptive)마다 완전히
        동일한 초기 조건에서 새로 시작하도록 모든 상태를 재생성한다."""
        use_seed = seed if seed is not None else self.seed
        sim = ParallelFaultSimulator(self.circuit, self.faults)
        prpg = PhaseShifterPRPG(num_bits=self.circuit.num_inputs, seed=use_seed)
        misr = MISR(num_inputs=self.circuit.num_outputs)
        scan_ctrl = ScanGroupController(self.circuit.inputs, num_groups=self.num_groups)
        return sim, prpg, misr, scan_ctrl

    def run(self, controller, num_patterns: int, record_every: int = 50, seed=None):
        """
        controller: FixedTController 또는 AdaptiveTController 인스턴스
        num_patterns: 총 인가할 패턴(사이클) 수
        record_every: 이 주기마다 (pattern_index, coverage)를 기록
        seed: None이면 self.seed 사용. 여러 시드로 반복 실행(튜닝/안정성
              분석)할 때 호출별로 다른 값을 넘길 수 있다.

        반환: dict(
            pattern_idx: list[int],
            coverage: list[float],
            T_history: list[int]       (매 record_every 지점의 현재 T)
            transitions: list[(pattern_idx, old_T, new_T)]
            final_coverage: float
            detected_faults: int
        )
        """
        sim, prpg, misr, scan_ctrl = self._fresh_engines(seed=seed)

        prev_sig = None
        pattern_idx_log = []
        coverage_log = []
        T_log = []
        hd_log = []

        t0 = time.time()
        for p in range(1, num_patterns + 1):
            candidate = prpg.next_pattern()
            applied = scan_ctrl.apply_new_pattern(candidate)

            good_outputs = sim.simulate_pattern(applied)

            sig = misr.compress(good_outputs)
            if prev_sig is None:
                hd = 0
            else:
                hd = hamming_distance(sig, prev_sig)
            prev_sig = sig

            controller.update(hd, misr_width=misr.width, pattern_index=p)
            T = controller.current_T()
            scan_ctrl.maybe_switch_group(T)

            if p % record_every == 0 or p == num_patterns:
                pattern_idx_log.append(p)
                coverage_log.append(sim.coverage() * 100.0)
                T_log.append(T)
                hd_log.append(hd)

        elapsed = time.time() - t0
        transitions = getattr(controller, "transition_log", [])

        if self.verbose:
            print(f"[run] {num_patterns} patterns in {elapsed:.1f}s "
                  f"({elapsed/num_patterns*1000:.2f} ms/pattern) | "
                  f"final coverage = {sim.coverage()*100:.3f}% | "
                  f"detected = {sim.num_detected()}/{sim.num_faults} | "
                  f"T transitions = {len(transitions)}")

        return {
            "pattern_idx": pattern_idx_log,
            "coverage": coverage_log,
            "T_history": T_log,
            "hd_history": hd_log,
            "transitions": transitions,
            "final_coverage": sim.coverage() * 100.0,
            "detected_faults": sim.num_detected(),
            "total_faults": sim.num_faults,
            "elapsed_sec": elapsed,
        }

    def patterns_to_reach(self, result: dict, target_coverage: float):
        """기록된 coverage 로그에서 target_coverage(%) 를 최초로 넘는
        패턴 수를 찾는다 (없으면 None)."""
        for idx, cov in zip(result["pattern_idx"], result["coverage"]):
            if cov >= target_coverage:
                return idx
        return None

    @staticmethod
    def coverage_auc(result: dict) -> float:
        """
        Coverage curve의 (근사) area-under-curve를 패턴 수로 정규화한 값.
        기록 간격이 균일하므로 단순 평균으로 근사해도 충분하다.

        이 값이 크다는 것은 "커버리지가 빨리, 그리고 높게 올라갔다"는
        뜻이므로, TAT(목표 커버리지 도달 패턴 수)와 최종 커버리지를
        동시에 반영하는 단일 스칼라 목적함수로 파라미터 튜닝에 사용한다.
        """
        cov = result["coverage"]
        if not cov:
            return 0.0
        return sum(cov) / len(cov)
