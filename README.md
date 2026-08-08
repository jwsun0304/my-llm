# my-llm

nanoGPT 스타일로 처음부터 구현하는 미니 GPT 프로젝트. 학습 목적 + 포트폴리오용.

## 진행 단계

1. [ ] 미니 GPT 구현 (tokenizer, model, train, sample)
2. [ ] Optuna로 하이퍼파라미터 체계적 탐색
3. [ ] (선택) 경량화 / 추론 최적화
4. [ ] 결과 정리

## 실행 환경

- 로컬: 코드 작성 및 문법 확인용
- 학습(GPU): Google Colab (무료 T4)

## 사용법

```bash
pip install -r requirements.txt
python src/prepare_data.py
python src/train.py
python src/sample.py
```
