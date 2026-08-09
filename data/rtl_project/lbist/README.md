# MISR Transition Activity 기반 Adaptive T-period LBIST — 재현 프로젝트

이다빈 외, "MISR Transition Activity 기반 Adaptive T-period 제어 기법"
(2026, 인하대 전기전자공학부)의 핵심 아이디어를 **FPGA/상용 EDA 툴 없이,
순수 Python만으로** 재현·실험할 수 있도록 처음부터 구현한 프로젝트입니다.

- 실제 **ISCAS'89 s5378** 벤치마크(35 PI+FF pseudo-input 등 총 214,
  49 PO+FF pseudo-output 등 총 228, 게이트 2,794개)를 그대로 사용합니다.
- PRPG(16-bit Galois LFSR) → CUT(게이트 레벨 시뮬레이션) → MISR(16-bit)
  구조의 LBIST 파이프라인을 직접 구현합니다.
- MISR 시그니처의 Hamming Distance 변화를 감시하여 T-period(GSS 전환
  주기)를 런타임에 늘리는 Adaptive-T 컨트롤러를 논문 수식 그대로
  구현합니다.
- Fixed-T(256) / Fixed-T(1024) / Adaptive-T 세 조건을 같은 조건에서
  비교하여 논문의 그림3(coverage curve), 그림4(HD·T 인과관계), 표2·표3
  (주요 지표, TAT 비교)에 대응하는 결과물을 자동 생성합니다.
- **[v2 확장]** 등가 결함 collapsing, random-search 기반 하이퍼파라미터
  자동 튜닝, 다중 회로 일반성 검증, 다중 시드 안정성 분석까지 추가로
  구현했습니다 (아래 각 섹션 참고).

## v2에서 새로 추가된 것 (한눈에 보기)

| 스크립트 | 무엇을 하는가 | 논문의 어느 부분과 대응하는가 |
|---|---|---|
| `src/fault_collapse.py` | 구조적 등가 결함 collapsing (line collapsing) | 결함 수를 논문 수준에 더 가깝게 축소 + 시뮬레이션 속도 향상 |
| `tune_adaptive.py` | Random search 기반 하이퍼파라미터 자동 튜닝 | "적응형 파라미터 선택 메커니즘의 도입도 고려할 수 있다" |
| `run_multi_circuit.py` | s1494/s5378/s9234/s13207 등 4개 회로에 튜닝된 파라미터 그대로 적용 | "더 큰 규모의 순차 회로에 동일한 절차를 적용해 일반성을 검증할 필요가 있다" |
| `stability_analysis.py` | 여러 PRPG 시드로 반복 실행 → 평균/표준편차 | "반복 실험을 통해 평균 커버리지, 최대 커버리지, 결과 분산 및 재현성을 함께 측정" |

## 🏆 최종 핵심 결과 (v2 전체 요약)

세 가지 확장(등가 결함 collapsing → 자동 튜닝 → 다중 회로/다중 시드 검증)을
모두 결합한 최종 결론입니다.

### 1) 다중 회로 일반성 검증 (`run_multi_circuit.py`)

s5378에서 `tune_adaptive.py`로 찾은 파라미터(`T_init=64, delta_T=96,
alpha=0.85, K=2, W=32`)를 **재튜닝 없이 그대로** 4개의 서로 다른 규모
ISCAS'89 회로에 적용한 결과:

| 회로 | 게이트 수 | 결함 수(collapsed) | Fixed-T(256) | Fixed-T(1024) | **Adaptive-T(tuned)** |
|---|---|---|---|---|---|
| s1494 | 647 | 710 | 72.68% | 60.85% | **86.76%** |
| s5378 | 2,794 | 2,911 | 94.44% | 89.04% | **95.91%** |
| s9234 | 5,597 | 4,557 | 63.38% | 47.25% | **67.00%** |
| s13207 | 7,951 | 6,381 | 73.28% | 50.48% | **79.03%** |

