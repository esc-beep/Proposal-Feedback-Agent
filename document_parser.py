"""Upstage Document Parse integration."""

import os
import re
from html.parser import HTMLParser
from typing import BinaryIO

import requests


class DocumentParseError(RuntimeError):
    """Raised when PDF parsing cannot complete."""


class DocumentParser:
    ENDPOINT = "https://api.upstage.ai/v1/document-ai/document-parse"
    MAX_BYTES = 20 * 1024 * 1024
    MAX_PAGES = 50

    def __init__(self, api_key: str | None = None, timeout: int = 120):
        self.api_key = os.getenv("UPSTAGE_API_KEY") if api_key is None else api_key
        self.timeout = timeout

    def parse_pdf(self, uploaded_file: BinaryIO) -> str:
        if uploaded_file is None:
            raise DocumentParseError("기획서 PDF를 업로드해주세요.")

        name = getattr(uploaded_file, "name", "plan.pdf")
        if not name.lower().endswith(".pdf"):
            raise DocumentParseError("기획서는 PDF 파일만 업로드할 수 있어요.")

        data = self._read_bytes(uploaded_file)
        if len(data) > self.MAX_BYTES:
            raise DocumentParseError("PDF는 20MB 이하 파일만 업로드할 수 있어요.")
        if self._estimate_page_count(data) > self.MAX_PAGES:
            raise DocumentParseError("PDF는 50페이지 이하 파일만 업로드할 수 있어요.")
        if not self.api_key:
            raise DocumentParseError("UPSTAGE_API_KEY 환경변수가 설정되지 않았어요.")

        try:
            response = requests.post(
                self.ENDPOINT,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"document": (name, data, "application/pdf")},
                data={"ocr": "auto"},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DocumentParseError(f"PDF 파싱 중 오류가 발생했어요: {exc}") from exc

        payload = response.json()
        text = self._extract_text(payload)
        if not text.strip():
            raise DocumentParseError("PDF에서 평가할 수 있는 텍스트를 추출하지 못했어요.")
        return text

    def _read_bytes(self, uploaded_file: BinaryIO) -> bytes:
        if hasattr(uploaded_file, "getvalue"):
            return bytes(uploaded_file.getvalue())
        if hasattr(uploaded_file, "getbuffer"):
            return bytes(uploaded_file.getbuffer())
        return bytes(uploaded_file.read())

    def _estimate_page_count(self, data: bytes) -> int:
        return max(1, len(re.findall(rb"/Type\s*/Page\b", data)))

    def _extract_text(self, payload: dict) -> str:
        for key in ("markdown", "text", "content"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
            if isinstance(value, dict):
                nested = self._extract_content_text(value)
                if nested.strip():
                    return nested

        document = payload.get("document")
        if isinstance(document, dict):
            for key in ("markdown", "text", "content"):
                value = document.get(key)
                if isinstance(value, str) and value.strip():
                    return value
                if isinstance(value, dict):
                    nested = self._extract_content_text(value)
                    if nested.strip():
                        return nested

        pages = payload.get("pages")
        if isinstance(pages, list):
            page_texts = []
            for page in pages:
                if isinstance(page, dict):
                    page_texts.append(self._extract_content_text(page))
            return "\n\n".join(text for text in page_texts if text.strip())

        elements = payload.get("elements")
        if isinstance(elements, list):
            element_texts = []
            for element in elements:
                if isinstance(element, dict):
                    element_texts.append(self._extract_content_text(element.get("content", element)))
            return "\n\n".join(text for text in element_texts if text.strip())

        return ""

    def _extract_content_text(self, content: dict) -> str:
        for key in ("markdown", "text"):
            value = content.get(key)
            if isinstance(value, str) and value.strip():
                return value

        html = content.get("html")
        if isinstance(html, str) and html.strip():
            return _html_to_text(html)

        return ""


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "br", "div", "tr", "li", "h1", "h2", "h3", "h4", "td", "th"}:
            self.parts.append("\n")

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)


def _html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    text = " ".join(parser.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
