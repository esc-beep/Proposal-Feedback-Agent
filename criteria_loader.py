"""Rubric loading for the single-team feedback agent."""

import json
import os
from dataclasses import dataclass, replace
from typing import Dict, Iterable, List, Optional

from evaluation_criteria import (
    MULTI_WORKFLOW_TECHNICAL_CRITERIA,
    MULTI_WORKFLOW_UPSTAGE_CRITERIA,
    PRACTICALITY_CRITERIA,
    PROBLEM_SOLVING_CRITERIA,
    TECHNICAL_CRITERIA,
    UPSTAGE_CRITERIA,
)


@dataclass(frozen=True)
class CriteriaItem:
    key: str
    name: str
    category: str
    max_score: int
    input: str
    rubric: str
    multi_rubric: Optional[str] = None


class CriteriaSet:
    def __init__(self, items: Iterable[CriteriaItem]):
        self.items = list(items)
        self._by_key = {item.key: item for item in self.items}

    def by_key(self, key: str) -> CriteriaItem:
        return self._by_key[key]

    def for_mode(self, mode: str) -> List[CriteriaItem]:
        if mode == "A":
            return [item for item in self.items if item.input == "document"]
        return list(self.items)

    def max_score_for_mode(self, mode: str) -> int:
        return sum(item.max_score for item in self.for_mode(mode))


def _scale_rubric(rubric: str, source_score: int, target_score: int) -> str:
    return (
        rubric.replace(f"({source_score}점)", f"({target_score}점)")
        .replace(f"<0-{source_score}>", f"<0-{target_score}>")
        .replace(f"총점\": <0-{source_score}>", f"총점\": <0-{target_score}>")
        + f"\n\n이 항목의 최종 점수는 반드시 0점부터 {target_score}점 사이의 정수로 산정하세요."
    )


DEFAULT_CRITERIA = [
    CriteriaItem(
        key="기획서_실용성",
        name="실용성",
        category="기획서 평가",
        max_score=20,
        input="document",
        rubric=PRACTICALITY_CRITERIA
        + "\n\n위 기획서 본문에서 실제 사용 시나리오, 반복 업무 제거, 적용 가능성을 중심으로 20점 만점으로 평가하세요.",
    ),
    CriteriaItem(
        key="문제해결_창의성",
        name="문제 해결 접근법 및 창의성 평가",
        category="기획서 평가",
        max_score=20,
        input="document",
        rubric=PROBLEM_SOLVING_CRITERIA
        + "\n\n위 기획서 본문에서 문제 정의의 구체성, 차별화된 관점, 솔루션 구성의 참신함을 종합해 20점 만점으로 평가하세요.",
    ),
    CriteriaItem(
        key="워크플로우_정상_작동",
        name="기술적 완성도",
        category="워크플로우 평가",
        max_score=25,
        input="workflow",
        rubric=_scale_rubric(TECHNICAL_CRITERIA, 15, 25),
        multi_rubric=_scale_rubric(MULTI_WORKFLOW_TECHNICAL_CRITERIA, 15, 25),
    ),
    CriteriaItem(
        key="Upstage_활용",
        name="업스테이지 제품 활용도",
        category="워크플로우 평가",
        max_score=15,
        input="workflow",
        rubric=UPSTAGE_CRITERIA
        + "\n\n이 항목의 최종 점수는 반드시 0점부터 15점 사이의 정수로 산정하세요.",
        multi_rubric=MULTI_WORKFLOW_UPSTAGE_CRITERIA
        + "\n\n이 항목의 최종 점수는 반드시 0점부터 15점 사이의 정수로 산정하세요.",
    ),
    CriteriaItem(
        key="기획_워크플로우_매핑",
        name="기획서 ↔ 워크플로우 매핑 정도",
        category="기획서 ↔ 워크플로우 매핑 정도",
        max_score=20,
        input="combined",
        rubric="""
# 기획서 ↔ 워크플로우 매핑 정도 평가 기준 (20점)

기획서에 적힌 문제, 사용자 시나리오, 핵심 기능, 자동화 흐름이 실제 n8n 워크플로우 JSON에 얼마나 충실하게 구현되어 있는지 평가하세요.

## 평가 관점
- 기획서의 핵심 사용자 문제와 워크플로우의 실제 동작 목적이 일치하는가?
- 기획서에서 약속한 입력, 처리 단계, 출력 또는 사용자 경험이 워크플로우에 반영되어 있는가?
- 기획서에는 중요한 기능으로 적혀 있지만 워크플로우에 빠진 부분이 있는가?
- 워크플로우에 구현된 기능이 기획 의도와 무관하게 벗어나 있거나 과도하지 않은가?
- 구현 범위가 기획된 방향을 검증 가능한 형태로 잘 보여주는가?

반드시 0점부터 20점 사이의 정수 점수와 함께 강점, 약점, 개선 제안을 JSON으로 작성하세요.
""",
    ),
]


class CriteriaLoader:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path if config_path is not None else os.getenv("CRITERIA_CONFIG_PATH")

    def load(self) -> CriteriaSet:
        items_by_key: Dict[str, CriteriaItem] = {item.key: item for item in DEFAULT_CRITERIA}
        if self.config_path:
            with open(self.config_path, "r", encoding="utf-8") as file:
                config = json.load(file)
            for override in config.get("criteria", []):
                key = override["key"]
                base = items_by_key.get(key)
                if base is None:
                    base = CriteriaItem(
                        key=key,
                        name=override.get("name", key),
                        category=override.get("category", "기타"),
                        max_score=int(override.get("max_score", 0)),
                        input=override.get("input", "document"),
                        rubric=override.get("rubric", ""),
                    )
                items_by_key[key] = replace(
                    base,
                    name=override.get("name", base.name),
                    category=override.get("category", base.category),
                    max_score=int(override.get("max_score", base.max_score)),
                    input=override.get("input", base.input),
                    rubric=override.get("rubric", base.rubric),
                    multi_rubric=override.get("multi_rubric", base.multi_rubric),
                )

        ordered = [items_by_key[item.key] for item in DEFAULT_CRITERIA if item.key in items_by_key]
        extra = [item for key, item in items_by_key.items() if key not in {default.key for default in DEFAULT_CRITERIA}]
        return CriteriaSet(ordered + extra)