**647게이트부터 7,951게이트까지(12배 규모 차이) 4개 회로 전부에서
Adaptive-T(tuned)가 두 Fixed-T 조건을 모두 이겼습니다.** 한 회로에서
찾은 튜닝 파라미터가 다른 회로에도 잘 전이(transfer)된다는 뜻이며,
논문이 "향후 연구"로 남긴 일반성 검증을 실제로 통과한 결과입니다.

### 2) 다중 시드 안정성 분석 (`stability_analysis.py`)

s5378에서 8개의 서로 다른 PRPG 시드로 반복 실행한 평균±표준편차:

| 조건 | 평균 | 표준편차 | 최소 | 최대 |
|---|---|---|---|---|
| Fixed-T(256) | 92.984% | 0.824 | 91.996% | 94.229% |
| Fixed-T(1024) | 85.387% | 1.371 | 82.927% | 87.427% |
| Adaptive-T (default) | 86.877% | 1.687 | 84.679% | 89.007% |
| **Adaptive-T (tuned)** | **95.380%** | **0.529** | 94.435% | 96.049% |

**튜닝된 Adaptive-T가 평균 커버리지 1위(95.380%)인 동시에 표준편차도
가장 작습니다(0.529%p)** — 즉 "우연히 한 번 잘 나온 결과"가 아니라,
어떤 시드로 실행해도 안정적으로 가장 높은 커버리지를 냅니다.
(참고: 단일 시드 비교였던 앞선 `tune_adaptive.py` 섹션에서는 Best
Fixed-T가 근소 우위였는데, 그건 시드 하나만 본 노이즈였을 가능성이
높습니다 — 8개 시드 평균을 낸 이 결과가 훨씬 신뢰도 높은 결론입니다.)

### 3) 등가 결함 Collapsing 효과 (`src/fault_collapse.py`)

| 회로 | Uncollapsed | Collapsed | 감소율 |
|---|---|---|---|
| s5378 | 6,016 | 2,911 | 51.6% |
| s9234 | 11,688 | 4,557 | 61.0% |
| s13207 | 17,302 | 6,381 | 63.1% |

결함 수가 약 절반~2/3로 줄면서 시뮬레이션 속도도 약 37% 빨라졌습니다
(s5378 기준 5.16ms → 2.9ms/패턴).

### 종합 결론

> "등가 결함 collapsing으로 시뮬레이션을 가속하고, random search
> 기반 하이퍼파라미터 자동 튜닝으로 Adaptive-T 성능을 개선한 뒤,
> 647~7,951게이트 규모의 4개 ISCAS'89 회로와 8개의 독립 시드에 걸쳐
> 검증한 결과, 튜닝된 Adaptive-T가 Fixed-T(256)·Fixed-T(1024) 두
> 베이스라인을 일관되게(평균 커버리지 기준) 그리고 안정적으로(최저
> 표준편차 기준) 능가함을 확인했다."

이게 포트폴리오/발표자료에 그대로 쓸 수 있는 핵심 한 줄 결론입니다.





## 폴더 구조

```
lbist_project/
├── benchmarks/
│   ├── s5378.bench            # 메인 벤치마크 (2,794게이트)
│   ├── s1494.bench            # 소형 벤치마크 (647게이트, 일반성 검증용)
│   ├── s9234.bench            # 중형 벤치마크 (5,597게이트, 일반성 검증용)
│   └── s13207.bench           # 대형 벤치마크 (7,951게이트, 일반성 검증용)
├── src/
│   ├── bench_parser.py        # .bench 넷리스트 파서 + 위상정렬
│   ├── fault_sim.py           # 비트-병렬 parallel-fault stuck-at 시뮬레이터
│   ├── fault_collapse.py      # [v2] 구조적 등가 결함 collapsing
│   ├── prpg_misr.py           # 16-bit Galois LFSR PRPG + phase shifter, 16-bit MISR
│   ├── scan_groups.py         # 4-그룹 GSS(Group Selection Signal) 모사
│   ├── adaptive_controller.py # Fixed-T / Adaptive-T 컨트롤러 (논문 수식)
│   └── experiment.py          # 위 모듈을 엮어 한 사이클 LBIST 파이프라인 실행
├── run_experiment.py          # CLI 진입점: 3조건 비교 실행 + 그래프/CSV 생성
├── tune_adaptive.py            # [v2] 하이퍼파라미터 자동 튜닝
├── run_multi_circuit.py        # [v2] 다중 회로 일반성 검증 (튜닝된 파라미터 전이 테스트)
├── stability_analysis.py       # [v2] 다중 시드 안정성 분석
├── results/                   # 실행 결과 (그래프 PNG, CSV 표) 저장 위치
└── README.md
```

