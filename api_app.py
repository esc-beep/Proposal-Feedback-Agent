"""FastAPI backend for feedback evaluation and admin reads."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Callable, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile

from document_parser import DocumentParseError
from feedback_evaluator import FeedbackEvaluator
from feedback_renderer import FeedbackRenderer, safe_feedback_filename
from feedback_storage import FeedbackRunStore
from workflow_input_loader import WorkflowInputError


load_dotenv()


class UploadFileAdapter:
    def __init__(self, upload: UploadFile):
        self.name = upload.filename or "upload"
        self._upload = upload
        self._cached: bytes | None = None

    def getvalue(self) -> bytes:
        if self._cached is None:
            self._upload.file.seek(0)
            self._cached = self._upload.file.read()
            self._upload.file.seek(0)
        return self._cached


def create_app(
    store: FeedbackRunStore | None = None,
    evaluator_factory: Callable[[], FeedbackEvaluator] = FeedbackEvaluator,
    shared_token: str | None = None,
) -> FastAPI:
    database_url = os.getenv("DATABASE_URL", "sqlite:///feedback_runs.db")
    feedback_store = store or FeedbackRunStore(database_url)
    token = shared_token if shared_token is not None else os.getenv("API_SHARED_TOKEN", "")

    def require_token(authorization: Optional[str] = Header(default=None)) -> None:
        if token and authorization != f"Bearer {token}":
            raise HTTPException(status_code=401, detail="인증 토큰이 올바르지 않습니다.")

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        feedback_store.initialize()
        try:
            yield
        finally:
            feedback_store.close()

    app = FastAPI(title="Proposal Feedback API", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/feedback-runs", dependencies=[Depends(require_token)])
    def create_feedback_run(
        team_name: str = Form(...),
        plan_pdf: UploadFile = File(...),
        workflow_file: UploadFile | None = File(default=None),
    ) -> dict:
        try:
            feedback_json = evaluator_factory().evaluate(
                team_name,
                UploadFileAdapter(plan_pdf),
                UploadFileAdapter(workflow_file) if workflow_file is not None else None,
            )
            markdown = FeedbackRenderer().render(feedback_json)
            run_id = feedback_store.save_feedback_result(feedback_json, markdown)
        except (DocumentParseError, WorkflowInputError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {
            "id": run_id,
            "feedback_json": feedback_json,
            "feedback_markdown": markdown,
            "feedback_filename": safe_feedback_filename(team_name),
        }

    @app.get("/admin/submissions", dependencies=[Depends(require_token)])
    def list_admin_submissions() -> dict:
        submissions = feedback_store.list_submissions()
        return {
            "total_count": len(submissions),
            "team_count": len({submission["team_name"] for submission in submissions}),
            "submissions": submissions,
        }

    @app.get("/admin/submissions/{run_id}", dependencies=[Depends(require_token)])
    def get_admin_submission(run_id: int) -> dict:
        submission = feedback_store.get_submission(run_id)
        if submission is None:
            raise HTTPException(status_code=404, detail="응답을 찾을 수 없습니다.")
        return submission

    return app


app = create_app()
