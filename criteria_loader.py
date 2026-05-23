"""Rubric loading for the single-team feedback agent."""

import json
import os
from dataclasses import dataclass, replace
from typing import Dict, Iterable, List, Optional

from evaluation_criteria import (
    MULTI_WORKFLOW_TECHNICAL_CRITERIA,
    MULTI_WORKFLOW_UPSTAGE_CRITERIA,
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


def _document_rubric(title: str, max_score: int, focus: str, criteria: str) -> str:
    return f"""
# {title} 평가 기준 ({max_score}점)

제출된 기획서 본문만 근거로 평가하세요. 추측하지 말고 본문에 드러난 내용으로만 판단합니다.

## 평가 초점
{focus}

## 세부 기준
{criteria}

반드시 0점부터 {max_score}점 사이의 정수 점수와 함께 강점, 약점, 개선 제안을 JSON으로 작성하세요.
"""


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
        rubric=_document_rubric(
            "실제 적용 가능성",
            20,
            "제안한 자동화가 실제 업무나 생활 문제에 지속적으로 적용될 수 있는지 평가합니다.",
            """
- 반복 업무나 실제 pain point를 구체적으로 포착했는가?
- 누가, 언제, 어떤 입력으로 사용하고 어떤 결과를 얻는지 사용 시나리오가 선명한가?
- 수동 작업 대비 시간 절감, 오류 감소, 품질 향상 등 적용 효과가 설득력 있게 제시되었는가?
- 단발성 아이디어가 아니라 운영 가능한 형태로 확장될 여지가 있는가?
""",
        ),
    ),
    CriteriaItem(
        key="자동화_효과",
        name="자동화 효과 및 사용자 편의성",
        category="실용성·비즈니스",
        max_score=10,
        input="document",
        rubric=_document_rubric(
            "자동화 효과 및 사용자 편의성",
            10,
            "자동화가 사용자에게 주는 효율 개선과 사용 편의성을 평가합니다.",
            """
- 자동화가 실제로 사용자의 반복 입력, 판단, 정리, 전달 과정을 줄이는가?
- 기술 지식이 낮은 사용자도 입력과 결과를 직관적으로 이해할 수 있는가?
- 결과물의 형태, 알림, 안내, 오류 대응이 사용자 흐름을 방해하지 않는가?
- 다른 사용자나 유사한 상황에서도 재사용 가능한 구조로 설명되었는가?
""",
        ),
    ),
    CriteriaItem(
        key="문제_정의_독창성",
        name="문제 정의의 독창성",
        category="창의성",
        max_score=15,
        input="document",
        rubric=_document_rubric(
            "문제 정의의 독창성",
            15,
            "자동화 대상으로 삼은 문제의 구체성, 차별성, 관점의 새로움을 평가합니다.",
            """
- 실제 사용자나 조직이 겪는 구체적이고 공감 가능한 문제를 정의했는가?
- 단순한 효율화 구호가 아니라 기존 방식의 한계와 원인을 설명했는가?
- 문제를 바라보는 관점이 흔한 예제나 템플릿과 구별되는가?
- 데이터, 사례, 정량/정성 근거로 문제의 중요성을 뒷받침했는가?
""",
        ),
    ),
    CriteriaItem(
        key="솔루션_참신함",
        name="솔루션 구성의 참신함",
        category="창의성",
        max_score=15,
        input="document",
        rubric=_document_rubric(
            "솔루션 구성의 참신함",
            15,
            "제안한 해결 방식과 자동화 흐름의 구성적 참신함을 평가합니다.",
            """
- 단순 API 호출 조합을 넘어 문제에 맞는 단계적 흐름이나 의사결정 구조를 제안했는가?
- 입력, 처리, 출력의 연결이 논리적이고 설득력 있게 구성되었는가?
- 조건 분기, 후처리, 피드백 루프, 외부 도구 연계 등 창의적 해결 방식을 고민했는가?
- 제한된 도구 안에서도 사용자 문제에 특화된 차별화된 아이디어가 드러나는가?
""",
        ),
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