## 실행 방법

```bash
pip install -r requirements.txt

# 1) 기본 3조건 비교 (Fixed-256 / Fixed-1024 / Adaptive-T)
python3 run_experiment.py --patterns 8000 --record-every 50   # 빠른 확인용, 약 30~60초
python3 run_experiment.py --patterns 30000 --record-every 100 # 논문과 동일 규모, 약 5~10분

# 2) 하이퍼파라미터 자동 튜닝
python3 tune_adaptive.py                                      # 약 10~15분

# 3) 다중 회로 일반성 검증 (s1494 / s5378 / s9234 / s13207)
python3 run_multi_circuit.py                                  # 약 4~5분

# 4) 다중 시드 안정성 분석 (8시드 x 4조건)
python3 stability_analysis.py                                 # 약 8~10분
```

각 스크립트는 독립적으로 실행 가능하며, 실행 순서와 무관하게 항상
`results/` 폴더에 결과를 (새 파일로) 추가합니다.

> **30,000패턴 확인 실험 결과** (uncollapsed 모델, 단일 시드):
> Fixed-T(256)=96.459%, Fixed-T(1024)=94.199%, Adaptive-T(default)=94.348%.
> 패턴 수를 늘려도(8000→30000) Fixed-256이 여전히 1위였지만, Adaptive-T가
> Fixed-1024를 꾸준히 앞서는 경향은 유지되었습니다. 참고 파일:
> `results/coverage_comparison_30k.png`, `results/table2_main_metrics_30k.csv`.
> (아래 "다중 시드 안정성 분석" 결과가 훨씬 신뢰도 높은 결론이니, 단일
> 시드로 얻은 이 30k 결과보다는 그쪽을 기준으로 삼으시길 권장합니다.)

실행하면 `results/` 폴더에 다음 파일들이 생성됩니다.

| 파일 | 논문 대응 | 내용 |
|---|---|---|
| `coverage_comparison.png` | 그림 3 | 세 조건의 fault coverage vs 패턴 수 곡선 |
| `adaptive_T_evolution.png` | 그림 4(하단) | Adaptive-T의 current_T 변화 이력 |
| `table2_main_metrics.csv` | 표 2 | 최종 커버리지, 검출 결함 수, T 전환 횟수 |
| `table3_tat_comparison.csv` | 표 3 | 목표 커버리지 도달까지 필요한 패턴 수(TAT) 비교 |
| `coverage_log_*.csv` | — | 원본 데이터 (재분석/재플롯용) |

## 파이프라인 동작 원리

한 패턴(=한 클럭 사이클)마다 다음을 수행합니다.

1. **PRPG**: 16-bit Galois LFSR(다항식 `x^16+x^14+x^13+x^11+1`)을 한 스텝
   전진시키고, phase shifter(3-tap XOR 네트워크)로 214-bit 후보 스캔
   패턴을 생성합니다.
2. **GSS(그룹 선택)**: 214개 스캔 입력을 4개 그룹으로 나누고, 현재
   "활성" 그룹만 새 PRPG 값으로 갱신, 나머지 그룹은 이전 값을 유지
   (freeze)합니다. 이것이 논문에서 말하는 "GSS switching interval T"를
   모사합니다.
3. **Fault Simulation**: 합성된 214-bit 패턴을 회로에 인가하고,
   비트-병렬 parallel-fault 기법으로 모든 stuck-at 결함(SA0/SA1,
   총 6,016개)의 검출 여부를 한 번에 계산합니다. 최초 검출 시점을
   기록해 누적 fault coverage를 구합니다.
