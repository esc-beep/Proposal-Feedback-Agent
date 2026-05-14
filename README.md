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

# 터미널 1: API
uvicorn api_app:app --reload

# 터미널 2: Streamlit
streamlit run app.py

# 터미널 3: 관리자 Streamlit
streamlit run admin_app.py --server.port=8502
```

## 환경 변수

- `DATABASE_URL`: Railway Postgres 연결 문자열
- `OPENROUTER_API_KEY`: OpenRouter `openai/gpt-4o` 호출용. API 서비스에 설정합니다.
- `UPSTAGE_API_KEY`: Upstage Document Parse 호출용. API 서비스에 설정합니다.
- `BACKEND_API_URL`: Streamlit 웹 서비스가 호출할 FastAPI 주소. 로컬 기본값은 `http://localhost:8000`입니다.
- `API_SHARED_TOKEN`: Streamlit 웹 서비스와 FastAPI 서비스 사이의 Bearer 토큰
- `ADMIN_PASSWORD`: Streamlit 관리자 페이지 비밀번호
- `CRITERIA_CONFIG_PATH`: 선택. 행사별 rubric JSON 경로

## Railway

Railway에서는 같은 저장소로 서비스 3개를 구성합니다.

```bash
web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
admin: streamlit run admin_app.py --server.port=$PORT --server.address=0.0.0.0
api: uvicorn api_app:app --host 0.0.0.0 --port=$PORT
```

- `web` 서비스는 Streamlit 앱입니다.
- `admin` 서비스는 관리자 전용 Streamlit 앱입니다.
- `api` 서비스는 평가 실행, DB 저장, 관리자 조회 API를 담당합니다.
- 두 서비스는 같은 Railway Postgres의 `DATABASE_URL`을 공유합니다.
- `web`/`admin` 서비스의 `BACKEND_API_URL`은 Railway private networking 주소를 우선 사용합니다.
- Streamlit 헬스체크 경로는 `/_stcore/health`, FastAPI 헬스체크 경로는 `/health`를 사용합니다.

## 관리자 페이지

`admin` Railway 서비스로 배포된 관리자 전용 페이지에서 `ADMIN_PASSWORD`를 입력하면 저장된 응답을 볼 수 있습니다.
관리자 표에는 전체 응답 수, 응답 팀 수, 팀명, 모드, 항목별 점수, 최종 점수가 표시됩니다.
팀명 버튼을 누르면 표 아래에서 해당 응답의 총평, 액션 아이템, 항목별 강점/약점/개선 제안을 확인할 수 있습니다.

## 주요 파일

- `app.py`: 단일 페이지 Streamlit UI
- `admin_app.py`: 관리자 전용 Streamlit UI
- `api_app.py`: FastAPI 백엔드
- `feedback_storage.py`: 평가 결과 저장/조회
- `feedback_evaluator.py`: 입력 검증, PDF 파싱, 워크플로우 로딩, LLM 평가 orchestration
- `document_parser.py`: Upstage Document Parse 연동
- `workflow_input_loader.py`: `.json`/`.zip` 워크플로우 정규화
- `criteria_loader.py`: 기본 rubric 및 외부 설정 로딩
- `feedback_renderer.py`: 피드백 JSON을 Markdown 리포트로 렌더링
- `llm_evaluator.py`: OpenRouter JSON 응답 호출 래퍼
