#!/usr/bin/env python3
"""
gen_reference_vectors.py
-------------------------
src/prpg_misr.py, src/adaptive_controller.py의 실제 Python 클래스를 그대로
import해서 골든 레퍼런스 벡터를 생성한다. RTL testbench는 $readmemh로 이
파일들을 읽어 self-checking 비교를 수행한다.

이 스크립트가 만드는 파일들 (전부 tb/vectors/):
    prpg_ref.hex              - PhaseShifterPRPG(NUM_BITS=214) 214-cycle 패턴 시퀀스
    misr_stimulus.hex         - MISR(NUM_INPUTS=228) 랜덤 자극 응답 벡터
    misr_expected.hex         - 위 자극에 대한 기대 시그니처
    ctrl_hd.hex                - AdaptiveTController에 주입할 HD 시퀀스
    ctrl_expected_T.hex        - 매 사이클 기대 current_T
    ctrl_expected_stalled.hex  - 매 사이클 기대 stalled pulse
    top_expected_sig.hex       - lbist_top 통합 시나리오의 기대 MISR 시그니처
    top_expected_T.hex         - lbist_top 통합 시나리오의 기대 current_T
    top_expected_stalled.hex   - lbist_top 통합 시나리오의 기대 stalled pulse

Optuna로 찾은 최적 파라미터를 그대로 사용한다:
    T_init=33, T_max=1024, delta_T=193, K=3, W=34, alpha=0.8410895754890528,
    calib_multiplier=2.183035341991451 (-> calibration_patterns=72)
"""

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prpg_misr import PhaseShifterPRPG, MISR, hamming_distance
from adaptive_controller import AdaptiveTController

VECDIR = os.path.join(os.path.dirname(__file__), "vectors")
os.makedirs(VECDIR, exist_ok=True)

SEED = 0xACE1

OPT = dict(T_init=33, T_max=1024, delta_T=193, K=3, W=34,
           alpha=0.8410895754890528, calibration_patterns=72)

PRPG_NUM_BITS = 214     # s5378 PI 수 (실제 프로젝트 회로 폭)
MISR_NUM_INPUTS = 228   # s5378 PO 수
TOP_WIDTH = 63          # top 통합 테스트용 (response = PRPG pattern 루프백).
                        # 16의 배수를 피한다: phase-shifter의 offset 공식이 16-주기라
                        # 폭이 16의 배수면 매 채널이 짝수 번 XOR-fold되어 항상 0으로
                        # 상쇄되는 특수 케이스가 되고, 그러면 misr의 same-edge 타이밍
                        # 버그(prpg.v의 next_pattern 관련 주석 참고)가 우연히 가려진다.

PRPG_N = 300
MISR_N = 300
CTRL_N = 600
TOP_N = 600


def hexdump(path, values, nibbles):
    with open(path, "w") as f:
        for v in values:
            f.write(f"{v:0{nibbles}x}\n")


def gen_prpg_ref():
    prpg = PhaseShifterPRPG(num_bits=PRPG_NUM_BITS, seed=SEED)
    nibbles = (PRPG_NUM_BITS + 3) // 4
    vals = []
    for _ in range(PRPG_N):
        bits = prpg.next_pattern()
        v = 0
        for i, b in enumerate(bits):
            if b:
                v |= (1 << i)
        vals.append(v)
    hexdump(os.path.join(VECDIR, "prpg_ref.hex"), vals, nibbles)
    print(f"[prpg] {PRPG_N} cycles, width={PRPG_NUM_BITS}, seed=0x{SEED:04X}")


