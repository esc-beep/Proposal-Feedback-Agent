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
        key="워크플로우_정상_작동",
        name="워크플로우 정상 작동 여부",
        category="기술적 완성도",
        max_score=20,
        input="workflow",
        rubric=_scale_rubric(TECHNICAL_CRITERIA, 15, 20),
        multi_rubric=_scale_rubric(MULTI_WORKFLOW_TECHNICAL_CRITERIA, 15, 20),
    ),
    CriteriaItem(
        key="Upstage_활용",
        name="Upstage 서비스 활용 수준",
        category="기술적 완성도",
        max_score=20,
        input="workflow",
        rubric=_scale_rubric(UPSTAGE_CRITERIA, 15, 20),
        multi_rubric=_scale_rubric(MULTI_WORKFLOW_UPSTAGE_CRITERIA, 15, 20),
    ),
    CriteriaItem(
        key="실제_적용_가능성",
        name="실제 적용 가능성",
        category="실용성·비즈니스",
        max_score=20,
        input="document",
        rubric=PRACTICALITY_CRITERIA
        + "\n\n위 기획서 본문에서 실제 사용 시나리오, 반복 업무 제거, 적용 가능성을 중심으로 20점 만점으로 평가하세요.",
    ),
    CriteriaItem(
        key="자동화_효과",
        name="자동화 효과 및 사용자 편의성",
        category="실용성·비즈니스",
        max_score=10,
        input="document",
        rubric=PRACTICALITY_CRITERIA
        + "\n\n위 기획서 본문에서 자동화 효과, 사용 편의성, 재사용 가능성을 중심으로 10점 만점으로 평가하세요.",
    ),
    CriteriaItem(
        key="문제_정의_독창성",
        name="문제 정의의 독창성",
        category="창의성·문제 해결 접근법",
        max_score=15,
        input="document",
        rubric=PROBLEM_SOLVING_CRITERIA
        + "\n\n위 기획서 본문에서 문제 정의의 구체성, 차별화된 관점, 독창성을 중심으로 15점 만점으로 평가하세요.",
    ),
    CriteriaItem(
        key="솔루션_참신함",
        name="솔루션 구성의 참신함",
        category="창의성·문제 해결 접근법",
        max_score=15,
        input="document",
        rubric=PROBLEM_SOLVING_CRITERIA
        + "\n\n위 기획서 본문에서 솔루션 구성의 차별성, 전략적 조합, 창의적 해결 방식을 중심으로 15점 만점으로 평가하세요.",
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
