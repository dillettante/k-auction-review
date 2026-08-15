# 공공데이터 실거래가 — 사용자 키 설정

## 원칙

이 스킬과 공개 저장소에는 API 키를 저장하지 않는다. 각 사용자가 본인 공공데이터포털 계정에서 발급·승인받은 키를 로컬 실행 환경에만 설정한다. 키는 JSON, HTML, 명령행 인수, Git 커밋, 오류 로그에 넣지 않는다.

## 발급과 승인

공공데이터포털에서 본인 계정으로 다음 API를 각각 활용신청한다.

- [국토교통부 아파트 매매 실거래가 자료](https://www.data.go.kr/data/15126469/openapi.do) — `getRTMSDataSvcAptTrade`
- [국토교통부 토지 매매 실거래가 자료](https://www.data.go.kr/data/15126466/openapi.do) — `getRTMSDataSvcLandTrade`

승인된 API의 일반 인증키를 사용한다. 발급 화면의 Encoding/Decoding 안내에 따라 실제 호출되는 형식을 확인한다. 이 프로젝트의 조회 도구는 인코딩된 키와 디코딩된 키 모두를 환경변수 값으로 받을 수 있도록 URL 인코딩을 처리한다.

## 로컬 실행

현재 셸 세션에서만 설정한다.

```bash
export AUCTION_RTMS_API_KEY='본인의_공공데이터포털_일반인증키'
```

그 다음 프로젝트 루트에서 실행한다. 결과는 Git에서 제외된 `private/`에 저장한다.

```bash
python3 tools/fetch_molit_apt_trades.py \
  --lawd-cd 11215 --month 202607 \
  --output private/molit-apt-202607.json

python3 tools/fetch_molit_land_trades.py \
  --lawd-cd 11215 --month 202607 \
  --output private/molit-land-202607.json
```

API 키가 없거나 API별 활용 승인이 없으면 조회를 건너뛰고 권리분석 보고서는 제한자료 모드로 계속 생성할 수 있다.

## 사용 제한

- 아파트 실거래가는 같은 단지·전용면적·계약일·층을 우선 대조한다.
- 토지 거래가는 토지 별도매각·대지권 분리·토지 가치 별도 검증에만 사용한다. 통상적인 집합건물 대지권 지분에 토지 거래가를 더하지 않는다.
- 취소 표기 거래는 비교군에서 제외한다.
- 동일 단지 거래가 없으면 법정동·유사 면적 비교군임을 크게 표시한다.
- 실거래 비교군은 감정평가·입찰 권고가 아니다. 권리·점유 위험과 취득·명도·수리·금융·보유 비용, 사용자 수익 기준이 확인되기 전에는 입찰 상한가를 산출하지 않는다.
