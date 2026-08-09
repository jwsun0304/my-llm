# Optuna Trial Log — LBIST Adaptive T-period

목적함수: `score = avg_final_coverage - 0.01 * avg_speed_frac` (coverage 우선, 사실상 동률일 때만 speed_frac이 tie-break)

## Trial 0
- 시각: 2026-07-20T22:03:31
- 소요 시간: 117.0s
- 파라미터: `{'T_init': 116, 'delta_T': 245, 'alpha': 0.9122782431253075, 'K': 4, 'W': 11, 'calib_multiplier': 1.3119890406724053}`
- Optuna 판단(근사): exploration (초기 랜덤 샘플링, trial 0 < n_startup_trials=10)
- 결과: avg_coverage=65.0798%  avg_speed_frac=1.0000  score=65.0698
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 58.873 | None | 1.000 | 4 |
  | s5378 | 84.610 | None | 1.000 | 4 |
  | s9234 | 58.240 | None | 1.000 | 4 |
  | s13207 | 58.596 | None | 1.000 | 4 |

## Trial 1
- 시각: 2026-07-20T22:08:29
- 소요 시간: 120.9s
- 파라미터: `{'T_init': 116, 'delta_T': 245, 'alpha': 0.9122782431253075, 'K': 4, 'W': 11, 'calib_multiplier': 1.3119890406724053}`
- Optuna 판단(근사): exploration (초기 랜덤 샘플링, trial 1 < n_startup_trials=10)
- 결과: avg_coverage=65.0798%  avg_speed_frac=1.0000  score=65.0698
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 58.873 | None | 1.000 | 4 |
  | s5378 | 84.610 | None | 1.000 | 4 |
  | s9234 | 58.240 | None | 1.000 | 4 |
  | s13207 | 58.596 | None | 1.000 | 4 |

## Trial 2
- 시각: 2026-07-20T22:09:55
- 소요 시간: 85.4s
- 파라미터: `{'T_init': 45, 'delta_T': 226, 'alpha': 0.8743233534055306, 'K': 5, 'W': 4, 'calib_multiplier': 2.9398197043239884}`
- Optuna 판단(근사): exploration (초기 랜덤 샘플링, trial 2 < n_startup_trials=10)
- 결과: avg_coverage=71.4220%  avg_speed_frac=0.8542  score=71.4134
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 77.606 | 2500 | 0.417 | 5 |
  | s5378 | 83.339 | None | 1.000 | 5 |
  | s9234 | 55.036 | None | 1.000 | 5 |
  | s13207 | 69.707 | None | 1.000 | 5 |

## Trial 3
- 시각: 2026-07-20T22:12:20
- 소요 시간: 144.8s
- 파라미터: `{'T_init': 219, 'delta_T': 79, 'alpha': 0.7527292404900592, 'K': 2, 'W': 17, 'calib_multiplier': 2.049512863264476}`
- Optuna 판단(근사): exploration (초기 랜덤 샘플링, trial 3 < n_startup_trials=10)
- 결과: avg_coverage=76.0263%  avg_speed_frac=0.8875  score=76.0174
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 72.113 | None | 1.000 | 11 |
  | s5378 | 92.717 | None | 1.000 | 0 |
  | s9234 | 62.673 | None | 1.000 | 0 |
  | s13207 | 76.602 | 1100 | 0.550 | 0 |

## Trial 4
- 시각: 2026-07-20T22:14:51
- 소요 시간: 150.4s
- 파라미터: `{'T_init': 129, 'delta_T': 97, 'alpha': 0.87743733946949, 'K': 1, 'W': 17, 'calib_multiplier': 1.7327236865873834}`
- Optuna 판단(근사): exploration (초기 랜덤 샘플링, trial 4 < n_startup_trials=10)
- 결과: avg_coverage=70.2136%  avg_speed_frac=1.0000  score=70.2036
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 65.070 | None | 1.000 | 10 |
  | s5378 | 89.866 | None | 1.000 | 10 |
  | s9234 | 52.842 | None | 1.000 | 10 |
  | s13207 | 73.076 | None | 1.000 | 10 |

