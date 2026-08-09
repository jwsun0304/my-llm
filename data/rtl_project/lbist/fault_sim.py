"""
fault_sim.py
------------
Bit-parallel "parallel-fault" stuck-at fault 시뮬레이터.

핵심 아이디어 (고전적인 parallel-fault simulation 기법):
    회로의 모든 신호선 값을 하나의 큰 정수(Python big-int)로 표현한다.
    이 정수의 bit-0 은 "good machine"(결함 없는 회로)의 값이고,
    bit-i (i=1..F) 는 "i번째 결함이 주입된 machine"의 값이다.

    AND/OR/NOT 등 불리언 게이트 연산은 비트별로 독립적으로 동작하므로,
    파이썬의 정수 bitwise 연산(&, |, ^, ~) 한 번으로 (F+1)개의 회로를
    동시에 시뮬레이션할 수 있다.

    결함 주입은 "그 결함이 위치한 라인의 계산 결과 중, 그 결함 전용
    비트 위치만 상수값(0 또는 1)으로 덮어쓰기"로 구현한다.

이 방식은 O(1) 회 회로 순회로 전체 결함 리스트에 대한 검출 여부를
한 패턴당 한 번에 계산할 수 있어, 파이썬으로도 수천 개의 stuck-at
결함을 감당할 수 있는 속도를 낸다.
"""

from dataclasses import dataclass


@dataclass
class Fault:
    line: int      # 결함이 위치한 신호선 번호
    stuck_at: int  # 0 또는 1


def build_fault_list(circuit):
    """
    모든 입력선 + 모든 게이트 출력선에 대해 SA0/SA1 결함을 생성한다.
    (line-level stuck-at fault model, 등가 결함 collapsing은 하지 않음)
    """
    faults = []
    all_lines = list(circuit.inputs) + list(circuit.order)
    for line in all_lines:
        faults.append(Fault(line, 0))
        faults.append(Fault(line, 1))
    return faults


class ParallelFaultSimulator:
    """
    한 번 생성하면 회로 구조 + 결함 리스트에 대해 반복적으로
    패턴을 흘려보내며 최초 검출 시점을 기록할 수 있는 시뮬레이터.
    """

    def __init__(self, circuit, faults):
        self.circuit = circuit
        self.faults = faults
        self.num_faults = len(faults)
        self.width = 1 + self.num_faults          # bit0=good, bit1..F=faults
        self.full_mask = (1 << self.width) - 1

        # line -> [(bit_position, stuck_value), ...]
        self.override_map = {}
        for idx, flt in enumerate(faults, start=1):
            self.override_map.setdefault(flt.line, []).append((idx, flt.stuck_at))

        # 결과 기록용
        self.first_detected_at = [None] * self.num_faults  # pattern index (1-based) or None
        self.cumulative_detected_mask = 0                  # bit i(1..F) set => fault i-1 detected
        self.total_patterns_applied = 0

    # ---- 내부 유틸 -----------------------------------------------------
    def _broadcast(self, bit: int) -> int:
        return self.full_mask if bit else 0

    def _apply_overrides(self, line: int, value: int) -> int:
        ov = self.override_map.get(line)
        if not ov:
            return value
        for bitpos, stuck in ov:
            mask = 1 << bitpos
            if stuck == 0:
                value &= ~mask
            else:
                value |= mask
        return value

    # ---- 게이트 함수 -----------------------------------------------------
    def _eval_gate(self, gtype, fanin_values):
        m = self.full_mask
        if gtype == "NOT":
            return (~fanin_values[0]) & m
        if gtype == "BUFF" or gtype == "BUF":
            return fanin_values[0]
        if gtype == "AND":
            v = m
            for x in fanin_values:
                v &= x
            return v
        if gtype == "NAND":
            v = m
            for x in fanin_values:
                v &= x
            return (~v) & m
        if gtype == "OR":
            v = 0
            for x in fanin_values:
                v |= x
            return v
        if gtype == "NOR":
            v = 0
            for x in fanin_values:
                v |= x
            return (~v) & m
        if gtype == "XOR":
            v = 0
            for x in fanin_values:
                v ^= x
            return v
        if gtype == "XNOR":
            v = 0
            for x in fanin_values:
                v ^= x
            return (~v) & m
        raise ValueError(f"Unsupported gate type: {gtype}")

    # ---- 패턴 1개 시뮬레이션 --------------------------------------------
    def simulate_pattern(self, input_bits: dict) -> int:
        """
        input_bits: {input_line: 0/1, ...} (good machine 기준 패턴 값)
        반환값: primary output (good machine, bit0) 리스트 -> 실제로는
                self.last_outputs 에 라인->값(vector) 저장하고,
                good-machine 출력 비트만 뽑아 리스트로 반환한다.
        """
        circuit = self.circuit
        values = {}

        for line in circuit.inputs:
            bit = input_bits.get(line, 0)
            v = self._broadcast(bit)
            v = self._apply_overrides(line, v)
            values[line] = v

        for line in circuit.order:
            gtype, fanins = circuit.gates[line]
            fanin_vals = [values[f] for f in fanins]
            v = self._eval_gate(gtype, fanin_vals)
            v = self._apply_overrides(line, v)
            values[line] = v

        # ---- 결함 검출 계산 (output 라인들에서) ----
        detect_vec = 0
        good_outputs = []
        for line in circuit.outputs:
            v = values[line]
            goodbit = v & 1
            good_outputs.append(goodbit)
            broadcast = self.full_mask if goodbit else 0
            diffmask = v ^ broadcast   # bit i(1..F) = 1 이면 fault i에서 이 output이 good과 다름
            detect_vec |= diffmask

        self.total_patterns_applied += 1
        newly = detect_vec & ~self.cumulative_detected_mask
        if newly:
            # 새로 검출된 결함들의 최초 검출 시점 기록
            idx = 1
            tmp = newly >> 1  # bit0 제외하고 살펴봄
            fault_idx = 0
            while tmp:
                if tmp & 1:
                    if self.first_detected_at[fault_idx] is None:
                        self.first_detected_at[fault_idx] = self.total_patterns_applied
                fault_idx += 1
                tmp >>= 1
            self.cumulative_detected_mask |= detect_vec

        return good_outputs

    def coverage(self) -> float:
        detected = bin(self.cumulative_detected_mask >> 1).count("1")
        return detected / self.num_faults if self.num_faults else 0.0

    def num_detected(self) -> int:
        return bin(self.cumulative_detected_mask >> 1).count("1")
