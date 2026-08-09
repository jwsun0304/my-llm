"""
adaptive_controller.py
-----------------------
논문 "MISR Transition Activity 기반 Adaptive T-period 제어 기법"의
핵심 알고리즘을 그대로 구현한다.

- Instantaneous HD: 연속된 두 MISR 시그니처 간 Hamming Distance
- Sliding window 평균 avg_hd (window 크기 W)
- avg_hd < threshold(α * max_HD) 상태가 K회 연속되면 "stall" 판정
- stall 감지 시:
      current_T <- min(current_T + delta_T, T_MAX)
- Fixed-T 컨트롤러는 그냥 T를 고정하고 아무 것도 갱신하지 않는 것으로
  구현한다 (동일한 인터페이스를 공유해서 실험 코드에서 교체 가능하게).
"""

from collections import deque


class BaseTController:
    """공통 인터페이스: update(hd) 호출 시 stall 여부와 현재 T를 반환."""

    def current_T(self) -> int:
        raise NotImplementedError

    def update(self, hd: int, misr_width: int = 16):
        raise NotImplementedError


class FixedTController(BaseTController):
    def __init__(self, T: int):
        self.T = T

    def current_T(self) -> int:
        return self.T

    def update(self, hd: int, misr_width: int = 16, pattern_index: int = None):
        return False  # stall 개념 없음, 전환 없음


class AdaptiveTController(BaseTController):
    """
    논문 표1 파라미터 기본값을 그대로 사용:
        T_INIT=128, T_MAX=1024, delta_T=128, K=3, W=16, alpha=0.95

    구현 note (원 논문과의 차이점):
        원 논문은 threshold를 회로/설계에 맞춰 튜닝된 고정값으로 사용한다.
        본 재현 구현에서는 "GSS 그룹 프리징" 모사 구조 특성상 MISR HD의
        실제 baseline이 이상적인 misr_width/2 가정과 다를 수 있으므로,
        시뮬레이션 시작 직후 calibration_patterns 구간 동안 관측된 HD의
        평균을 baseline으로 삼고 threshold = alpha * baseline 으로 정의한다.
        이 calibration 구간 동안에는 stall 판정을 하지 않는다
        (즉, 초반 짧은 warm-up 이후부터 saturation 감지를 시작한다).
    """

    def __init__(self, T_init: int = 128, T_max: int = 1024, delta_T: int = 128,
                 K: int = 3, W: int = 16, alpha: float = 0.95,
                 calibration_patterns: int = None):
        self.T = T_init
        self.T_max = T_max
        self.delta_T = delta_T
        self.K = K
        self.W = W
        self.alpha = alpha
        # calibration 구간은 최소 T_init보다 길게 잡아, escalation이
        # 시작되기 전에 T_init 주기로 최소 한 번은 실제 그룹 전환이
        # 일어날 기회를 보장한다. 그렇지 않으면 HD가 조기에 낮게 관측될 때
        # 그룹이 한 번도 짧은 주기로 돌아보기 전에 T가 치솟아버려,
        # Fixed-T(T_max)와 사실상 동일한 스케줄로 붕괴해버리는 문제가 있다.
        self.calibration_patterns = calibration_patterns if calibration_patterns is not None else int(T_init * 1.5)

        self.hd_window = deque(maxlen=W)
        self.consecutive_low = 0
        self.transition_log = []   # (pattern_index, old_T, new_T)

        self._calib_hds = []
        self._baseline = None
        self._n_seen = 0

    def current_T(self) -> int:
        return self.T

    def update(self, hd: int, misr_width: int = 16, pattern_index: int = None):
        self._n_seen += 1

        # ---- calibration 구간: baseline HD만 수집, stall 판정 없음 ----
        if self._baseline is None:
            self._calib_hds.append(hd)
            if self._n_seen >= self.calibration_patterns:
                self._baseline = sum(self._calib_hds) / len(self._calib_hds)
                if self._baseline <= 0:
                    self._baseline = misr_width / 2.0  # fallback
            self.hd_window.append(hd)
            return False

        self.hd_window.append(hd)
        avg_hd = sum(self.hd_window) / len(self.hd_window)
        threshold = self.alpha * self._baseline
        # baseline은 "정상적으로 새 정보가 계속 들어올 때"의 평균 HD이고,
        # avg_hd가 그보다 alpha배 이하로 떨어지면 (=시그니처 변화가 둔화되면)
        # coverage saturation 경향으로 해석한다.

        stalled = False
        if avg_hd < threshold:
            self.consecutive_low += 1
            if self.consecutive_low >= self.K:
                old_T = self.T
                self.T = min(self.T + self.delta_T, self.T_max)
                if self.T != old_T:
                    self.transition_log.append((pattern_index, old_T, self.T))
                    stalled = True
                self.consecutive_low = 0
        else:
            self.consecutive_low = 0

        return stalled
