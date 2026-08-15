# 합성 사례

- `synthetic-case.json`: 실제 사건·문서·인물과 무관한 합성 JSON. 스키마·근거참조 검증용이다.
- `synthetic-report.html`: 위 JSON을 현재 `tools/render_report.py`로 생성한 네트워크 비의존 HTML 예시이다.

재생성:

```bash
python3 tools/validate_case.py prototypes/synthetic-case.json
python3 tools/render_report.py prototypes/synthetic-case.json prototypes/synthetic-report.html
```

외부 법령 링크는 근거 확인용으로만 사용되며, 보고서 본문을 열거나 인쇄하는 데 필요하지 않습니다.
