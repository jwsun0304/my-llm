"""
fault_collapse.py
------------------
등가 결함(equivalence fault) collapsing.

DFT 교과서에 나오는 표준 "구조적 등가 + fanout-free 라인" collapsing
규칙을 구현한다. 결함 리스트를 줄이면서도 검출 결과의 정확성은
그대로 유지한다 (등가 결함들은 항상 함께 검출되므로, 대표 결함
하나만 시뮬레이션해도 커버리지 계산 결과가 동일하다).

핵심 규칙 (모두 "그 신호선이 정확히 하나의 게이트에만 연결된 경우",
즉 fanout == 1 인 경우에만 적용 — fanout > 1인 stem 라인은 그 라인의
결함이 여러 branch에 동시에 영향을 주므로 안전하게 collapsing할 수
없다):

    AND(a,b,...)  -> 출력 SA0 은 각 입력의 SA0 과 등가.
                     (입력 하나라도 0이면 출력이 0이 되므로)
                     => fanout==1인 입력의 SA0 결함을 제거하고,
                        게이트 출력의 SA0 결함으로 대표한다.
    NAND(a,b,...) -> 출력 SA1 은 각 입력의 SA0 과 등가. (대칭 규칙)
    OR(a,b,...)   -> 출력 SA1 은 각 입력의 SA1 과 등가.
    NOR(a,b,...)  -> 출력 SA0 은 각 입력의 SA1 과 등가.
    NOT(a)        -> 출력 SA0 <-> 입력 SA1,  출력 SA1 <-> 입력 SA0.
                     (fanout==1이면 입력의 두 결함 모두 제거)
    BUFF(a)       -> 출력 SA0 <-> 입력 SA0,  출력 SA1 <-> 입력 SA1.
    XOR/XNOR      -> 단순 국소 등가 규칙이 없어 collapsing하지 않는다.

주의: 이는 "국소(local) 단일-게이트 등가 collapsing"만 구현한 것으로,
dominance collapsing이나 재수렴 팬아웃(reconvergent fanout)을 고려한
고급 checkpoint 기반 collapsing은 포함하지 않는다. 따라서 본 모듈이
만드는 결함 수는 상용 ATPG 툴의 결과보다는 많고, collapsing을 전혀
하지 않은 baseline보다는 적은, 중간 수준의 실용적 근사치이다.
"""

from fault_sim import Fault


def compute_fanout(circuit):
    """각 신호선이 몇 개의 '관측 지점'에 연결되는지 센다:
    (a) 이 라인을 fanin으로 쓰는 게이트 수 + (b) 원시 출력(primary output)
    이면 +1. 원시 출력은 그 자체로 독립적인 관측 지점이므로, 게이트
    fanout이 1이더라도 원시 출력이면 별도로 직접 관측 가능하다 —
    즉 fanout==1로 오인해 그 라인의 결함을 다른 게이트 출력 결함과
    묶어버리면(collapsing) 안 된다. 이 함수는 그 경우를 fanout>=2로
    처리해 collapsing 대상에서 제외한다."""
    fanout = {line: 0 for line in list(circuit.inputs) + list(circuit.order)}
    for line in circuit.order:
        _, fanins = circuit.gates[line]
        for fi in fanins:
            fanout[fi] = fanout.get(fi, 0) + 1
    for out_line in circuit.outputs:
        fanout[out_line] = fanout.get(out_line, 0) + 1
    return fanout


def build_fault_list_collapsed(circuit, verbose: bool = True):
    fanout = compute_fanout(circuit)

    all_faults = set()
    for line in list(circuit.inputs) + list(circuit.order):
        all_faults.add((line, 0))
        all_faults.add((line, 1))

    original_count = len(all_faults)

    for line in circuit.order:
        gtype, fanins = circuit.gates[line]

        if gtype == "AND":
            for fi in fanins:
                if fanout.get(fi, 0) == 1:
                    all_faults.discard((fi, 0))
        elif gtype == "NAND":
            for fi in fanins:
                if fanout.get(fi, 0) == 1:
                    all_faults.discard((fi, 0))
        elif gtype == "OR":
            for fi in fanins:
                if fanout.get(fi, 0) == 1:
                    all_faults.discard((fi, 1))
        elif gtype == "NOR":
            for fi in fanins:
                if fanout.get(fi, 0) == 1:
                    all_faults.discard((fi, 1))
        elif gtype == "NOT":
            fi = fanins[0]
            if fanout.get(fi, 0) == 1:
                all_faults.discard((fi, 0))
                all_faults.discard((fi, 1))
        elif gtype in ("BUFF", "BUF"):
            fi = fanins[0]
            if fanout.get(fi, 0) == 1:
                all_faults.discard((fi, 0))
                all_faults.discard((fi, 1))
        # XOR/XNOR: no collapsing

    faults = [Fault(line, sv) for (line, sv) in sorted(all_faults)]

    if verbose:
        reduced = original_count - len(faults)
        pct = reduced / original_count * 100.0 if original_count else 0.0
        print(f"[fault_collapse] {original_count} -> {len(faults)} faults "
              f"({reduced} removed, {pct:.1f}% reduction)")

    return faults


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from bench_parser import parse_bench
    from fault_sim import build_fault_list

    path = sys.argv[1] if len(sys.argv) > 1 else "../benchmarks/s5378.bench"
    c = parse_bench(path)
    uncollapsed = build_fault_list(c)
    collapsed = build_fault_list_collapsed(c, verbose=False)
    print(f"circuit: {c.summary()}")
    print(f"uncollapsed faults: {len(uncollapsed)}")
    print(f"collapsed faults:   {len(collapsed)}")
    print(f"reduction: {(1 - len(collapsed)/len(uncollapsed))*100:.1f}%")
