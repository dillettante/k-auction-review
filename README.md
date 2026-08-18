# K-Auction Review

> 한국 법원경매 자료를 근거별로 정리해 권리·점유·특수물건·입찰 전 확인사항과 실거래가 비교를 HTML로 생성하는 로컬 에이전트 스킬

입찰자가 제공한 법원경매 문서에서 사실과 근거를 구분하고, 제한된 자료로도 **현재 가장 가능성 높은 결론과 그 결론이 뒤집히는 조건**을 함께 제시하는 로컬 우선 도구입니다. 보고서는 네트워크 없이 열리는 단일 HTML 파일로 생성됩니다.

> **중요:** 개인이 무상으로 공개하는 참고용 분석도구이며 **입찰 권고, 법률의견, 권리의 최종 판정, 수익 보장이 아닙니다.** 이용하거나 이슈로 소통하더라도 자문관계가 성립하지 않습니다. 입찰 전 최신 법원 문서·등기사항전부증명서·현장 상태를 직접 확인하고, 필요하면 전문가의 검토를 받으세요 → [DISCLAIMER.md](DISCLAIMER.md)
>
> ⚠ **「잠정 입찰판단」은 권유가 아닙니다.** 이용자가 준 자료 안에서 **무엇이 확인됐고 무엇이 확인 안 됐는지**를 표시한 것이며, 신뢰도와 **결론이 뒤집히는 조건**이 항상 함께 붙습니다. **「자료에 없다」는 「위험이 없다」가 아닙니다.**

## 무엇을 제공하나요

- **입찰자 중심 요약**: 잠정 입찰판단(⚠ 권유가 아니라 **자료 상태 표시**), 신뢰도, 초보자 적합성, 권리·점유·특수물건·가격 요약
- **조건부 권리분석**: 확인된 단서 → 가장 가능성 높은 효과 → 결론이 뒤집히는 조건 → 입찰 전 행동
- **문서 게이트**: 매각물건명세서·현황조사서·감정평가서·등기 원문의 누락, 상충, OCR 확인 필요 상태 표시
- **증거 추적**: 결론에서 문서 종이와 원문 문구로 돌아가는 간결한 `근거 N` 링크
- **특수 쟁점 경보**: 가등기·유치권·대지권/별도등기·법정지상권·임차권등기·일괄매각 등의 추가 확인 항목
- **중대 쟁점 확인 게이트**: 유치권·가등기/가처분·토지/건물 분리·공유지분·임대차 징후가 있으면, 확인된 사실·빠진 사실·다음 행동을 한국어로 표시하고 자동 결론을 차단
- **실거래가 보조 비교**: 사용자가 직접 발급한 국토교통부 API 키로 아파트·토지 실거래가를 조회하고, 비교군의 적합성과 한계를 표시

## 현재 지원 범위

현재 핵심 범위는 **한국 법원의 주거용 집합건물 경매**입니다. 여러 목록의 일괄매각, 제시외 건물, 상가·단독주택·토지, 대지권 미등기, 지분매각은 자동 확정 대상이 아니며 `전문 검토 필요`로 분리합니다. 조세공매·신탁공매는 동일 규칙을 쓰지 않으며 현재 지원하지 않습니다.

상세 범위와 제외 기준은 [SCOPE.md](SCOPE.md)를 참조하세요.

## 빠른 시작

필수: Python 3.11+ / `jsonschema` / PDF 입력 분석 시 `PyMuPDF`.

```bash
git clone https://github.com/dillettante/k-auction-review.git
cd k-auction-review
python3 -m pip install -r requirements.txt
```
먼저 포함된 합성 사건으로 구조와 보고서 생성을 확인할 수 있습니다.

```bash
python3 tools/validate_case.py prototypes/synthetic-case.json
python3 tools/render_report.py prototypes/synthetic-case.json tmp/synthetic-report.html --mask
```

실제 사건은 로컬 전용 폴더에서 처리합니다.

