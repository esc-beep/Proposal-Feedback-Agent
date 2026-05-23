"""Markdown rendering for feedback JSON."""

import re
from datetime import datetime
from typing import Any, Dict, Iterable, List


class FeedbackRenderer:
    def render(self, result: Dict[str, Any]) -> str:
        mode = result.get("모드", "B")
        team_name = result.get("팀명", "팀")
        title = f"# {team_name} 기획안 피드백" if mode == "A" else f"# {team_name} 피드백"
        score_label = "점수" if mode == "A" else "총점"
        note = " _(기획서 평가만 진행되었습니다. 워크플로우는 평가에 포함되지 않았어요.)_" if mode == "A" else ""

        lines = [
            title,
            "",
            f"**{score_label}**: {result.get('총점', 0)} / {result.get('만점', 0)}점{note}",
            "",
            "## 한 줄 총평",
            str(result.get("전체_총평", "")),
            "",
            "## 항목별 피드백",
            "",
        ]

        if mode == "B":
            lines.extend(self._render_category(result, "🔧 기술적 완성도", [
                ("워크플로우_정상_작동", "워크플로우 정상 작동 여부"),
                ("Upstage_활용", "Upstage 서비스 활용 수준"),
            ]))

        lines.extend(self._render_category(result, "💡 실용성·비즈니스 임팩트", [
            ("실제_적용_가능성", "실제 적용 가능성"),
            ("자동화_효과", "자동화 효과 및 사용자 편의성"),
        ]))

        lines.extend(self._render_category(result, "✨ 창의성·문제 해결 접근법", [
            ("문제_정의_독창성", "문제 정의의 독창성"),
            ("솔루션_참신함", "솔루션 구성의 참신함"),
        ]))

        lines.extend(["## 다음 액션 아이템"])
        actions = result.get("다음_액션_아이템") or []
        for index, action in enumerate(actions, 1):
            lines.append(f"{index}. {action}")

        if mode == "A":
            footer = "_이 피드백은 기획서만 보고 60점 만점으로 작성되었어요. n8n 워크플로우를 만든 뒤 다시 돌리면 100점 만점 전체 평가를 받을 수 있어요._"
        else:
            footer = "_이 피드백은 자동 생성되었어요. 궁금한 점은 행사 멘토에게 문의해주세요._"
        lines.extend(["", "---", footer])
        return "\n".join(lines).strip() + "\n"

    def _render_category(self, result: Dict[str, Any], title: str, items: Iterable[tuple]) -> List[str]:
        details = result.get("항목별", {})
        present_items = [(key, label) for key, label in items if key in details]
        if not present_items:
            return []

        category_score = sum(int(details[key].get("점수", 0)) for key, _ in present_items)
        category_max = sum(int(details[key].get("만점", 0)) for key, _ in present_items)
        lines = [f"### {title} ({category_max}점) - {category_score}점", ""]

        for key, label in present_items:
            item = details[key]
            lines.extend([
                f"**{label} ({item.get('만점', 0)}점) - {item.get('점수', 0)}점**",
                f"- **강점**: {item.get('강점', '')}",
                f"- **약점**: {item.get('약점', '')}",
                f"- **개선 제안**: {item.get('개선_제안', '')}",
                "",
            ])
        return lines


def safe_feedback_filename(team_name: str, now: datetime | None = None) -> str:
    timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M")
    safe_name = re.sub(r'[\\/:*?"<>|]+', "_", team_name).strip() or "team"
    return f"{safe_name}_피드백_{timestamp}.md"