## Trial 5
- 시각: 2026-07-20T22:16:52
- 소요 시간: 121.7s
- 파라미터: `{'T_init': 134, 'delta_T': 208, 'alpha': 0.7579053968259243, 'K': 4, 'W': 30, 'calib_multiplier': 1.0929008254399954}`
- Optuna 판단(근사): exploration (초기 랜덤 샘플링, trial 5 < n_startup_trials=10)
- 결과: avg_coverage=81.1896%  avg_speed_frac=0.5208  score=81.1843
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 84.648 | 1400 | 0.233 | 5 |
  | s5378 | 96.324 | 3900 | 0.650 | 0 |
  | s9234 | 65.679 | 2100 | 0.700 | 0 |
  | s13207 | 78.107 | 1000 | 0.500 | 0 |

## Trial 6
- 시각: 2026-07-20T22:18:19
- 소요 시간: 86.6s
- 파라미터: `{'T_init': 168, 'delta_T': 70, 'alpha': 0.718864961965731, 'K': 6, 'W': 47, 'calib_multiplier': 2.6167946962329225}`
- Optuna 판단(근사): exploration (초기 랜덤 샘플링, trial 6 < n_startup_trials=10)
- 결과: avg_coverage=79.5636%  avg_speed_frac=0.8125  score=79.5555
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 84.085 | 4100 | 0.683 | 0 |
  | s5378 | 93.920 | None | 1.000 | 0 |
  | s9234 | 64.384 | 2300 | 0.767 | 0 |
  | s13207 | 75.866 | 1600 | 0.800 | 0 |

## Trial 7
- 시각: 2026-07-20T22:19:48
- 소요 시간: 88.5s
- 파라미터: `{'T_init': 100, 'delta_T': 53, 'alpha': 0.8984275776885255, 'K': 3, 'W': 9, 'calib_multiplier': 1.9903538202225404}`
- Optuna 판단(근사): exploration (초기 랜덤 샘플링, trial 7 < n_startup_trials=10)
- 결과: avg_coverage=72.3534%  avg_speed_frac=1.0000  score=72.3434
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 68.451 | None | 1.000 | 18 |
  | s5378 | 89.179 | None | 1.000 | 18 |
  | s9234 | 60.808 | None | 1.000 | 18 |
  | s13207 | 70.976 | None | 1.000 | 18 |

## Trial 8
- 시각: 2026-07-20T22:21:56
- 소요 시간: 127.8s
- 파라미터: `{'T_init': 39, 'delta_T': 236, 'alpha': 0.7750461946640048, 'K': 4, 'W': 18, 'calib_multiplier': 2.0401360423556216}`
- Optuna 판단(근사): exploration (초기 랜덤 샘플링, trial 8 < n_startup_trials=10)
- 결과: avg_coverage=86.9492%  avg_speed_frac=0.3125  score=86.9461
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 97.887 | 900 | 0.150 | 0 |
  | s5378 | 96.359 | 3800 | 0.633 | 0 |
  | s9234 | 73.031 | 800 | 0.267 | 0 |
  | s13207 | 80.520 | 400 | 0.200 | 0 |

## Trial 9
- 시각: 2026-07-20T22:23:28
- 소요 시간: 91.5s
- 파라미터: `{'T_init': 155, 'delta_T': 73, 'alpha': 0.981179542051722, 'K': 5, 'W': 46, 'calib_multiplier': 2.789654700855298}`
- Optuna 판단(근사): exploration (초기 랜덤 샘플링, trial 9 < n_startup_trials=10)
- 결과: avg_coverage=72.5383%  avg_speed_frac=1.0000  score=72.5283
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 71.408 | None | 1.000 | 12 |
  | s5378 | 87.942 | None | 1.000 | 12 |
  | s9234 | 59.074 | None | 1.000 | 12 |
  | s13207 | 71.729 | None | 1.000 | 12 |

## Trial 10
- 시각: 2026-07-20T22:24:54
- 소요 시간: 86.1s
- 파라미터: `{'T_init': 246, 'delta_T': 157, 'alpha': 0.809109438039618, 'K': 1, 'W': 33, 'calib_multiplier': 2.3804941471382906}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=1.224)
- 결과: avg_coverage=74.8784%  avg_speed_frac=0.9333  score=74.8691
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 66.620 | None | 1.000 | 5 |
  | s5378 | 93.988 | None | 1.000 | 0 |
  | s9234 | 63.902 | 2500 | 0.833 | 0 |
  | s13207 | 75.004 | 1800 | 0.900 | 0 |

## Trial 11
- 시각: 2026-07-20T22:26:21
- 소요 시간: 86.6s
- 파라미터: `{'T_init': 35, 'delta_T': 185, 'alpha': 0.7806251483411977, 'K': 3, 'W': 30, 'calib_multiplier': 1.0179256060258133}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.654)
- 결과: avg_coverage=86.2512%  avg_speed_frac=0.3208  score=86.2480
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 94.930 | 500 | 0.083 | 4 |
  | s5378 | 95.431 | 4300 | 0.717 | 0 |
  | s9234 | 70.880 | 1000 | 0.333 | 0 |
  | s13207 | 83.764 | 300 | 0.150 | 0 |

