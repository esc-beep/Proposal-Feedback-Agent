"""Single-team feedback orchestration."""

import json
from typing import Any, BinaryIO, Dict, List, Optional

from criteria_loader import CriteriaItem, CriteriaLoader
from document_parser import DocumentParser
from llm_evaluator import LLMEvaluator
from workflow_input_loader import WorkflowInputLoader


class FeedbackEvaluator:
    def __init__(
        self,
        document_parser: Optional[DocumentParser] = None,
        workflow_loader: Optional[WorkflowInputLoader] = None,
        criteria_loader: Optional[CriteriaLoader] = None,
        llm_evaluator: Optional[LLMEvaluator] = None,
    ):
        self.document_parser = document_parser or DocumentParser()
        self.workflow_loader = workflow_loader or WorkflowInputLoader()
        self.criteria_loader = criteria_loader or CriteriaLoader()
        self.llm_evaluator = llm_evaluator or LLMEvaluator()

    def evaluate(
        self,
        team_name: str,
        plan_pdf: BinaryIO,
        workflow_file: Optional[BinaryIO] = None,
    ) -> Dict[str, Any]:
        team_name = (team_name or "").strip()
        if not team_name:
            raise ValueError("팀명을 입력해주세요.")

        document_text = self.document_parser.parse_pdf(plan_pdf)
        workflows = self.workflow_loader.load(workflow_file) if workflow_file is not None else []
        mode = "B" if workflows else "A"
        criteria = self.criteria_loader.load()
        item_results: Dict[str, Dict[str, Any]] = {}

        for item in criteria.for_mode(mode):
            data = self._data_for_item(item, document_text, workflows)
            item_results[item.key] = self._evaluate_item(item, data, workflows)

        max_score = criteria.max_score_for_mode(mode)
        total_score = sum(int(item.get("점수", 0)) for item in item_results.values())
        synthesis = self.llm_evaluator.synthesize_feedback(team_name, mode, max_score, item_results)

        return {
            "팀명": team_name,
            "모드": mode,
            "총점": total_score,
            "만점": max_score,
            "항목별": item_results,
            "다음_액션_아이템": synthesis.get("다음_액션_아이템", [])[:3],
            "전체_총평": synthesis.get("전체_총평", ""),
        }

    def _data_for_item(self, item: CriteriaItem, document_text: str, workflows: List[Dict[str, Any]]) -> str:
        if item.input == "document":
            return document_text
        if item.input == "combined":
            return json.dumps(
                {
                    "기획서_본문": document_text,
                    "워크플로우들": [
                        {"파일명": workflow["name"], "워크플로우_JSON": workflow["data"]}
                        for workflow in workflows
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        return json.dumps(
            [{"파일명": workflow["name"], "워크플로우_JSON": workflow["data"]} for workflow in workflows],
            ensure_ascii=False,
            indent=2,
        )

    def _evaluate_item(self, item: CriteriaItem, data: str, workflows: List[Dict[str, Any]]) -> Dict[str, Any]:
        rubric = item.multi_rubric if item.input == "workflow" and len(workflows) > 1 and item.multi_rubric else item.rubric
        raw = self.llm_evaluator.evaluate_feedback(
            data=data,
            criteria=rubric,
            item_key=item.key,
            item_name=item.name,
            max_score=item.max_score,
        )
        return self._normalize_item_result(raw, item.max_score)

    def _normalize_item_result(self, raw: Dict[str, Any], max_score: int) -> Dict[str, Any]:
        score = self._coerce_score(raw.get("점수", raw.get("총점", 0)), max_score)
        return {
            "점수": score,
            "만점": max_score,
            "강점": str(raw.get("강점") or raw.get("종합_평가") or "강점이 명확히 드러난 부분을 더 구체화하면 좋아요."),
            "약점": str(raw.get("약점") or "보완할 지점을 더 구체적으로 확인해보면 좋아요."),
            "개선_제안": str(raw.get("개선_제안") or raw.get("개선 제안") or "다음 제출 전 근거와 예시를 한 단계 더 구체화해보세요."),
        }

    def _coerce_score(self, value: Any, max_score: int) -> int:
        try:
            score = int(float(value))
        except (TypeError, ValueError):
            score = 0
        return max(0, min(score, max_score))
