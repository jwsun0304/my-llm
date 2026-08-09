# Optuna 최적화 결과 요약

- 총 trial 수: 30
- Best trial: #22, score=87.3051
- Best params: `{'T_init': 33, 'delta_T': 193, 'alpha': 0.8410895754890528, 'K': 3, 'W': 34, 'calib_multiplier': 2.183035341991451}`
- Best avg_coverage: 87.3081%
- Best avg_speed_frac: 0.3000

## Baseline(논문 기본값) 대비 개선폭

- Baseline config: `{'T_init': 128, 'delta_T': 128, 'alpha': 0.95, 'K': 3, 'W': 16, 'calib_multiplier': 1.5}`
- Baseline avg_coverage: 62.7115%
- Baseline avg_speed_frac: 1.0000
- 개선폭: +24.5967%p (avg coverage)

## Parameter Importance (Optuna fANOVA)

- alpha: 0.7693
- T_init: 0.0723
- delta_T: 0.0475
- W: 0.0446
- calib_multiplier: 0.0420
- K: 0.0244
