# AI 활용 로그

이 프로젝트를 진행하며 Claude Code를 어떻게 활용했는지, 어떤 판단을 직접 내렸는지 기록한다.
형식: 문제 → 왜 AI가 필요했는지 → AI를 어떻게 활용했는지 → 결과를 어떻게 검증/수정했는지.

## 2026-08-08 ~ 09: 프로젝트 초기 세팅

- **문제**: 딥러닝 경험이 없는 상태에서 LLM을 처음부터 구현해야 함. 처음부터 모든 걸 스스로 설계하면 시간이 오래 걸림.
- **왜 AI 필요**: nanoGPT 구조(트랜스포머, self-attention)의 표준 구현 패턴을 빠르게 확보하고, 그 위에서 직접 원리를 이해하는 방식으로 시간을 절약하기 위함.
- **AI 활용**: Claude Code에게 GPT 모델(`model.py`), 학습 루프(`train.py`), 샘플링 스크립트(`sample.py`)의 초안 작성을 요청.
- **검증/판단**:
  - 로컬 환경(Python 3.14, GPU 없음)에서는 PyTorch 실행이 불가능하다는 걸 직접 확인(`nvidia-smi`, `python -c "import torch"` 실행 결과)한 뒤, 학습은 Colab에서 하고 로컬은 코드 작성 전용으로 쓰기로 판단.
  - 체크포인트 저장/재개 로직(`train.py`의 `start_iter` 처리)이 Colab 세션 끊김에 대비해 필요하다고 판단해 반영.
  - `.claude/settings.local.json`처럼 개인 로컬 설정 파일은 GitHub에 올릴 필요가 없다고 판단해 `.gitignore`에 직접 추가.
  - git 커밋 계정 정보(user.name/email)는 AI가 임의로 설정하지 않고 본인이 직접 실행하도록 함 — 계정 정보는 스스로 확인·결정해야 하는 영역이라고 판단.

## 2026-08-09: Colab 첫 학습 실행

- **문제**: Colab 런타임을 처음에 CPU로 잡아서 학습이 비정상적으로 느렸음(3분 넘게 첫 로그도 안 뜸). 원인이 CPU 런타임인지 출력 버퍼링인지 바로 판단이 안 섰음.
- **AI 활용**: Claude Code가 두 가지 가능성(출력 버퍼링, CPU 런타임)을 모두 제시.
- **검증/판단**: 실제로는 CPU 런타임이 원인이었음 — 직접 런타임 설정 화면을 확인해서 원인을 특정한 뒤 GPU(T4)로 전환. AI 제안 중 버퍼링 쪽(`-u` 옵션)은 부가적으로 적용.
- **결과**: GPU 전환 후 정상 학습 진행, 5000 iter까지 완료.

| iter | train loss | val loss |
|---|---|---|
| 0 | 4.3043 | 4.3071 |
| 1000 | 1.4679 | 1.6721 |
| 2000 | 1.2016 | 1.4951 |
| 2250 | 1.1584 | **1.4882 (val 최저점)** |
| 2750 | 1.0745 | 1.4834 |
| 3000 | 1.0334 | 1.4916 |
| 4000 | 0.8545 | 1.5866 |
| 4999 | 0.6526 | 1.7525 |

- **관찰**: iter 2000 부근부터 train loss는 계속 감소(1.20→0.65)하는데 val loss는 iter 2250~2750 부근에서 최저점(≈1.483~1.488)을 찍은 뒤 다시 상승(4999 기준 1.7525)하는 패턴 확인. 명확한 overfitting — train loss만 보면 계속 좋아지는 것처럼 보이지만 실제 일반화 성능은 iter 2500 전후를 정점으로 악화됨. 작은 모델(n_layer=6, n_embd=384)+작은 데이터(tiny-shakespeare, 약 100만 토큰) 조합, 그리고 early stopping/체크포인트 선택 없이 고정 5000 iter를 끝까지 돌린 설정에서 예상 가능한 현상으로 해석. → Ablation/이후 실험에서는 "val loss 최저점 체크포인트를 최종 모델로 선택"하는 방식을 근거로 설명 가능.

## 2026-08-09: 체크포인트 로딩 오류 (torch.load)

