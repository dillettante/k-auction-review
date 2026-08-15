# KCI 논문 카탈로그 — 1차 선별

상태: 서지·제목 기준 1차 선별 완료 · 2026-08-15 · 본문 열람·법리 검증 전

## 수집 스냅샷

- 출처: KCI `articleSearch` Open API, `research/kci_queries.json`의 18개 제목 검색어
- 요청 결과: 원시 결과 730건, KCI 제어번호 기준 중복 제거 후 464건
- 수집물: 논문 전문·초록 없이 서지 메타데이터만. 실행 산출물은 `tmp/kci/`에만 두며 Git 제외 대상이다.
- 검색 누락 표시: 정확 제목 검색어 `매각물건명세서`, `주택임대차 경매`, `매각물건 명세서`는 결과가 없었다. 관련 논문은 `임차인 경매`, `대항력`, `우선변제권`, `배당 경매`의 확장 검색에서 보완했다.

아래의 “검토 이유”는 제목·서지·검색어에 근거한 우선순위일 뿐, 논문의 결론을 요약하거나 채택한 것이 아니다. 논문을 읽은 뒤에도 현행 법령·판례·공식 법원 자료를 독립적으로 확인해야 한다.

## 즉시 검토 대상

| 연결 이슈 | 논문 | 검토 이유 |
| --- | --- | --- |
| IA05 문서 불일치 | [ART003329717 (2026), 조재진·권기욱, 「부동산 경매의 하자 예방을 위한 경매문서군 정보공시의 실효성 제고에 관한 연구」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003329717) | 명세서·현황·감정 등 문서군과 증거 추적형 HTML 설계의 비교 대상 |
| IA03 임차인 | [ART003296070 (2025), 김명곤·임미화, 「부동산 경매절차에서 임차인 권리보호의 법적 과제와 개선방안」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003296070) | 주거용 MVP의 임차인 입력·누락자료 질문 설계 대상 |
| IA03·IA04 | [ART003083642 (2024), 정은아, 「임차목적물의 경매절차 진행 시 우선변제권을 승계한 보증금반환채권 양수인의 배당요구와 임대차의 종료」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003083642) | 임차인·채권양수·배당요구를 분리할 필요성을 검토 |
| IA03 | [ART002322011 (2018), 유제민, 「부동산 경매절차에서의 임대차와 관련된 각종 쟁점」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002322011) | 대항력·배당 관련 쟁점 탐색의 교차 자료 |
| IA03 | [ART002358285 (2018), 노한장, 「부동산경매 절차상 주택임차인 보호의 문제점과 해결방안 연구」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002358285) | 임차인 보호 제도·예외 탐색 자료 |
| IA04 | [ART001414509 (2009), 이천교, 「배당요구 종기제도와 실무」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART001414509) | 배당요구 종기와 사건기록 입력 항목의 탐색 자료 |
| IA04 | [ART003044375 (2023), 성준호, 「민사집행법상 부동산경매에 있어 잉여주의와 소멸주의 및 인수주의」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003044375) | 전세권·채권적 전세 관련 분기 검토 |
| IA04 | [ART002502249 (2019), 원상철, 「경매절차에서 배당의 쟁점에 관한 실무적 고찰」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002502249) | 배당 절차의 질문 목록 보완 |
| IA06 보전등기 | [ART003123157 (2024), 양형우, 「경매절차에서 청구권 보전을 위한 가등기의 효력」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003123157) | 가등기 원인·후속 절차 자료 요구의 설계 대상 |
| IA06 | [ART002939543 (2023), 이천교, 「공유물분할을 위한 경매실무와 문제점」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002939543) | 공유지분·선순위 가등기 사안의 MVP 범위 제외 기준 검토 |
| IA06 | [ART002446633 (2019), 전장헌, 「부동산경매에서 매수인에 대한 가압류의 관계와 담보책임에 관한 소고」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002446633) | 보전처분이 감지될 때의 추가 기록 요구 검토 |
| IA07 대지권 | [ART003270791 (2025), 이찬양, 「대지권 미등기를 둘러싼 집합건물의 합리적 규율방안에 관한 소고」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003270791) | 대지사용권·근저당·매수인 관계의 질문 카드 보완 |
| IA07 | [ART003051926 (2024), 서종희, 「집합건물의 공용부분에서의 수익금의 분배 및 대지권 미등기 상태의 아파트 경매에 관한 소고」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003051926) | 집합건물·대지권 미등기 자료 요청의 교차 확인 |
| IA07·IA09 | [ART002201438 (2017), 박재승, 「구분건물의 토지지분만의 경매에서의 문제점과 그 해결방안」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002201438) | 토지·건물 분리 매각의 보류 조건 검토 |
| IA09 지상권 | [ART003270795 (2025), 백상현·장교식, 「부동산경매에서 법정지상권의 불확실성에 따른 법제 개선 방안」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003270795) | 법정지상권의 자동판정 금지 및 역사자료 요구 근거 탐색 |
| IA08 유치권 | [ART003312118 (2026), 박해선·이린하·김제완, 「부동산 경매에서 다툼 있는 유치권의 처리」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003312118) | 최근 대상결정과 신고·점유·채권 자료의 분리 검토 |
| IA08 | [ART003051931 (2024), 박영목, 「부동산 경매 시 유치권의 대항력 제한 법리에 대한 검토」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003051931) | 유치권 이슈의 판례 재검증 출발점 |
| IA08 | [ART002934160 (2023), 양형우, 「유치권부존재확인 확정판결과 후행 경매절차에서 유치권의 효력」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002934160) | 확정판결·후속 절차 문서의 필요성 검토 |
| IA08 | [ART003016238 (2023), 김성욱, 「부동산 경매절차에서 유치권자의 지위에 관한 고찰」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003016238) | 유치권자 관련 질문·결론 상태 설계 보완 |
| IA08 | [ART002445365 (2019), 서종희, 「유치권자와 경매절차에서의 유치목적물 매수인의 법적 관계」](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002445365) | 매수인 관계를 자동 결론에서 제외하는 검토 자료 |

## 다음 선별 순서

1. 즉시 검토 대상의 본문을 적법한 접근 범위에서 읽고, `사실유형 / 논점 / 저자가 소개한 판례·법령 / 검증할 1차 출처 / 이슈 카드 연결`만 기록한다.
2. 그 결과로 IA03·IA04·IA06·IA07·IA08·IA09의 카드별 보충 질문을 만든다. 논문의 견해와 현행 1차 자료가 다르면 충돌로 표시한다.
3. 464건 중 나머지는 제목 기준으로 `out_of_scope`(시세·낙찰가·정책), `comparative_or_policy`, `secondary_review` 후보로 분류한다.
4. 논문 본문·초록·대량 메타데이터는 공개 저장소에 포함하지 않는다.
