---
name: analyze-korean-auction-rights
description: "Analyze Korean court-auction document bundles (PDF, image, HTML, or text) into a local evidence-linked HTML review of sale scope, registry timeline, occupancy, special rights, missing documents, and optional transaction comparables. Use when reviewing Korean real-estate court auctions, registry certificates, sale specifications, status reports, appraisal reports, tenants, provisional registrations, land rights, or pre-bid risks."
---

# 한국 법원경매 권리분석

제공 문서에서 확인된 사실과 공식 법령·판례 근거를 분리해, 입찰 전 확인할 사항을 추적 가능한 HTML로 만든다. 이는 법률의견·입찰대행·안전 또는 수익 보장이 아니다.

⚠⚠ **답을 내기 전에 `../DISCLAIMER.md`를 읽는다.** 경계가 거기 있다.

⚠⚠ **`preliminary_bid_candidate`를 「입찰하라」로 쓰지 않는다.** 그것은 **이용자가 준 자료 안에서 결론을 뒤집는 사실이 아직 안 보인다**는 상태 표시이지 권유가 아니다. 신뢰도와 **뒤집히는 조건**을 항상 같은 화면에 둔다. **「자료에 없다」와 「위험이 없다」는 다르다** — 그 구별을 출력에서 지우지 않는다.

## 작업 순서

1. **입력 게이트** — 사건별로 묶인 파일을 `tools/intake_manifest.py`로 검사하고 `tools/check_bundle_gate.py`로 필수 문서·OCR 필요 여부를 표시한다. 최신 건물·토지 등기사항전부증명서, 매각물건명세서, 현황조사서, 감정평가서가 빠지면 `limited_source_mode`를 유지한다. 대상 특정부터 입찰가 마무리까지의 작성 순서는 [입찰 전 실무 검토 순서](references/pre-bid-workflow.md)를 따른다.
2. **사실 추출** — 페이지·원문 근거를 `case.schema.json`의 `evidence`에 보관한다. OCR 값은 `candidate`로 시작하며 원문 확인 전 `confirmed`로 바꾸지 않는다. 스캔 PDF는 macOS Vision OCR을 사용하되 기존 글자층에 OCR을 덧씌우지 않는다.
3. **권리·점유 대조와 중대 쟁점 게이트** — 권리와 점유 사실을 날짜 축에 분리하고, 문서 충돌을 `conflicts`에 기록한다. 유치권·가등기/가처분·토지와 건물의 분리·공유지분·임대차 적용법 징후가 있으면 [중대 권리 쟁점 확인 게이트](references/decision-gates.md)를 읽고 `legal_gate_reviews`를 작성한다. 이 필드는 `확인된 사실`, `빠진 사실`, `다음 행동`만 기록하며 권리효과 자체를 자동 결론 내리지 않는다. `tools/validate_case.py`를 통과하지 못한 사건은 렌더하지 않는다.
4. **수요자 중심 결정지원** — 자료 부족을 곧바로 “판단 불가”로 바꾸지 않는다. `현재 자료에서 가장 가능성 높은 효과 → 결론이 뒤집히는 조건 → 사용자가 확인할 문서·현장 → 미확인 시 가격에 반영할 위험` 순으로 출력한다. `buyer_brief`에 잠정 입찰판단, 신뢰도, 초보자 적합성, 권리·점유·특수물건·가격 요약을 먼저 작성한다. 다만 `legal_gate_reviews`에 `facts_incomplete` 또는 `expert_review_required`가 있으면 그 쟁점의 인수·소멸·금액을 확정 문구로 쓰지 않는다. 확정과 잠정 추론은 문구·색·증거 상태로 구별한다.
5. **선택적 가격 근거** — 사용자가 직접 발급한 공공데이터포털 키로만 국토교통부 실거래가를 조회한다. 동일 단지·유사 면적이 확인되지 않으면 보조 비교군으로 명시하며, 권리·점유·비용 가정이 미비하면 입찰 상한가를 계산하지 않는다. 자세한 절차는 [references/market-data.md](references/market-data.md)를 읽는다.
6. **공유본 생성** — 실제 사건은 `--mask`로 렌더한다. 개인식별정보·원문 PDF·OCR 전문·API 키·`private/` 결과를 공개 저장소에 넣지 않는다.