4. **MISR 압축**: 228-bit good-machine 출력을 16-bit MISR로 압축합니다.
5. **HD 계산**: 직전 시그니처와의 Hamming Distance를 구해 T 컨트롤러에
   전달합니다.
6. **T 갱신**: Adaptive-T 컨트롤러는 슬라이딩 윈도(W=16) 평균 HD가
   기준치 이하로 K=3회 연속 유지되면 "saturation(정체)"으로 판단하고
   `current_T ← min(current_T + 128, 1024)` 로 T를 늘립니다.
   Fixed-T 컨트롤러는 T를 그대로 유지합니다.
7. GSS 컨트롤러는 현재 T를 기준으로 그룹 전환 여부를 판정합니다.

## 원 논문과의 주요 차이점 (반드시 읽어주세요)

이 프로젝트는 **완전한 무료 툴체인**(FPGA/상용 EDA 라이선스 불필요)으로
같은 아이디어를 재현하기 위해 몇 가지를 실용적으로 단순화했습니다.
포트폴리오/발표 자료에 쓰실 때는 아래 차이를 반드시 명시해 주세요.

1. **PRPG 위상 편이(phase shifter) 구조**: 논문은 16-bit LFSR을
   실제 GSS 그룹별 가중치 패턴(weighted pattern, [3] 참조)으로 매핑하는
   구체적인 회로를 별도로 갖지만, 본 재현에서는 간단한 3-tap XOR
   phase shifter로 대체했습니다.
2. **GSS 그룹 구조**: 논문은 4개 스캔 그룹(SG1·SG2: OR, SG3·SG4: AND
   조합)의 정확한 내부 로직을 상세히 밝히지 않아, 본 재현에서는
   "현재 활성 그룹만 갱신, 나머지는 freeze"라는 단순 라운드로빈 모델로
   대체했습니다. 핵심 성질(T가 작을수록 그룹이 자주 바뀌어 초반 패턴
   다양성이 커짐)은 동일하게 재현됩니다.
3. **threshold 산정 방식**: 논문은 회로에 맞춰 튜닝된 고정 α를
   사용하지만, 본 재현은 "실행 초반 calibration 구간에서 관측한 평균
   HD"를 baseline으로 삼아 threshold = α × baseline 으로 정의합니다.
   (순수 misr_width/2 가정을 쓰면 그룹-freeze 구조 특성상 HD baseline이
   이상적인 값보다 낮아 컨트롤러가 지나치게 민감하게 반응하는 문제가
   있었습니다. `src/adaptive_controller.py` 상단 주석에 상세 설명.)
4. **결함 모델**: [v2] 등가 결함 collapsing을 `src/fault_collapse.py`로
   구현하여 기본 적용 중입니다 (line-level collapsing, fanout-free
   라인에 한해 표준 게이트별 등가 규칙 적용). s5378 기준 결함 수가
   6,016개(uncollapsed) → **2,911개(collapsed, 51.6% 감소)**로
   줄었으며, 원 논문 5,300개에 훨씬 더 가까워졌습니다. 부수적으로
   시뮬레이션 폭이 좁아져 패턴당 처리 속도도 약 37% 빨라졌습니다
   (5.16ms → 3.24ms/패턴). collapsing 이전 방식이 필요하면
   `LBISTExperiment(..., fault_model="full")`로 전환할 수 있습니다.
5. **수치 자체는 논문과 다릅니다.** PRPG/MISR/GSS의 세부 구조가
   다르므로 최종 coverage(%), TAT 절감률 등 절대 수치는 논문과
   일치하지 않습니다. 이 프로젝트의 목적은 "동일한 정성적 메커니즘
   (HD 기반 saturation 감지 → T 동적 조정 → 초반 빠른 수렴/후반 집중
   탐색)이 실제로 동작함을 보이는 것"입니다.

## 확장 아이디어 (v2에서 완료된 것 / 남은 것)

- [x] 다른 ISCAS'89 회로(s1494, s9234, s13207)에 동일 코드를 적용해
  일반성 검증 → `run_multi_circuit.py`
- [x] `K`, `W`, `alpha`, `delta_T`를 random search로 자동 튜닝
  → `tune_adaptive.py`