```bash
python3 tools/intake_manifest.py /path/to/case-files --recursive --output private/intake.json
python3 tools/check_bundle_gate.py private/intake.json --output private/gate.json

# 사건 JSON을 작성·확인한 뒤
python3 tools/validate_case.py private/case.json
python3 tools/render_report.py private/case.json tmp/report.html --mask
```
입력 스키마와 작성 원칙은 [스킬 안내](analyze-korean-auction-rights/SKILL.md), 법령·판례 출처는 [법률 규칙 등록부](research/legal/LEGAL_RULE_REGISTER.md)와 [판례 등록부](research/legal/CASE_REGISTER.md)에 있습니다.
중대 권리 쟁점의 실무 확인 순서는 [확인 게이트](analyze-korean-auction-rights/references/decision-gates.md), 기계 검증용 사실 목록은 [게이트 카탈로그](research/legal/LEGAL_GATE_CATALOG.json)에 있습니다.
제한자료에서도 보고서를 실무적인 행동으로 연결하는 순서는 [입찰 전 실무 검토 순서](analyze-korean-auction-rights/references/pre-bid-workflow.md)를 참조하세요.

## 제한자료를 읽는 방식

경매지 단독 자료라면 보고서는 확정 판정을 하지 않습니다. 대신 말소기준권리, 등기 시계열, 비소멸 권리 기재, 임차내역, 매각 범위 등 제공 문서의 단서를 종합하여 다음을 출력합니다.

1. 현재 자료로 본 잠정 입찰판단
2. 그 판단의 신뢰도와 초보자 적합성
3. 결론을 뒤집을 수 있는 선순위 권리·점유·특별매각조건
4. 입찰 전 직접 확인할 문서·현장·비용 항목

`부족 자료 = 무응답`이 아니라, 근거와 전제를 분리한 최대한의 실무적 정보를 제공하는 것이 목표입니다.

## 실거래가 데이터 (선택)

국토교통부 실거래가 API는 사용자 본인이 [공공데이터포털](https://www.data.go.kr/)에서 발급받은 키를 실행 환경에만 설정하여 사용합니다. 키는 보고서·JSON·명령어·저장소에 저장하지 않습니다.

```bash
export AUCTION_RTMS_API_KEY='your-data-go-kr-key'
python3 tools/fetch_molit_apt_trades.py \
  --lawd-cd 11215 --month 202607 --output private/molit-apt.json
```
동일 단지가 확인되지 않은 비교군은 항상 보조 비교로 표시합니다. 상세 절차는 [시장데이터 안내](analyze-korean-auction-rights/references/market-data.md)를 참조하세요.

## 프라이버시·공개 원칙

- 실제 사건 문서, 경매지, 등기사항증명서, OCR 전문, 개인정보, API 키는 로컬에만 두세요.
- `private/`, `samples/`, `tmp/`, `.env*`는 Git에서 제외됩니다. 공개 저장소에는 합성 사건과 공식 출처에 기초한 독자적 요약만 둡니다.
- 배포 전 아래 검사를 실행하세요.

```bash
python3 tools/check_public_release.py --root .
```

## 구성

| 경로 | 내용 |
| --- | --- |
| `analyze-korean-auction-rights/` | Codex·호환 에이전트용 스키 정의 |
| `tools/` | 문서 게이트, 추출, 검증, HTML 렌더, 시장데이터 도구 |
| `research/legal/` | 공식 법령·판례 링크와 이슈별 적용 한계 |
| `research/` | KCI 서지 선별과 방법론 지도 |
| `prototypes/` | 실제 사건과 무관한 합성 검증 사례 |
| `DISCLAIMER.md` | 경계와 면책 — **답을 내기 전에 읽을 것** |
| `SCOPE.md` | 지원 범위·제외 기준·출력 구조 |

## 라이선스

[MIT License](LICENSE). 법령·판례·KCI 등 외부 출처의 원문 권리는 각 권리자에게 있으며, 이 저장소의 요약과 링크는 인용 근거나 법률의견이 아닙니다.

⚠ 조회한 실거래가 등 외부 데이터는 **재배포하지 마십시오.** 개별 수치의 인용은 자유롭지만 체계적·반복적 복제는 **데이터베이스제작자의 권리**(저작권법 제93조) 문제가 됩니다. 자세한 경계는 [`DISCLAIMER.md`](DISCLAIMER.md)에 있습니다.