## Trial 12
- 시각: 2026-07-20T22:27:42
- 소요 시간: 80.7s
- 파라미터: `{'T_init': 35, 'delta_T': 180, 'alpha': 0.8058067267497638, 'K': 3, 'W': 29, 'calib_multiplier': 1.658109434489086}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.462)
- 결과: avg_coverage=81.0006%  avg_speed_frac=0.4042  score=80.9966
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 80.423 | 2500 | 0.417 | 6 |
  | s5378 | 95.431 | 4300 | 0.717 | 0 |
  | s9234 | 64.384 | 1000 | 0.333 | 4 |
  | s13207 | 83.764 | 300 | 0.150 | 0 |

## Trial 13
- 시각: 2026-07-20T22:29:06
- 소요 시간: 84.3s
- 파라미터: `{'T_init': 65, 'delta_T': 148, 'alpha': 0.8073137505062156, 'K': 3, 'W': 24, 'calib_multiplier': 2.3053624004499618}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.506)
- 결과: avg_coverage=80.5862%  avg_speed_frac=0.4000  score=80.5822
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 77.465 | 1400 | 0.233 | 7 |
  | s5378 | 95.912 | 4000 | 0.667 | 0 |
  | s9234 | 70.156 | 1200 | 0.400 | 0 |
  | s13207 | 78.812 | 600 | 0.300 | 0 |

## Trial 14
- 시각: 2026-07-20T22:30:51
- 소요 시간: 104.8s
- 파라미터: `{'T_init': 79, 'delta_T': 197, 'alpha': 0.702790656829779, 'K': 2, 'W': 37, 'calib_multiplier': 1.0141677399487772}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.857)
- 결과: avg_coverage=83.0121%  avg_speed_frac=0.5042  score=83.0070
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 86.338 | 1600 | 0.267 | 1 |
  | s5378 | 95.088 | 5800 | 0.967 | 0 |
  | s9234 | 69.476 | 1300 | 0.433 | 0 |
  | s13207 | 81.147 | 700 | 0.350 | 0 |

## Trial 15
- 시각: 2026-07-20T22:31:56
- 소요 시간: 64.9s
- 파라미터: `{'T_init': 63, 'delta_T': 125, 'alpha': 0.7709596048670332, 'K': 5, 'W': 22, 'calib_multiplier': 1.6200744542112033}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.591)
- 결과: avg_coverage=80.5517%  avg_speed_frac=0.5500  score=80.5462
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 77.606 | 4700 | 0.783 | 8 |
  | s5378 | 95.672 | 3900 | 0.650 | 0 |
  | s9234 | 67.281 | 1400 | 0.467 | 0 |
  | s13207 | 81.649 | 600 | 0.300 | 0 |

## Trial 16
- 시각: 2026-07-20T22:33:42
- 소요 시간: 105.7s
- 파라미터: `{'T_init': 34, 'delta_T': 182, 'alpha': 0.8383932029036517, 'K': 2, 'W': 39, 'calib_multiplier': 1.9938571243740753}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.703)
- 결과: avg_coverage=85.3232%  avg_speed_frac=0.2625  score=85.3206
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 92.958 | 500 | 0.083 | 6 |
  | s5378 | 96.427 | 2300 | 0.383 | 0 |
  | s9234 | 68.817 | 1300 | 0.433 | 0 |
  | s13207 | 83.090 | 300 | 0.150 | 0 |

## Trial 17
- 시각: 2026-07-20T22:35:01
- 소요 시간: 79.0s
- 파라미터: `{'T_init': 86, 'delta_T': 217, 'alpha': 0.7365441105935651, 'K': 6, 'W': 24, 'calib_multiplier': 1.4181537525997028}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.587)
- 결과: avg_coverage=82.2100%  avg_speed_frac=0.5000  score=82.2050
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 89.014 | 1000 | 0.167 | 5 |
  | s5378 | 95.294 | 5100 | 0.850 | 0 |
  | s9234 | 65.767 | 1900 | 0.633 | 0 |
  | s13207 | 78.765 | 700 | 0.350 | 0 |

