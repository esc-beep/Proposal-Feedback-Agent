import unittest
from types import SimpleNamespace

from admin_app import ITEM_SCORE_LABELS, format_admin_table_rows
from app import MAX_PDF_SIZE, validate_submission
from criteria_loader import CriteriaLoader
from feedback_renderer import FeedbackRenderer


class PrdAlignmentTest(unittest.TestCase):
    def test_criteria_modes_follow_prd_scores_and_keys(self):
        criteria = CriteriaLoader().load()

        mode_a = criteria.for_mode("A")
        mode_b = criteria.for_mode("B")

        self.assertEqual(
            [item.key for item in mode_a],
            [
                "실제_적용_가능성",
                "자동화_효과",
                "문제_정의_독창성",
                "솔루션_참신함",
            ],
        )
        self.assertEqual(criteria.max_score_for_mode("A"), 60)
        self.assertEqual(
            [item.key for item in mode_b],
            [
                "워크플로우_정상_작동",
                "Upstage_활용",
                "실제_적용_가능성",
                "자동화_효과",
                "문제_정의_독창성",
                "솔루션_참신함",
            ],
        )
        self.assertEqual(criteria.max_score_for_mode("B"), 100)

    def test_renderer_uses_prd_sections_and_mode_a_footer(self):
        result = {
            "팀명": "테스트팀",
            "모드": "A",
            "총점": 42,
            "만점": 60,
            "전체_총평": "좋아요.",
            "항목별": {
                "실제_적용_가능성": {"점수": 12, "만점": 20, "강점": "a", "약점": "b", "개선_제안": "c"},
                "자동화_효과": {"점수": 8, "만점": 10, "강점": "a", "약점": "b", "개선_제안": "c"},
                "문제_정의_독창성": {"점수": 10, "만점": 15, "강점": "a", "약점": "b", "개선_제안": "c"},
                "솔루션_참신함": {"점수": 12, "만점": 15, "강점": "a", "약점": "b", "개선_제안": "c"},
            },
            "다음_액션_아이템": [],
        }

        markdown = FeedbackRenderer().render(result)

        self.assertIn("**점수**: 42 / 60점", markdown)
        self.assertIn("### 💡 실용성·비즈니스 임팩트 (30점) - 20점", markdown)
        self.assertIn("### ✨ 창의성·문제 해결 접근법 (30점) - 22점", markdown)
        self.assertNotIn("🔧 기술적 완성도", markdown)
        self.assertIn("60점 만점", markdown)
        self.assertNotIn("40점 만점", markdown)

    def test_renderer_mode_b_includes_technical_prd_section(self):
        item = {"점수": 1, "만점": 1, "강점": "a", "약점": "b", "개선_제안": "c"}
        result = {
            "팀명": "테스트팀",
            "모드": "B",
            "총점": 6,
            "만점": 100,
            "전체_총평": "좋아요.",
            "항목별": {
                "워크플로우_정상_작동": {**item, "점수": 15, "만점": 20},
                "Upstage_활용": {**item, "점수": 16, "만점": 20},
                "실제_적용_가능성": {**item, "점수": 17, "만점": 20},
                "자동화_효과": {**item, "점수": 8, "만점": 10},
                "문제_정의_독창성": {**item, "점수": 12, "만점": 15},
                "솔루션_참신함": {**item, "점수": 13, "만점": 15},
            },
            "다음_액션_아이템": [],
        }

        markdown = FeedbackRenderer().render(result)

        self.assertIn("### 🔧 기술적 완성도 (40점) - 31점", markdown)
        self.assertIn("워크플로우 정상 작동 여부 (20점)", markdown)
        self.assertIn("Upstage 서비스 활용 수준 (20점)", markdown)
        self.assertNotIn("기획서 ↔ 워크플로우 매핑", markdown)

    def test_admin_columns_use_prd_item_labels_and_missing_scores(self):
        self.assertEqual(
            ITEM_SCORE_LABELS,
            [
                ("워크플로우_정상_작동", "워크플로우 정상 작동"),
                ("Upstage_활용", "Upstage 활용"),
                ("실제_적용_가능성", "실제 적용 가능성"),
                ("자동화_효과", "자동화 효과"),
                ("문제_정의_독창성", "문제 정의 독창성"),
                ("솔루션_참신함", "솔루션 참신함"),
            ],
        )
        rows = format_admin_table_rows([
            {
                "id": 1,
                "created_at": "2026-05-23T10:00:00",
                "team_name": "테스트팀",
                "mode": "A",
                "total_score": 42,
                "max_score": 60,
                "item_scores": {"실제_적용_가능성": {"점수": 12, "만점": 20}},
            }
        ])

        self.assertEqual(rows[0]["워크플로우 정상 작동"], "-")
        self.assertEqual(rows[0]["실제 적용 가능성"], "12 / 20")

    def test_validate_submission_rejects_pdf_larger_than_20mb(self):
        oversized_pdf = SimpleNamespace(size=MAX_PDF_SIZE + 1)

        errors = validate_submission("테스트팀", oversized_pdf, None, True, 0)

        self.assertIn("기획서 PDF는 20MB 이하만 업로드할 수 있어요.", errors)


if __name__ == "__main__":
    unittest.main()
