"""
scan_groups.py
--------------
논문에서 언급된 "4개 스캔 그룹(SG1~SG4)"과 GSS(Group Selection Signal)
순환 구조를 단순화하여 구현한다.

동작 개념:
    - 전체 스캔 입력(214개)을 4개 그룹으로 균등 분할한다.
    - 매 사이클 PRPG가 새 패턴을 만들지만, 그 사이클에 "활성(active)"
      상태인 그룹의 스캔 셀만 새 PRPG 값으로 갱신되고, 나머지 그룹은
      직전 사이클의 값을 그대로 유지(freeze)한다.
    - GSS는 T 사이클마다 다음 그룹으로 라운드로빈 전환된다.

    이 구조는 논문 그림3 설명(초반 구간에서 GSS 전환 주기가 짧을수록
    다양한 스캔 그룹에 패턴이 빠르게 분배되어 초기 고장 검출 속도가
    높아진다)을 그대로 재현하기 위한 것이다. T가 작으면 그룹이 자주
    바뀌어 패턴 다양성이 커지고(exploration), T가 크면 한 그룹에
    오래 머물며 그 그룹에 연결된 고장을 집중적으로 검사한다
    (exploitation).
"""


class ScanGroupController:
    def __init__(self, scan_lines, num_groups: int = 4):
        self.scan_lines = list(scan_lines)
        self.num_groups = num_groups
        self.groups = self._split(self.scan_lines, num_groups)
        self.active_group = 0
        self.cycles_in_group = 0
        # 각 그룹의 현재(frozen) 값 저장
        self.frozen_values = {line: 0 for line in self.scan_lines}

    @staticmethod
    def _split(lines, k):
        n = len(lines)
        size = (n + k - 1) // k
        return [lines[i:i + size] for i in range(0, n, size)]

    def maybe_switch_group(self, T: int):
        """T 사이클이 지나면 다음 그룹으로 전환. 전환되면 True 반환."""
        self.cycles_in_group += 1
        if self.cycles_in_group >= T:
            self.active_group = (self.active_group + 1) % self.num_groups
            self.cycles_in_group = 0
            return True
        return False

    def apply_new_pattern(self, prpg_pattern: list):
        """
        prpg_pattern: len(scan_lines) 폭의 새 PRPG 출력.
        활성 그룹에 해당하는 라인만 새 값으로 갱신하고, 나머지는 동결.
        최종 인가 패턴(dict: line->bit)을 반환한다.
        """
        active_lines = set(self.groups[self.active_group])
        for idx, line in enumerate(self.scan_lines):
            if line in active_lines:
                self.frozen_values[line] = prpg_pattern[idx]
        return dict(self.frozen_values)
