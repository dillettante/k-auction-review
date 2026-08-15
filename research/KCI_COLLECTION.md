# KCI 논문 수집·정리 — Phase 1 보완

상태: 1차 수집 완료 · 2026-08-15 · 본문 검토 대기

## 왜 필요한가

경공매 실용서와 민사집행 전문서는 쟁점 지도와 실무 맥락을 제공하지만, 논문은 쟁점의 학설·판례 비판·제도 변화·사실관계 유형을 넓히는 별도 연구층이다. 논문은 법률 규칙의 권위 있는 출처가 아니므로, 법령·대법원 판례·공식 법원 안내와 분리해 보관한다.

## 공식 인터페이스

한국연구재단 KCI의 논문 기본정보 API는 `articleSearch`를 사용하며, KCI 인증키와 제목 검색어가 필수다. 결과는 XML이고 요청당 최대 100건이다. 검색 결과에는 논문 ID, 제목, 저자, 학술지·발행기관·발행연월, 쪽수, 연구분야, DOI/UCI, 피인용 수, 원문공개 여부, KCI URL 등이 포함될 수 있다.

- 공식 명세: <https://www.kci.go.kr/kciportal/po/openapi/openDataView.kci?datasetBean.dtstSeqNo=1>
- KCI 데이터 제공 안내: <https://www.kci.go.kr/kciportal/po/openapi/openDataPackGuide.kci?datasetBean.dtstTyCd=00>
- 인증키 신청·관리: <https://www.kci.go.kr/kciportal/po/openapi/openApiList.kci>

인증키는 Git, JSON 설정, Markdown, 실행 로그에 넣지 않는다. 실행 순간에만 환경변수 `KCI_API_KEY`로 제공한다.

## 검색 범위

[`kci_queries.json`](kci_queries.json)은 부동산경매·민사집행·강제/임의경매·매각물건명세서·배당요구·주택임대차·유치권·법정지상권·가등기·전세권·대지권과 표현 변형을 포함한 18개 제목 검색어로 구성됐다. 1차 수집에서 원시 결과 730건, 중복 제거 464건을 확보했다. 제목 검색만으로는 논문을 빠뜨릴 수 있으므로, 누락된 표현·저널·저자를 추가하는 2차 검색을 별도로 기록한다.

## 수집 실행

```bash
export KCI_API_KEY='발급받은-키'
python3 scripts/collect_kci.py --max-pages 10 --output-dir tmp/kci
```

`tmp/kci/`에는 원문 PDF와 초록을 저장하지 않고 서지 메타데이터 JSON·CSV만 생성한다. 이 경로는 공개 저장소에 넣지 않는다. 수집기가 API 키를 출력하거나 파일에 기록하지 않는지 코드 검토 후 실행한다.

## 정리 절차

1. `kci_article_id`로 같은 논문을 합친다. 서로 다른 제목 검색어에 걸리면 `matched_query_ids`를 누적한다.
2. 제목·초록(웹에서 열람할 때만)·학술지·발행연도만 검토해 다음 중 하나로 태그한다: `procedure`, `registry_priority`, `tenant`, `distribution`, `special_right`, `land_building`, `comparative_or_policy`, `out_of_scope`.
3. 쟁점과 직접 관계가 있는 논문만 **요약 카드** 후보로 올린다. 카드에는 서지, KCI URL, 질문, 다루는 사실유형, 저자의 견해, 검증할 1차 자료를 기록한다.
4. 법령·대법원 판례를 직접 확인한 뒤에만 논문에서 소개된 규칙을 `legal_rule` 후보로 검토한다. 논문만으로 규칙 ID를 만들지 않는다.
5. 공개 저장소에는 독자적 요약과 공식 법률 출처 링크만 넣으며, 유료·제한 원문·대량 초록·PDF는 넣지 않는다.

## 수집 완료 기준

- 18개 제목 쿼리의 요청·결과 수·실행시각이 JSON에 기록되었다.
- 중복 제거 후 모든 레코드에 KCI 제어번호 또는 안정적인 서지키가 있다.
- 각 레코드가 `관련`, `보류`, `범위 밖` 중 하나로 검토되었다.
- `관련` 논문은 쟁점 카드와 연결되었지만, 법령·판례 확인 전에는 법적 결론으로 사용되지 않는다.