## Trial 18
- 시각: 2026-07-20T22:36:23
- 소요 시간: 81.7s
- 파라미터: `{'T_init': 58, 'delta_T': 152, 'alpha': 0.7793884779354318, 'K': 4, 'W': 17, 'calib_multiplier': 2.333539387200136}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.412)
- 결과: avg_coverage=77.9949%  avg_speed_frac=0.5875  score=77.9890
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 67.606 | None | 1.000 | 7 |
  | s5378 | 96.153 | 4000 | 0.667 | 0 |
  | s9234 | 67.215 | 1300 | 0.433 | 0 |
  | s13207 | 81.006 | 500 | 0.250 | 0 |

## Trial 19
- 시각: 2026-07-20T22:37:44
- 소요 시간: 80.2s
- 파라미터: `{'T_init': 86, 'delta_T': 232, 'alpha': 0.8399317603779471, 'K': 3, 'W': 41, 'calib_multiplier': 1.7820197228868855}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.651)
- 결과: avg_coverage=78.1607%  avg_speed_frac=0.5917  score=78.1547
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 72.817 | 3200 | 0.533 | 5 |
  | s5378 | 95.294 | 5100 | 0.850 | 0 |
  | s9234 | 65.767 | 1900 | 0.633 | 0 |
  | s13207 | 78.765 | 700 | 0.350 | 0 |

## Trial 20
- 시각: 2026-07-20T22:39:03
- 소요 시간: 79.3s
- 파라미터: `{'T_init': 32, 'delta_T': 254, 'alpha': 0.7909028729177123, 'K': 2, 'W': 27, 'calib_multiplier': 2.5588864835511433}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.529)
- 결과: avg_coverage=85.7075%  avg_speed_frac=0.2292  score=85.7052
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 92.113 | 600 | 0.100 | 4 |
  | s5378 | 96.565 | 2000 | 0.333 | 0 |
  | s9234 | 71.955 | 1000 | 0.333 | 0 |
  | s13207 | 82.197 | 300 | 0.150 | 0 |

## Trial 21
- 시각: 2026-07-20T22:40:26
- 소요 시간: 82.6s
- 파라미터: `{'T_init': 51, 'delta_T': 247, 'alpha': 0.7946059951875618, 'K': 2, 'W': 28, 'calib_multiplier': 2.5870544217894627}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.544)
- 결과: avg_coverage=76.2001%  avg_speed_frac=0.5833  score=76.1943
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 59.155 | None | 1.000 | 4 |
  | s5378 | 94.847 | 5400 | 0.900 | 1 |
  | s9234 | 71.187 | 700 | 0.233 | 0 |
  | s13207 | 79.611 | 400 | 0.200 | 0 |

## Trial 22
- 시각: 2026-07-20T22:41:51
- 소요 시간: 84.4s
- 파라미터: `{'T_init': 33, 'delta_T': 193, 'alpha': 0.8410895754890528, 'K': 3, 'W': 34, 'calib_multiplier': 2.183035341991451}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 개선 성공 (best-so-far 대비 정규화거리=0.516)
- 결과: avg_coverage=87.3081%  avg_speed_frac=0.3000  score=87.3051
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 97.746 | 300 | 0.050 | 2 |
  | s5378 | 96.290 | 4100 | 0.683 | 0 |
  | s9234 | 72.043 | 1100 | 0.367 | 0 |
  | s13207 | 83.153 | 200 | 0.100 | 0 |

## Trial 23
- 시각: 2026-07-20T22:43:10
- 소요 시간: 79.1s
- 파라미터: `{'T_init': 68, 'delta_T': 186, 'alpha': 0.8337137187671008, 'K': 3, 'W': 34, 'calib_multiplier': 2.2604971982622155}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.166)
- 결과: avg_coverage=84.8091%  avg_speed_frac=0.4458  score=84.8046
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 97.042 | 700 | 0.117 | 0 |
  | s5378 | 94.916 | 5300 | 0.883 | 0 |
  | s9234 | 68.356 | 1600 | 0.533 | 0 |
  | s13207 | 78.922 | 500 | 0.250 | 0 |

