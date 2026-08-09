#!/usr/bin/env python3
"""
gen_misr_coverage_stimulus.py
-------------------------------
misr.v 커버리지 주도 검증 루프용 자극 생성기.

BASE_VECTORS: 기존 tb_misr.v가 쓰는 것과 동일한 방식(random.Random(0xBEEF)
로 뽑은 228-bit 랜덤값 300개)으로 만든 "1회차" 출발점.

EXTRA_VECTORS: 커버리지 리포트를 보고 라운드마다 여기에 직접 벡터를
추가한다. 각 항목에 "몇 회차에, 어떤 커버포인트를 채우려고 추가했는지"
주석을 남겨 감사(audit) 가능하게 한다.

RESET_SCENARIO: cp_rst_mid_enable 커버포인트용 - enable=1인 도중 rst_n이
걸리는 사이클을 하나 끼워넣는다. 이 사이클의 기대 시그니처는 0(리셋이
enable보다 우선)이고, RTL 쪽에서 실제로 이 인덱스에 맞춰 rst_n을 펄스로
걸어야 하므로(tb_misr_coverage.v의 RESET_AT_INDEX와 반드시 동기화) 이
스크립트가 출력하는 reset_at_index 값을 그대로 testbench에 반영한다.

기존 tb/vectors/misr_stimulus.hex / tb_misr.v(단위테스트)는 건드리지
않는다 - 이 커버리지 루프 전용 파일만 별도로 관리한다.
"""

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prpg_misr import MISR

NUM_INPUTS = 228
VECDIR = os.path.join(os.path.dirname(__file__), "vectors")

ALL_ZERO = 0
ALL_ONE = (1 << NUM_INPUTS) - 1


def base_vectors():
    rng = random.Random(0xBEEF)
    return [rng.getrandbits(NUM_INPUTS) for _ in range(300)]


# 라운드별로 추가된 지향성(directed) 벡터. 각 항목: (설명, 값)
EXTRA_VECTORS = [
    # --- 2회차: 1회차 리포트에서 MISS였던 커버포인트를 채우려고 추가 ---
    ("R2: response all-zero 커버 (cp_resp_all_zero)", ALL_ZERO),
    ("R2: response all-one 커버 (cp_resp_all_one)", ALL_ONE),
]

# 2회차: cp_rst_mid_enable 커버용 - enable=1 도중 rst_n을 겹쳐 거는 시나리오.
ADD_RESET_SCENARIO = True


def build_stimulus():
    vecs = base_vectors()
    for _desc, v in EXTRA_VECTORS:
        vecs.append(v)

    reset_at_index = None
    if ADD_RESET_SCENARIO:
        rng2 = random.Random(0xD00D)
        reset_at_index = len(vecs)
        vecs.append(0)   # 리셋과 겹치는 사이클의 response - 리셋이 우선이라 값은 무의미
        vecs.append(rng2.getrandbits(NUM_INPUTS))   # 리셋 직후 정상 동작 재개 확인 #1
        vecs.append(rng2.getrandbits(NUM_INPUTS))   # 리셋 직후 정상 동작 재개 확인 #2

    return vecs, reset_at_index


def compute_expected(stim, reset_at_index):
    misr = MISR(num_inputs=NUM_INPUTS)
    sigs = []
    for idx, v in enumerate(stim):
        if reset_at_index is not None and idx == reset_at_index:
            misr.signature = 0   # RTL: 이 사이클에 rst_n=0이 enable=1과 겹쳐 signature가 강제로 0
            sigs.append(0)
            continue
        bits = [(v >> i) & 1 for i in range(NUM_INPUTS)]
        sigs.append(misr.compress(bits))
    return sigs


def hexdump(path, values, nibbles):
    with open(path, "w") as f:
        for v in values:
            f.write(f"{v:0{nibbles}x}\n")


def main():
    os.makedirs(VECDIR, exist_ok=True)
    stim, reset_at_index = build_stimulus()
    sigs = compute_expected(stim, reset_at_index)

    stim_nibbles = (NUM_INPUTS + 3) // 4
    hexdump(os.path.join(VECDIR, "misr_cov_stimulus.hex"), stim, stim_nibbles)
    hexdump(os.path.join(VECDIR, "misr_cov_expected.hex"), sigs, 4)

    print(f"[gen_misr_coverage_stimulus] N={len(stim)} "
          f"(base=300, extra={len(EXTRA_VECTORS)}, reset_scenario={ADD_RESET_SCENARIO})")
    for desc, v in EXTRA_VECTORS:
        print(f"    + {desc}")
    if reset_at_index is not None:
        print(f"    + reset_at_index={reset_at_index} "
              f"(tb_misr_coverage.v의 RESET_AT_INDEX와 동기화 필요)")


if __name__ == "__main__":
    main()