def gen_misr_ref():
    misr = MISR(num_inputs=MISR_NUM_INPUTS)
    rng = random.Random(0xBEEF)
    stim_nibbles = (MISR_NUM_INPUTS + 3) // 4
    stim_vals, sig_vals = [], []
    for _ in range(MISR_N):
        v = rng.getrandbits(MISR_NUM_INPUTS)
        bits = [(v >> i) & 1 for i in range(MISR_NUM_INPUTS)]
        sig = misr.compress(bits)
        stim_vals.append(v)
        sig_vals.append(sig)
    hexdump(os.path.join(VECDIR, "misr_stimulus.hex"), stim_vals, stim_nibbles)
    hexdump(os.path.join(VECDIR, "misr_expected.hex"), sig_vals, 4)
    print(f"[misr] {MISR_N} cycles, num_inputs={MISR_NUM_INPUTS}")


def make_hd_sequence(n, rng):
    """calibration 구간엔 활동적인(높은) HD, 이후엔 낮은 HD로 떨어뜨려
    stall/T-escalation이 실제로 여러 번 트리거되도록 설계한 시퀀스."""
    seq = []
    for i in range(n):
        if i < OPT["calibration_patterns"]:
            seq.append(rng.randint(11, 15))
        else:
            # 서서히 감쇠하다가 낮은 대역에서 흔들리도록
            decay_point = OPT["calibration_patterns"] + 20
            if i < decay_point:
                seq.append(rng.randint(6, 10))
            else:
                seq.append(rng.randint(1, 4))
    return seq


def gen_ctrl_ref():
    rng = random.Random(0xC0FFEE)
    hd_seq = make_hd_sequence(CTRL_N, rng)

    ctrl = AdaptiveTController(**OPT)
    T_vals, stalled_vals = [], []
    for i, hd in enumerate(hd_seq, start=1):
        stalled = ctrl.update(hd, misr_width=16, pattern_index=i)
        T_vals.append(ctrl.current_T())
        stalled_vals.append(1 if stalled else 0)

    hexdump(os.path.join(VECDIR, "ctrl_hd.hex"), hd_seq, 2)
    hexdump(os.path.join(VECDIR, "ctrl_expected_T.hex"), T_vals, 3)
    hexdump(os.path.join(VECDIR, "ctrl_expected_stalled.hex"), stalled_vals, 1)
    print(f"[ctrl] {CTRL_N} cycles, transitions={len(ctrl.transition_log)}, "
          f"final_T={ctrl.current_T()}")
    for (p, oldT, newT) in ctrl.transition_log:
        print(f"        pattern {p}: T {oldT} -> {newT}")


def gen_top_ref():
    """lbist_top 시나리오: PRPG 패턴을 그대로 MISR의 response로 루프백
    (실제 CUT이 없으므로 데이터패스/제어 통합 검증용 단순화)."""
    prpg = PhaseShifterPRPG(num_bits=TOP_WIDTH, seed=SEED)
    misr = MISR(num_inputs=TOP_WIDTH)
    ctrl = AdaptiveTController(**OPT)

    prev_sig = None
    sig_vals, T_vals, stalled_vals = [], [], []
    for p in range(1, TOP_N + 1):
        pattern_bits = prpg.next_pattern()
        sig = misr.compress(pattern_bits)
        hd = 0 if prev_sig is None else hamming_distance(sig, prev_sig)
        prev_sig = sig
        stalled = ctrl.update(hd, misr_width=16, pattern_index=p)
        sig_vals.append(sig)
        T_vals.append(ctrl.current_T())
        stalled_vals.append(1 if stalled else 0)

    hexdump(os.path.join(VECDIR, "top_expected_sig.hex"), sig_vals, 4)
    hexdump(os.path.join(VECDIR, "top_expected_T.hex"), T_vals, 3)
    hexdump(os.path.join(VECDIR, "top_expected_stalled.hex"), stalled_vals, 1)
    print(f"[top] {TOP_N} cycles, width={TOP_WIDTH}, transitions={len(ctrl.transition_log)}, "
          f"final_T={ctrl.current_T()}")


if __name__ == "__main__":
    gen_prpg_ref()
    gen_misr_ref()
    gen_ctrl_ref()
    gen_top_ref()
    print("\nAll reference vectors written to", VECDIR)
