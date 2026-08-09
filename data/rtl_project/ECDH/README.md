# X25519 ECDH 하드웨어 가속기 (FPGA)

## 개요

FPGA 기반 고속 X25519 (Curve25519) ECDH(Elliptic Curve Diffie-Hellman) 하드웨어 가속기.
Montgomery ladder 알고리즘 기반 scalar multiplication을 파이프라인 하드웨어로 구현하고,
RFC 7748 / RFC 8037 표준 테스트 벡터와 Google Wycheproof 테스트 벡터(518개, `x25519_test.json`)로
검증했다. AXI-Stream 인터페이스를 사용해 연구실 FPGA 보드와 통신하도록 설계됨
(호스트 측 통신 드라이버: `PQC_KEM.c`).

지도교수 지도 하에 진행된 학부연구생 프로젝트로, 원본 설계 보고서와 발표자료는 저작권이
학교로 양도되어 이 저장소에는 포함하지 않았다. 여기에는 소스 코드만 포함한다.

## 데이터 흐름 (파이프라인)

```
top_ecdh_axi (AXI-Stream, mode로 동작 선택)
  -> top_x25519_wrapper (64bit 버스 <-> 256bit 내부 신호 변환)
    -> top_x25519 (바이트 스왑 + 스칼라 클램핑 + FSM 제어)
      -> x25519_core (Montgomery ladder 실행)
        -> inversion_25519 (페르마 소정리 기반 모듈러 역원)
          -> mult_mod_25519 (최종 아핀 좌표 계산)
```

## 모듈별 설명

| 파일 | 역할 |
|---|---|
| `top_ecdh_axi.v` | AXI-Stream 입출력 wrapper, `mode` 신호로 동작 모드 선택 |
| `top_x25519_wrapper.v` | 64bit 버스 ↔ 256bit 내부 데이터 변환 (4클럭에 걸쳐 로드/언로드) |
| `top_x25519.v` | 최상위 제어. 입력 바이트 스왑, X25519 스펙에 따른 스칼라 클램핑, 하위 모듈 연결 FSM |
| `x25519_core.v` | Montgomery ladder 실행 엔진 (`mont_ladder` 컨트롤러 + `shared_alu_25519` 실행부) |
| `mont_ladder.v` | Montgomery ladder 18-step FSM (X25519 표준 알고리즘), constant-time cswap 포함 |
| `shared_alu_25519.v` | 덧셈/뺄셈/곱셈을 겸하는 모듈러 연산 ALU (mod 2^255-19), 파이프라인 구조 |
| `mult_mod_25519.v` | 모듈러 곱셈기. 비교기 없이 MUX 기반 최종 보정으로 최적화 |
| `mod_reducer_25519.v` | p = 2^255 - 19의 특수한 형태를 이용한 별도의 축소(reduction) 모듈 |
| `inversion_25519.v` | 페르마의 소정리(Z^(p-2) mod p) 기반 모듈러 역원 계산, square-and-multiply 방식 |
| `curve25519.v` | 참고/비교용 대안 구현체 (다른 포트 인터페이스, 고정 레이턴시 파이프라인 가정 — 본인 최종 설계와는 별개로 검토했던 버전으로 추정, 출처 재확인 필요) |
| `inversion_255.v` | 주석이 없어 용도 불명. 실험/미사용 파일로 추정 |
| `PQC_KEM.c` | 본인이 작성한 호스트 측 C 드라이버. **연구실 FPGA 보드와 통신하기 위한 코드**로, Vivado AXI DMA 레지스터를 직접 제어해 가속기에 입력을 보내고 결과를 받아옴 |

## 검증

- RFC 7748 / RFC 8037 표준 테스트 벡터를 테스트벤치에 하드코딩해 self-checking 방식으로 검증
  (`tb_top_x25519.v`, `tb_top_x25519_wrapper.v`, `tb_top_ecdh_axi.v`)
- Google Wycheproof 테스트 벡터(`x25519_test.json`, 518개) — edge case, known-answer 등
  다양한 케이스로 추가 검증 (출처: `테스트벡터 출처.txt`)

---
*이 문서는 소스 코드를 읽고 자동 생성한 초안입니다. `curve25519.v`의 출처 등
추정으로 표시한 부분은 검토 후 직접 수정해 주세요.*
