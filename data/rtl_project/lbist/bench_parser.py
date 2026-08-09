"""
bench_parser.py
----------------
ISCAS'89 .bench 포맷 파서.

.bench 포맷 예:
    INPUT(1)
    OUTPUT(999)
    215 = NOT(1)
    216 = NOR(3,4,5)

full-scan 형태로 배포되는 s*.bench 파일은 순차 회로(FF)를
"의사 입력(pseudo-input) / 의사 출력(pseudo-output)"으로 풀어놓은
조합회로 넷리스트이므로, 조합 로직 시뮬레이터로 그대로 다룰 수 있다.

파서는 다음을 만든다:
    - inputs   : 입력 라인 번호 리스트 (등장 순서)
    - outputs  : 출력 라인 번호 리스트 (등장 순서)
    - gates    : {output_line: (gate_type, [fanin_line, ...])}
    - order    : 위상 정렬된 gate output line 리스트 (평가 순서)
"""

from collections import deque
import re

GATE_RE = re.compile(r"^(\d+)\s*=\s*([A-Za-z]+)\((.*)\)$")
IO_RE = re.compile(r"^(INPUT|OUTPUT)\((\d+)\)$")


class Circuit:
    def __init__(self, inputs, outputs, gates, order):
        self.inputs = inputs          # list[int]
        self.outputs = outputs        # list[int]
        self.gates = gates            # dict[int, (str, list[int])]
        self.order = order            # list[int], topological eval order
        self.num_inputs = len(inputs)
        self.num_outputs = len(outputs)
        self.num_gates = len(gates)

    def summary(self):
        return (f"inputs={self.num_inputs}, outputs={self.num_outputs}, "
                f"gates={self.num_gates}")


def parse_bench(path: str) -> Circuit:
    inputs = []
    outputs = []
    gates = {}          # line -> (gate_type, fanins)

    with open(path, "r") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            m_io = IO_RE.match(line)
            if m_io:
                kind, num = m_io.group(1), int(m_io.group(2))
                if kind == "INPUT":
                    inputs.append(num)
                else:
                    outputs.append(num)
                continue

            m_gate = GATE_RE.match(line)
            if m_gate:
                out_line = int(m_gate.group(1))
                gtype = m_gate.group(2).upper()
                args = [int(a.strip()) for a in m_gate.group(3).split(",") if a.strip() != ""]
                gates[out_line] = (gtype, args)
                continue
            # 알 수 없는 라인은 무시 (예: 빈 주석 등)

    order = _topo_sort(inputs, gates)
    return Circuit(inputs, outputs, gates, order)


def _topo_sort(inputs, gates):
    """Kahn's algorithm 기반 위상 정렬. gates: dict[line] = (type, fanins)."""
    indeg = {line: 0 for line in gates}
    consumers = {line: [] for line in gates}
    input_set = set(inputs)

    for line, (_, fanins) in gates.items():
        for fi in fanins:
            if fi in gates:
                consumers[fi].append(line)
                indeg[line] += 1
            # fi가 input이면 즉시 사용 가능하므로 indegree에 안 잡힘

    queue = deque([line for line, d in indeg.items() if d == 0])
    order = []
    while queue:
        line = queue.popleft()
        order.append(line)
        for nxt in consumers[line]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)

    if len(order) != len(gates):
        missing = set(gates) - set(order)
        raise RuntimeError(f"Cyclic or unresolved netlist! unresolved gates: {list(missing)[:10]}...")

    return order


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "benchmarks/s5378.bench"
    c = parse_bench(path)
    print("Parsed:", c.summary())
    print("First 5 inputs:", c.inputs[:5])
    print("First 5 outputs:", c.outputs[:5])
    print("First 5 gates:", [(l, c.gates[l]) for l in c.order[:5]])
