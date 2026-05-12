# 피드백 Agent

기획서 PDF와 n8n 워크플로우 JSON/ZIP을 받아 한 팀 단위의 개인 피드백 리포트를 생성하는 Streamlit 앱입니다.

## 평가 모드

- **모드 A: 기획서 평가만**  
  PDF만 업로드하면 기획서 기반 4개 항목을 60점 만점으로 평가합니다.

- **모드 B: 전체 평가**  
  PDF와 n8n JSON/ZIP을 함께 업로드하면 워크플로우 2개 항목과 기획서 4개 항목을 100점 만점으로 평가합니다.

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 환경 변수

- `OPENROUTER_API_KEY`: OpenRouter `openai/gpt-4o` 호출용
- `UPSTAGE_API_KEY`: Upstage Document Parse 호출용
- `CRITERIA_CONFIG_PATH`: 선택. 행사별 rubric JSON 경로

## Railway

Railway에서는 `Procfile`의 다음 명령으로 실행됩니다.

```bash
web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

헬스체크 경로는 Streamlit 기본값인 `/_stcore/health`를 사용합니다.

## 주요 파일

- `app.py`: 단일 페이지 Streamlit UI
- `feedback_evaluator.py`: 입력 검증, PDF 파싱, 워크플로우 로딩, LLM 평가 orchestration
- `document_parser.py`: Upstage Document Parse 연동
- `workflow_input_loader.py`: `.json`/`.zip` 워크플로우 정규화
- `criteria_loader.py`: 기본 rubric 및 외부 설정 로딩
- `feedback_renderer.py`: 피드백 JSON을 Markdown 리포트로 렌더링
- `llm_evaluator.py`: OpenRouter JSON 응답 호출 래퍼
