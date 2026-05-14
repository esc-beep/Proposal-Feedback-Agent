"""Streamlit admin UI for stored feedback submissions."""

import os
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv


DEFAULT_BACKEND_API_URL = "http://localhost:8000"
ITEM_SCORE_LABELS = [
    ("워크플로우_정상_작동", "워크플로우 정상 작동"),
    ("Upstage_활용", "Upstage 활용"),
    ("실제_적용_가능성", "실제 적용 가능성"),
    ("자동화_효과", "자동화 효과"),
    ("문제_정의_독창성", "문제 정의 독창성"),
    ("솔루션_참신함", "솔루션 참신함"),
]

load_dotenv()


def main() -> None:
    st.set_page_config(page_title="피드백 관리자", page_icon="🗂️", layout="wide")
    _render_admin_page()


class BackendAPIError(RuntimeError):
    """Raised when the admin UI cannot complete a backend request."""


def backend_api_url() -> str:
    return os.getenv("BACKEND_API_URL", DEFAULT_BACKEND_API_URL).rstrip("/")


def api_headers() -> dict[str, str]:
    token = os.getenv("API_SHARED_TOKEN", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def fetch_admin_submissions() -> dict[str, Any]:
    try:
        response = requests.get(
            f"{backend_api_url()}/admin/submissions",
            headers=api_headers(),
            timeout=30,
        )
    except requests.RequestException as exc:
        raise BackendAPIError(f"관리자 목록을 불러오지 못했어요: {exc}") from exc
    return _json_or_error(response)


def fetch_admin_submission(run_id: int) -> dict[str, Any]:
    try:
        response = requests.get(
            f"{backend_api_url()}/admin/submissions/{run_id}",
            headers=api_headers(),
            timeout=30,
        )
    except requests.RequestException as exc:
        raise BackendAPIError(f"상세 피드백을 불러오지 못했어요: {exc}") from exc
    return _json_or_error(response)


def _json_or_error(response: requests.Response) -> dict[str, Any]:
    if response.ok:
        return response.json()

    message = response.text
    try:
        payload = response.json()
        message = payload.get("detail", message)
    except ValueError:
        pass
    raise BackendAPIError(str(message))


def _render_admin_page() -> None:
    st.title("관리자 페이지")
    st.caption("저장된 평가 응답과 항목별 점수를 확인합니다.")

    configured_password = os.getenv("ADMIN_PASSWORD", "")
    password = st.text_input("관리자 비밀번호", type="password")
    if not admin_password_matches(password, configured_password):
        if password:
            st.error("관리자 비밀번호가 올바르지 않습니다.")
        elif not configured_password:
            st.error("ADMIN_PASSWORD 환경변수를 먼저 설정해주세요.")
        return

    try:
        payload = fetch_admin_submissions()
    except BackendAPIError as exc:
        st.error(str(exc))
        return

    col1, col2 = st.columns(2)
    col1.metric("전체 응답 수", payload.get("total_count", 0))
    col2.metric("응답 팀 수", payload.get("team_count", 0))

    rows = format_admin_table_rows(payload.get("submissions", []))
    if not rows:
        st.info("아직 저장된 응답이 없습니다.")
        return

    st.markdown("### 응답 목록")
    _render_admin_table(rows)

    selected_id = st.session_state.get("selected_admin_submission_id")
    if selected_id:
        try:
            detail = fetch_admin_submission(int(selected_id))
        except BackendAPIError as exc:
            st.error(str(exc))
            return
        _render_admin_detail(detail)


def admin_password_matches(candidate: str, configured_password: str) -> bool:
    return bool(configured_password) and candidate == configured_password


def format_admin_table_rows(submissions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for submission in submissions:
        item_scores = submission.get("item_scores") or {}
        row = {
            "id": submission.get("id"),
            "제출일시": _format_created_at(submission.get("created_at", "")),
            "팀명": submission.get("team_name", ""),
            "모드": submission.get("mode", ""),
            "최종 점수": f"{submission.get('total_score', 0)} / {submission.get('max_score', 0)}",
        }
        for key, label in ITEM_SCORE_LABELS:
            row[label] = _format_item_score(item_scores.get(key))
        rows.append(row)
    return rows


def _render_admin_table(rows: list[dict[str, Any]]) -> None:
    header = st.columns([1.5, 1.3, 0.7, 1.0, 1, 1, 1, 1, 1, 1])
    labels = ["제출일시", "팀명", "모드", "최종 점수"] + [label for _, label in ITEM_SCORE_LABELS]
    for column, label in zip(header, labels):
        column.markdown(f"**{label}**")

    for row in rows:
        columns = st.columns([1.5, 1.3, 0.7, 1.0, 1, 1, 1, 1, 1, 1])
        columns[0].write(row["제출일시"])
        if columns[1].button(str(row["팀명"]), key=f"submission_{row['id']}"):
            st.session_state.selected_admin_submission_id = row["id"]
        columns[2].write(row["모드"])
        columns[3].write(row["최종 점수"])
        for index, (_, label) in enumerate(ITEM_SCORE_LABELS, start=4):
            columns[index].write(row[label])


def _render_admin_detail(detail: dict[str, Any]) -> None:
    feedback = detail.get("feedback_json") or {}
    st.markdown("---")
    st.subheader(f"{detail.get('team_name', '')} 상세 피드백")
    st.write(f"최종 점수: {detail.get('total_score', 0)} / {detail.get('max_score', 0)}")
    st.markdown("#### 전체 총평")
    st.write(feedback.get("전체_총평", ""))

    actions = feedback.get("다음_액션_아이템") or []
    if actions:
        st.markdown("#### 다음 액션 아이템")
        for index, action in enumerate(actions, 1):
            st.write(f"{index}. {action}")

    st.markdown("#### 항목별 피드백")
    for key, label in ITEM_SCORE_LABELS:
        item = (feedback.get("항목별") or {}).get(key)
        if not item:
            continue
        with st.expander(f"{label} - {item.get('점수', 0)} / {item.get('만점', 0)}"):
            st.markdown(f"**강점**: {item.get('강점', '')}")
            st.markdown(f"**약점**: {item.get('약점', '')}")
            st.markdown(f"**개선 제안**: {item.get('개선_제안', '')}")

    with st.expander("마크다운 원본 보기"):
        st.markdown(detail.get("feedback_markdown", ""))


def _format_item_score(score: Any) -> str:
    if not score:
        return "-"
    return f"{score.get('점수', 0)} / {score.get('만점', 0)}"


def _format_created_at(value: str) -> str:
    if not value:
        return ""
    return value.replace("T", " ")[:16]


if __name__ == "__main__":
    main()