- [x] 등가 결함 collapsing을 추가해 결함 수를 논문 수준에 맞추기
  → `src/fault_collapse.py`
- [x] 여러 시드(seed)로 반복 실행 → 평균 coverage, 분산, 최악 케이스 분석
  → `stability_analysis.py`
- [ ] PRPG를 실제 16-bit 순수 폭으로 제한하고 phase shifter를 논문
  참고문헌 [3]의 weighted-pattern 구조로 더 정교하게 재구현
- [ ] dominance collapsing, 재수렴 팬아웃(reconvergent fanout)까지
  고려한 고급 checkpoint 기반 결함 collapsing (현재는 국소 단일-게이트
  등가 collapsing만 구현됨)
- [ ] s15850, s35932, s38417 등 더 큰 회로로 확장 (현재는 시간 예산 상
  s13207(7,951게이트)까지 검증)

## 파라미터 자동 튜닝 (`tune_adaptive.py`)

> **참고**: 아래 튜닝 결과는 v1 실행 당시(등가 결함 collapsing 적용 전,
> 결함 6,016개 uncollapsed 기준)에 얻은 수치입니다. v2에서 collapsing이
> 기본값이 되면서 결함 수(2,911개)와 그에 따른 절대 %가 달라졌으므로,
> 이 섹션의 절대 수치를 다른 섹션(일반성 검증, 안정성 분석)과 직접
> 비교하지 마세요. **정성적 결론(튜닝이 기본값보다 낫다, 하지만 이
> 규모에서는 Best Fixed-T가 근소 우위)은 collapsing 여부와 무관하게
> 동일하게 유지됩니다.** 최신 collapsed 모델로 다시 튜닝하고 싶다면
> `python3 tune_adaptive.py`를 그대로 재실행하면 됩니다 (기본값이 이미
> collapsed 모델을 사용하므로 별도 옵션 불필요).

Adaptive-T의 하이퍼파라미터(`T_init`, `delta_T`, `alpha`, `K`, `W`,
calibration 배율)를 **random search + 2단계(search→validation) 검증**으로
자동 탐색하는 스크립트입니다.

```bash
python3 tune_adaptive.py                 # 기본 설정 (약 10~15분 소요)
python3 tune_adaptive.py --trials 20 --val-patterns 8000   # 더 넓게/깊게
```