## Trial 24
- 시각: 2026-07-20T22:44:45
- 소요 시간: 94.4s
- 파라미터: `{'T_init': 51, 'delta_T': 166, 'alpha': 0.7372694542450705, 'K': 4, 'W': 43, 'calib_multiplier': 2.107137950530362}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.482)
- 결과: avg_coverage=84.8733%  avg_speed_frac=0.3333  score=84.8700
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 92.817 | 1200 | 0.200 | 1 |
  | s5378 | 95.878 | 4200 | 0.700 | 0 |
  | s9234 | 71.187 | 700 | 0.233 | 0 |
  | s13207 | 79.611 | 400 | 0.200 | 0 |

## Trial 25
- 시각: 2026-07-20T22:46:04
- 소요 시간: 78.9s
- 파라미터: `{'T_init': 79, 'delta_T': 131, 'alpha': 0.8533714623925386, 'K': 3, 'W': 34, 'calib_multiplier': 1.4844857426298492}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.493)
- 결과: avg_coverage=80.4064%  avg_speed_frac=0.5542  score=80.4009
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 75.915 | 2800 | 0.467 | 8 |
  | s5378 | 95.088 | 5800 | 0.967 | 0 |
  | s9234 | 69.476 | 1300 | 0.433 | 0 |
  | s13207 | 81.147 | 700 | 0.350 | 0 |

## Trial 26
- 시각: 2026-07-20T22:47:26
- 소요 시간: 82.5s
- 파라미터: `{'T_init': 46, 'delta_T': 206, 'alpha': 0.8223607686432061, 'K': 5, 'W': 20, 'calib_multiplier': 1.8856568348427307}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.542)
- 결과: avg_coverage=78.3771%  avg_speed_frac=0.5542  score=78.3716
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 66.761 | None | 1.000 | 5 |
  | s5378 | 97.458 | 2700 | 0.450 | 0 |
  | s9234 | 66.842 | 1700 | 0.567 | 4 |
  | s13207 | 82.448 | 400 | 0.200 | 0 |

## Trial 27
- 시각: 2026-07-20T22:48:45
- 소요 시간: 78.1s
- 파라미터: `{'T_init': 70, 'delta_T': 196, 'alpha': 0.9494390213445787, 'K': 4, 'W': 36, 'calib_multiplier': 1.184560099032261}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.677)
- 결과: avg_coverage=75.6286%  avg_speed_frac=0.8125  score=75.6205
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 68.451 | None | 1.000 | 5 |
  | s5378 | 91.893 | None | 1.000 | 5 |
  | s9234 | 60.083 | None | 1.000 | 5 |
  | s13207 | 82.087 | 500 | 0.250 | 0 |

## Trial 28
- 시각: 2026-07-20T22:49:59
- 소요 시간: 74.1s
- 파라미터: `{'T_init': 103, 'delta_T': 225, 'alpha': 0.862392250932763, 'K': 3, 'W': 31, 'calib_multiplier': 1.5471797448974185}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.479)
- 결과: avg_coverage=73.7246%  avg_speed_frac=0.8250  score=73.7164
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 63.521 | None | 1.000 | 5 |
  | s5378 | 94.435 | 6000 | 1.000 | 4 |
  | s9234 | 58.350 | None | 1.000 | 2 |
  | s13207 | 78.593 | 600 | 0.300 | 0 |

## Trial 29
- 시각: 2026-07-20T22:50:54
- 소요 시간: 55.0s
- 파라미터: `{'T_init': 34, 'delta_T': 171, 'alpha': 0.7766761017549104, 'K': 4, 'W': 14, 'calib_multiplier': 1.272500275741253}`
- Optuna 판단(근사): exploration (TPE가 미개척 영역을 시도) → 기존 최고 대비 미개선 (best-so-far 대비 정규화거리=0.716)
- 결과: avg_coverage=80.7809%  avg_speed_frac=0.3875  score=80.7771
- 회로별 상세:

  | 회로 | final_coverage(%) | patterns_to_reach | speed_frac | T전환횟수 |
  |---|---|---|---|---|
  | s1494 | 74.789 | 3500 | 0.583 | 6 |
  | s5378 | 96.427 | 2300 | 0.383 | 0 |
  | s9234 | 68.817 | 1300 | 0.433 | 0 |
  | s13207 | 83.090 | 300 | 0.150 | 0 |

