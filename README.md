# my-llm

nanoGPT 스타일로 처음부터 구현하는 미니 GPT 프로젝트. 학습 목적 + 포트폴리오용.

## 진행 단계

1. [x] 미니 GPT 구현 (tokenizer, model, train, sample)
2. [ ] Optuna로 하이퍼파라미터 체계적 탐색
3. [ ] (선택) 경량화 / 추론 최적화
4. [ ] 결과 정리

## 실행 환경

- 로컬: 코드 작성 및 문법 확인용
- 학습(GPU): Google Colab (무료 T4)

## 사용법 (로컬, 코드 확인용)

```bash
pip install -r requirements.txt
python src/prepare_data.py
python src/train.py
python src/sample.py
```

## Colab에서 실행 (실제 학습)

Colab 노트북 셀에 아래를 순서대로 실행:

```python
!git clone https://github.com/jwsun0304/my-llm.git
%cd my-llm
!pip install -q -r requirements.txt
!python src/prepare_data.py
!python src/train.py
```

코드 수정 후 최신 버전을 받으려면:

```python
%cd my-llm
!git pull
```