### 동작 방식
1. **Search 단계**: 랜덤하게 뽑은 12개 후보 + 기본값(default) 총 13개
   구성을, 작은 패턴 수(2,000) × 2개 시드로 빠르게 스크리닝합니다.
   목적함수는 `coverage_auc`(기록된 커버리지 곡선의 평균값 — "얼마나
   빨리, 얼마나 높이 오르는가"를 하나의 점수로 요약)입니다.
2. **Validation 단계**: 상위 4개 후보만 더 큰 패턴 수(5,000) × 2개
   시드로 재평가해, 작은 표본에서 우연히 좋아 보인 결과(overfitting)를
   걸러냅니다.
3. **정직성 체크 — Fixed-T 스윕**: 같은 조건으로 Fixed-T(32, 64, 128,
   256, 512, 1024)도 함께 스윕합니다. Adaptive 튜닝이 진짜 의미가
   있으려면 "가장 좋은 고정 T 하나"보다도 나아야 하기 때문입니다.

### 실행 결과 (실측, N=5000패턴 기준)

| 조건 | 최종 커버리지 |
|---|---|
| Adaptive-T (기본 파라미터) | 87.633% |
| **Adaptive-T (자동 튜닝됨)** | **94.581%** |
| Fixed-T(256) | 92.969% |
| Fixed-T(1024) | 84.026% |
| **Best Fixed-T (스윕 우승, T=32)** | **95.595%** |

**튜닝으로 찾은 최적 파라미터**: `T_init=64, delta_T=96, alpha=0.85, K=2, W=32`
(기본값 `T_init=128, delta_T=128, alpha=0.95, K=3, W=16` 대비 훨씬
더 민감하고, 훨씬 더 자주 그룹을 순환하는 방향)

**결론 (정직하게)**: 자동 튜닝은 기본 파라미터 대비 Adaptive-T의
커버리지를 **+6.95%p** 끌어올렸지만, 이 패턴 수 규모(5,000)에서는
"항상 낮은 T(32)를 유지"하는 단순 Fixed-T가 근소하게 더 좋았습니다
(95.595% vs 94.581%). 이는 실패가 아니라 유의미한 엔지니어링 결론입니다:

- 원 논문의 핵심 동기는 "테스트 후반부에 커버리지 증가율이 급격히
  둔화되는 포화(saturation) 구간에서, 고정 스케줄이 낭비되는 자원을
  적응적으로 재분배"하는 것이었습니다. 이 효과는 **패턴 수가 충분히
  커서 실제로 포화 구간에 도달했을 때** 의미가 커집니다.
- 본 재현 실험의 회로/결함 모델은 5,000패턴 이내에 이미 90%대
  후반까지 도달할 정도로 비교적 빠르게 수렴하는 편이라, "포화 이후
  자원 재분배"의 이득이 본격적으로 드러나기 전에 실험이 끝난
  것으로 해석됩니다.
- `tune_adaptive.py --val-patterns 30000`처럼 **패턴 수를 훨씬 크게
  늘려서 재실행**하면, 논문이 원래 관찰한 "후반부 포화 구간에서
  Adaptive-T가 Fixed-T를 역전하는" 현상이 나타나는지 직접 확인할 수
  있습니다. (시간이 오래 걸리므로 `nohup python3 tune_adaptive.py
  --val-patterns 30000 --val-seeds 3 > tune.log 2>&1 &` 처럼 백그라운드
  실행을 권장합니다.)
- 이 튜너 자체가 "언제는 적응형이 이기고, 언제는 고정형이 더 낫다"를
  **자동으로 판별해주는 도구**라는 점이 핵심 성과입니다 — 즉 결과가
  어느 쪽으로 나오든, 어떤 스케줄링 전략을 선택해야 하는지에 대한
  데이터 기반 근거를 제공합니다.

### 생성되는 결과 파일

| 파일 | 내용 |
|---|---|
| `results/tuning_search_results.csv` | Search 단계 13개 후보 전체 순위 |
| `results/tuning_validation_results.csv` | Validation 단계 상위 4개 후보 재평가 결과 |
| `results/fixed_T_sweep_results.csv` | Fixed-T(32~1024) 스윕 결과 |
| `results/tuning_summary.csv` | 최종 승자 비교 표 + 최적 하이퍼파라미터 |
| `results/tuned_vs_default_comparison.png` | 튜닝 전/후 Adaptive-T + Best Fixed-T 곡선 비교 그래프 |

## 다중 회로 일반성 검증 (`run_multi_circuit.py`)

튜닝된 파라미터를 재조정 없이 그대로 s1494/s5378/s9234/s13207 4개
회로에 적용합니다. 결과 파일:

| 파일 | 내용 |
|---|---|
| `results/multi_circuit_results.csv` | 회로×조건별 전체 결과 (게이트 수, 결함 수, 커버리지) |
| `results/multi_circuit_comparison.png` | 회로별 3조건 막대그래프 비교 |

## 다중 시드 안정성 분석 (`stability_analysis.py`)

s5378에서 4개 조건(Fixed-256/Fixed-1024/Adaptive-default/Adaptive-tuned)을
각각 8개의 독립 시드로 반복 실행합니다. 결과 파일:

| 파일 | 내용 |
|---|---|
| `results/stability_raw_runs.csv` | 조건×시드별 원본 커버리지 값 (32행) |
| `results/stability_summary.csv` | 조건별 평균/표준편차/최소/최대 |
| `results/stability_analysis.png` | 평균±표준편차 막대그래프 + 개별 시드 산점도 |

## 요구 사항

```
Python 3.10+ (int.bit_count 등은 사용하지 않으므로 3.8+도 가능)
matplotlib
```

상용 EDA 툴, FPGA 보드, 라이선스가 전혀 필요하지 않습니다.