- **문제**: `sample.py`로 최종 체크포인트(iter 4999)를 불러올 때 `_pickle.UnpicklingError: Weights only load failed` 발생. `train.py`의 재개 로직에서도 동일 지점에서 터질 수 있는 문제.
- **원인 분석**: PyTorch 2.6부터 `torch.load`의 `weights_only` 기본값이 `False`→`True`로 바뀌어, 체크포인트에 텐서 외에 `GPTConfig` 객체(`train.py`에서 `"config": config`로 통째로 저장)가 들어있으면 기본 보안 모드에서 차단됨.
- **AI 활용**: Claude Code가 에러 메시지의 원인(파이썬/PyTorch 버전 변경 이력)을 짚어주고 수정안(`weights_only=False` 명시) 제시.
- **검증/판단**: 이 체크포인트는 본인이 직접 학습시켜 만든 신뢰 가능한 파일이므로 `weights_only=False`가 안전하다고 판단해 채택 (외부에서 받은 체크포인트였다면 `add_safe_globals` 방식을 썼을 것). `sample.py`, `train.py` 양쪽 모두 수정 후 Colab에서 `git pull`로 반영해 정상 동작 확인.

## Stage 1 마무리 (nanoGPT 학습 결과)

`sample.py` 생성 샘플(온도 0.8, top_k 40)에서 `GLOUCESTER:`, `BRUTUS:`, `CORIOLANUS:` 등 등장인물 이름과 대사 포맷(콜론, 개행 구조)을 정확히 재현했고 셰익스피어체 어휘/운율도 따라갔으나, 문장 단위 의미는 대부분 맞지 않음 — char-level, 소형 모델(6-layer, 384-dim)이 문법적 패턴은 학습했지만 의미적 일관성까지는 확보하지 못한 상태로 해석. 위 overfitting 관찰과 함께 "표면적 패턴 vs 의미적 이해"를 구분해 설명할 수 있는 근거로 확보.

## 2026-08-10: Stage 2 Ablation 실험 (positional encoding / causal mask 제거)

- **문제**: 모델이 "그냥 돌아가는 것"과 "왜 각 구성요소가 필요한지"는 다른 문제. positional encoding과 causal mask가 실제로 성능에 어떤 영향을 주는지 정량적으로 증명하고 싶었음.
- **왜 AI 필요**: `GPTConfig`에 `use_pos_emb`/`use_causal_mask` 플래그를 추가해 모델 구조를 건드리지 않고 두 요소를 켜고 끌 수 있게 만드는 리팩터링, 그리고 `train.py`의 학습 루프를 `train_model()` 함수로 재사용 가능하게 분리하는 작업을 Claude Code에 요청.
- **AI 활용**: 3개 variant(baseline / no_pos_emb / no_causal_mask)를 동일 조건(1500 iter, 동일 batch/lr)으로 학습하는 `ablation.py` 작성.
- **검증/판단**: Colab 세션이 두 번 끊기면서 처음부터 다시 돌려야 하는 문제를 겪음 → 체크포인트/결과 CSV 저장 경로를 환경변수(`CKPT_DIR`, `RESULTS_DIR`)로 오버라이드 가능하게 만들어 Google Drive에 저장하도록 수정, 이미 끝난 variant는 재실행 시 건너뛰도록 `ablation.py`에 스킵 로직 추가 — 세션 안정성 문제를 직접 겪고 나서 판단해 반영.
- **결과** (각 variant 1500 iter 학습, val loss 기준):

| variant | 최종 train loss | 최종 val loss |
|---|---|---|
| baseline | 1.3403 | 1.5605 |
| no_pos_emb | 1.4063 | 1.6394 |
| no_causal_mask | 0.0101 | **0.0101 (iter 450 부근에서 급락)** |

- **해석**:
  - `no_pos_emb`는 학습 내내 baseline보다 꾸준히 나쁨 (val loss +0.08) — 위치 정보 없이는 토큰 순서를 활용하지 못해 성능이 확실히 저하됨을 확인.
  - `no_causal_mask`는 iter 300~450 사이에서 val loss가 2.4 → 0.016으로 급락 후 0.01 부근에 고정. 이는 성능이 좋아진 게 아니라, causal mask가 없으면 attention이 예측 대상인 다음 위치의 토큰을 직접 참조할 수 있어 모델이 "베끼기" shortcut을 학습한 것 — 즉 정답 유출(label leakage). loss는 거의 0이지만 실제 생성 시점(autoregressive)에는 미래 토큰이 존재하지 않으므로 이 모델은 텍스트 생성 능력이 전혀 없음. → causal mask가 성능 향상용이 아니라 **autoregressive 언어모델이 성립하기 위한 구조적 필수조건**이라는 것을 수치로 증명.

## (진행하며 계속 추가)

- Optuna 탐색 단계에서 AI가 제안한 탐색 범위를 그대로 썼는지, 왜 수정했는지 기록.
- 도메인 특화(RAG) 단계에서 데이터 선정 기준과 그 판단 근거 기록.
