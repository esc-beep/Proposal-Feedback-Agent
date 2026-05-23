"""Streamlit UI for the single-team personal feedback agent."""

import html
import os
from typing import Any

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from database_config import resolve_database_url
from document_parser import DocumentParseError
from feedback_evaluator import FeedbackEvaluator
from feedback_renderer import FeedbackRenderer, safe_feedback_filename
from feedback_storage import FeedbackRunStore
from workflow_input_loader import WorkflowInputError


MAX_RUNS_PER_SESSION = 5
MAX_PDF_SIZE = 20 * 1024 * 1024

load_dotenv()


def main() -> None:
    st.set_page_config(page_title="피드백 Agent", page_icon="📝", layout="wide")
    _init_state()
    _render_feedback_page()


def _render_feedback_page() -> None:
    st.title("피드백 Agent")
    st.caption("기획서 PDF와 n8n 워크플로우를 바탕으로 개인 피드백 리포트를 생성합니다.")

    _render_env_status()

    with st.form("feedback_form"):
        team_name = st.text_input("팀명", placeholder="예: 스노로즈팀")
        plan_pdf = st.file_uploader("기획서 PDF", type=["pdf"], help="20MB / 50페이지 이하 PDF를 업로드해주세요.")
        workflow_file = st.file_uploader(
            "n8n 워크플로우 JSON 또는 ZIP (선택)",
            type=["json", "zip"],
            help="업로드하지 않으면 기획서 60점 만점 평가만 진행합니다.",
        )

        confirm_plan_only = True
        if plan_pdf is not None and workflow_file is None:
            st.warning("기획서만 넣으면 기획안에 대한 평가만 진행돼요.")
            confirm_plan_only = st.checkbox("네, 기획서만 60점 만점으로 평가할게요.")

        submitted = st.form_submit_button(
            "피드백 생성",
            type="primary",
            disabled=st.session_state.get("run_count", 0) >= MAX_RUNS_PER_SESSION,
        )

    if submitted:
        errors = validate_submission(
            team_name,
            plan_pdf,
            workflow_file,
            confirm_plan_only,
            st.session_state.get("run_count", 0),
        )
        if errors:
            for error in errors:
                st.error(error)
        else:
            _run_feedback(team_name, plan_pdf, workflow_file)

    if "feedback_markdown" in st.session_state:
        _render_result()


def _init_state() -> None:
    st.session_state.setdefault("run_count", 0)


def _render_env_status() -> None:
    missing = [
        name
        for name in ("OPENROUTER_API_KEY", "UPSTAGE_API_KEY")
        if not os.getenv(name)
    ]
    if missing:
        st.info(f"환경변수 설정 필요: {', '.join(missing)}")
    if not os.getenv("DATABASE_URL"):
        st.info("DATABASE_URL 미설정 시 로컬 SQLite 파일에 저장합니다.")


def validate_submission(team_name, plan_pdf, workflow_file, confirm_plan_only: bool, run_count: int) -> list[str]:
    errors = []
    if run_count >= MAX_RUNS_PER_SESSION:
        errors.append("현재 세션에서 사용할 수 있는 평가 횟수를 모두 사용했어요.")
    if not (team_name or "").strip():
        errors.append("팀명을 입력해주세요.")
    if plan_pdf is None:
        errors.append("기획서 PDF를 업로드해주세요.")
    if plan_pdf is not None and getattr(plan_pdf, "size", 0) > MAX_PDF_SIZE:
        errors.append("기획서 PDF는 20MB 이하만 업로드할 수 있어요.")
    if plan_pdf is not None and workflow_file is None and not confirm_plan_only:
        errors.append("기획서만 평가하려면 확인 체크박스를 선택해주세요.")
    return errors


def _run_feedback(team_name, plan_pdf, workflow_file) -> None:
    if st.session_state.run_count >= MAX_RUNS_PER_SESSION:
        st.error("현재 세션에서 사용할 수 있는 평가 횟수를 모두 사용했어요.")
        return

    progress = st.progress(0)
    status = st.empty()

    try:
        status.text("PDF를 파싱하고 있어요...")
        progress.progress(20)

        status.text("AI가 항목별 피드백을 작성하고 있어요...")
        progress.progress(45)

        payload = submit_feedback_run(team_name, plan_pdf, workflow_file)
        feedback_json = payload["feedback_json"]
        markdown = payload["feedback_markdown"]
        progress.progress(85)

        st.session_state.feedback_json = feedback_json
        st.session_state.feedback_markdown = markdown
        st.session_state.feedback_filename = payload["feedback_filename"]
        st.session_state.run_count += 1

        progress.progress(100)
        status.text("피드백 리포트가 생성되었어요.")
    except (DocumentParseError, WorkflowInputError, ValueError, FeedbackStorageError) as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"피드백 생성 중 예상하지 못한 오류가 발생했어요: {exc}")
    finally:
        progress.empty()
        status.empty()


class FeedbackStorageError(RuntimeError):
    """Raised when feedback cannot be saved after evaluation."""


def create_feedback_store() -> FeedbackRunStore:
    return FeedbackRunStore(resolve_database_url())


def submit_feedback_run(
    team_name,
    plan_pdf,
    workflow_file,
    evaluator: FeedbackEvaluator | None = None,
    store: FeedbackRunStore | None = None,
) -> dict[str, Any]:
    feedback_json = (evaluator or FeedbackEvaluator()).evaluate(team_name, plan_pdf, workflow_file)
    markdown = FeedbackRenderer().render(feedback_json)
    feedback_store = store or create_feedback_store()
    should_close = store is None
    try:
        feedback_store.initialize()
        run_id = feedback_store.save_feedback_result(feedback_json, markdown)
    except Exception as exc:
        raise FeedbackStorageError(f"피드백 저장 중 오류가 발생했어요: {exc}") from exc
    finally:
        if should_close:
            feedback_store.close()

    return {
        "id": run_id,
        "feedback_json": feedback_json,
        "feedback_markdown": markdown,
        "feedback_filename": safe_feedback_filename(team_name),
    }


def _render_result() -> None:
    feedback = st.session_state.feedback_json
    markdown = st.session_state.feedback_markdown
    filename = st.session_state.feedback_filename

    st.markdown("---")
    st.subheader("피드백 결과")
    _render_result_actions(markdown, filename, "top")
    st.markdown(markdown)
    _render_result_actions(markdown, filename, "bottom")

    with st.expander("JSON 원본 보기"):
        st.json(feedback)


def _render_result_actions(markdown: str, filename: str, key_suffix: str) -> None:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.download_button(
            "마크다운 다운로드",
            data=markdown.encode("utf-8"),
            file_name=filename,
            mime="text/markdown",
            key=f"download_{key_suffix}",
        )
    with col2:
        _copy_button(markdown, key_suffix)


def _copy_button(markdown: str, key_suffix: str) -> None:
    escaped = html.escape(markdown)
    components.html(
        f"""
        <textarea id="feedback-{key_suffix}" style="position:absolute;left:-9999px;">{escaped}</textarea>
        <button
          style="border:1px solid #d0d7de;border-radius:6px;padding:0.45rem 0.75rem;background:white;cursor:pointer;"
          onclick="
            const text = document.getElementById('feedback-{key_suffix}').value;
            navigator.clipboard.writeText(text);
            this.innerText = '복사 완료';
          "
        >클립보드 복사</button>
        """,
        height=45,
    )


if __name__ == "__main__":
    main()