## 실행 도구

프로젝트 루트의 `tools/`를 사용한다.

- `intake_manifest.py` — 파일 유형·해시·OCR 필요 여부만 기록
- `check_bundle_gate.py` — 필수 문서 및 제한자료 모드 판정
- `render_bundle_gate_report.py` — 문서 완전성·특수 문구 경보 HTML 생성
- `extract_insight_auction.py` — InsightAuction 단일 PDF의 후보 사실 추출
- `extract_sale_spec_flags.py` — 공식 매각물건명세서의 특수권리·점유 검토 문구 탐지
- `validate_case.py` — 스키마와 증거·규칙 참조 검사
- `render_report.py` — 단일 HTML 보고서 생성
- `fetch_molit_apt_trades.py`, `fetch_molit_land_trades.py` — 사용자 키 기반 실거래 조회
- `build_market_comparables.py` — 동일 단지 우선, 없으면 법정동·면적 보조 비교군 생성
- `calculate_bid_ceiling.py` — 권리·비교군·비용 입력 게이트를 모두 통과한 경우만 참고 상한 계산

## 출력 통제

- `confirmed`: 필요한 증거와 현행 공식 근거가 모두 있다.
- `conditional`: 가정과 해소 조건을 함께 표시한다.
- `withheld`: 자료 부족·상충·지원 범위 밖이다.

결론·입찰 판단·가격 섹션마다 증거 ID와 법률 규칙 ID가 있어야 한다. 경매지·광고·OCR 요약만으로는 권리효과, 임차인 부존재, 토지 부담, 입찰가를 확정하지 않는다.

다만 **확정하지 않는 것과 아무 결론도 주지 않는 것은 다르다.** 경매지에 말소기준권리, 소멸 여부, 비소멸 권리 없음, 임차내역 없음 등이 함께 표시되면 이를 잠정 신호로 종합해 `preliminary_bid_candidate` 또는 `expert_review_required`를 제시한다. 단일 민간자료이면 신뢰도는 `low`로 두고, 공식 원문에서 뒤집힐 조건을 바로 옆에 적는다.

아파트의 “대지권 지분과 전유부분 전체 매각”은 통상적인 집합건물 구조일 수 있으므로 그 문구만으로 지분 특수물건으로 분류하지 않는다. 전유부분 일부 지분매각, 대지권 미등기·분리매각, 토지 별도등기 등 추가 단서가 있을 때만 특수물건 경보를 높인다.

## 중대 쟁점 기록 형식

`legal_gate_reviews`는 선택 필드이지만, 위 중대 쟁점의 단서가 있으면 생략하지 않는다. 각 항목은 `gate_id`, 상태, 확인·미확인 사실, 증거, 적용 규칙, 다음 행동으로 구성한다.

- `facts_incomplete`: 필요한 사실이 빠진 상태다. 빠진 사실과 그것을 얻을 문서·현장 확인을 반드시 쓴다.
- `record_ready_for_review`: 카탈로그의 필수 사실과 증거가 갖추어진 상태다. 이는 전문 검토에 필요한 기록이 정리됐다는 뜻일 뿐 결론 확정이 아니다.
- `expert_review_required`: 점유·소송·등기 원문·분할관계 등으로 개별 검토가 필요한 상태다. 입찰 전 해소 경로를 구체적으로 쓴다.

검증기는 게이트별 필수 사실 목록과 규칙·판례 연결을 검사한다. 보고서에는 영어 식별자 대신 `중대 권리 쟁점 확인` 카드와 한국어 확인 목록만 표시한다.

## 마지막 — 보고서와 답변에 반드시 붙인다

**아래 한 줄을 그대로** 붙인다. 요약하거나 생략하지 않는다.

> 이 결과는 제공하신 자료 범위의 정리이며 **입찰 권고·법률의견이 아닙니다.** 경매 사건은 진행 중에 바뀝니다 — 입찰 전 최신 법원 문서·등기사항전부증명서·현장을 직접 확인하십시오.

⚠ 사용자가 **보고서를 외부에 공유**하려 하면 마스킹 모드를 안내한다. 사건자료에는 채무자·임차인·점유자의 **개인정보가 들어 있다**(`../DISCLAIMER.md` §5).
