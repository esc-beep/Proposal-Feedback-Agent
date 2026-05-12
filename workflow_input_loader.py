"""Utilities for loading a single team's n8n workflow upload."""

import io
import json
import os
import zipfile
from typing import Any, BinaryIO, Dict, List


class WorkflowInputError(ValueError):
    """Raised when a workflow upload cannot be used for evaluation."""


class WorkflowInputLoader:
    """Normalize a .json or .zip upload into a list of workflow objects."""

    def load(self, uploaded_file: BinaryIO) -> List[Dict[str, Any]]:
        if uploaded_file is None:
            return []

        name = getattr(uploaded_file, "name", "workflow")
        extension = os.path.splitext(name)[1].lower()
        raw_bytes = self._read_bytes(uploaded_file)

        if extension == ".json":
            return [{"name": os.path.basename(name), "data": self._load_json(raw_bytes, name)}]
        if extension == ".zip":
            return self._load_zip(raw_bytes)

        raise WorkflowInputError("n8n 워크플로우는 .json 또는 .zip 파일만 업로드할 수 있어요.")

    def _read_bytes(self, uploaded_file: BinaryIO) -> bytes:
        if hasattr(uploaded_file, "getvalue"):
            data = uploaded_file.getvalue()
        elif hasattr(uploaded_file, "getbuffer"):
            data = bytes(uploaded_file.getbuffer())
        else:
            position = uploaded_file.tell() if hasattr(uploaded_file, "tell") else None
            data = uploaded_file.read()
            if position is not None and hasattr(uploaded_file, "seek"):
                uploaded_file.seek(position)

        if not data:
            raise WorkflowInputError("업로드된 워크플로우 파일이 비어 있어요.")
        return bytes(data)

    def _load_json(self, raw_bytes: bytes, name: str) -> Dict[str, Any]:
        try:
            return json.loads(raw_bytes.decode("utf-8-sig"))
        except UnicodeDecodeError as exc:
            raise WorkflowInputError(f"{name} 파일을 UTF-8 JSON으로 읽을 수 없어요.") from exc
        except json.JSONDecodeError as exc:
            raise WorkflowInputError(f"{name} 파일의 JSON 형식이 올바르지 않아요.") from exc

    def _load_zip(self, raw_bytes: bytes) -> List[Dict[str, Any]]:
        workflows: List[Dict[str, Any]] = []
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as zip_file:
                for item in zip_file.infolist():
                    if item.is_dir() or item.filename.startswith("__MACOSX/"):
                        continue
                    if not item.filename.lower().endswith(".json"):
                        continue
                    if os.path.basename(item.filename).startswith("._"):
                        continue

                    data = self._load_json(zip_file.read(item), item.filename)
                    workflows.append({"name": item.filename, "data": data})
        except zipfile.BadZipFile as exc:
            raise WorkflowInputError("zip 파일을 열 수 없어요. 압축 파일이 손상되었는지 확인해주세요.") from exc

        if not workflows:
            raise WorkflowInputError("zip 안에서 평가 가능한 n8n JSON 파일을 찾지 못했어요.")
        return workflows
