"""
LLM을 이용한 평가 유틸리티
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# .env 파일 로드 (프로젝트 루트 기준으로 명시적으로 로드)
# - 실행 위치(cwd)가 달라도 동작하도록 함
# - 권한/환경 제약이 있는 경우에도 import 자체가 죽지 않도록 방어
try:
    project_root = Path(__file__).resolve().parent
    dotenv_path = project_root / ".env"
    # env var가 이미 설정되어 있어도(.e.g. test_key) .env가 우선하도록 override=True
    load_dotenv(dotenv_path=dotenv_path, override=True)
except (PermissionError, OSError):
    # 환경에 따라 .env 접근이 막힐 수 있음 (예: 샌드박스)
    # 이 경우에도 OPENROUTER_API_KEY가 환경변수로 주어지면 정상 동작 가능
    pass


class LLMEvaluator:
    """OpenRouter의 openai/gpt-4o를 사용한 피드백 평가자."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: OpenAI API 키. None이면 환경변수에서 로드
        """
        self.api_key = os.getenv("OPENROUTER_API_KEY") if api_key is None else api_key
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY가 설정되지 않았습니다. "
                "프로젝트 루트의 .env 파일 또는 환경변수 OPENROUTER_API_KEY를 확인하세요."
            )
        if self.api_key.startswith(("sk-proj-", "sk-")) and not self.api_key.startswith("sk-or-"):
            raise ValueError(
                "OPENROUTER_API_KEY에는 OpenRouter API key를 넣어야 합니다. "
                "현재 값은 OpenAI API key처럼 보입니다. OpenRouter에서 발급한 sk-or-... 형식의 키를 설정해주세요."
            )

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ValueError("openai 패키지가 설치되어 있지 않습니다. requirements.txt를 설치해주세요.") from exc

        self.client = OpenAI(api_key=self.api_key, base_url="https://openrouter.ai/api/v1")
        self.model = "openai/gpt-4o"
        self.system_message = """당신은 n8n과 AI 자동화 산출물을 평가하는 한국어 피드백 코치입니다.

평가 기준은 명확하게 적용하되, 결과 설명은 비전공 참가자가 이해할 수 있게 친절한 존댓말로 작성하세요.
강점을 먼저 짚고, 약점은 "이 부분을 보완하면 더 좋아질 거예요"처럼 미래지향적으로 표현하세요.
모르는 기술 용어는 쉬운 말로 풀어 설명하고, 모든 응답은 JSON 형식으로만 작성하세요."""
    
    def evaluate(
        self, 
        data: str, 
        criteria: str, 
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        주어진 데이터를 기준에 따라 평가
        
        Args:
            data: 평가할 데이터 (JSON 문자열 또는 텍스트)
            criteria: 평가 기준
            max_retries: JSON 파싱 실패 시 최대 재시도 횟수
            
        Returns:
            평가 결과 딕셔너리
        """
        prompt = f"{criteria}\n\n## 평가 대상 데이터:\n{data}\n\n위 데이터를 심사 기준에 따라 평가하고, 반드시 JSON 형식으로만 응답하십시오."
        
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": self.system_message
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.0,  # 일관성을 위해 낮은 temperature 사용
                    response_format={"type": "json_object"}  # JSON 응답 강제
                )
                
                result = response.choices[0].message.content
                parsed_result = json.loads(result)
                
                return parsed_result
                
            except json.JSONDecodeError as e:
                if attempt < max_retries - 1:
                    print(f"JSON 파싱 실패 (시도 {attempt + 1}/{max_retries}), 재시도 중...")
                    continue
                else:
                    print(f"JSON 파싱 최종 실패: {e}")
                    return {
                        "error": "JSON 파싱 실패",
                        "raw_response": result,
                        "총점": 0
                    }
            
            except Exception as e:
                print(f"API 호출 실패: {e}")
                return {
                    "error": str(e),
                    "총점": 0
                }
        
        return {"error": "평가 실패", "총점": 0}

    def evaluate_feedback(
        self,
        data: str,
        criteria: str,
        item_key: str,
        item_name: str,
        max_score: int,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        prompt = f"""
{criteria}

## 평가 항목
- 키: {item_key}
- 이름: {item_name}
- 만점: {max_score}점

## 평가 대상 데이터
{data}

## 출력 형식
반드시 아래 JSON 형식으로만 응답하세요.
{{
  "점수": 0,
  "만점": {max_score},
  "강점": "참가자가 유지하면 좋은 점을 친절하게 설명",
  "약점": "보완하면 좋아질 점을 비전공자도 이해할 수 있게 설명",
  "개선_제안": "다음 제출 전에 바로 실행할 수 있는 구체적인 제안"
}}
"""
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.system_message},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )
                return json.loads(response.choices[0].message.content)
            except json.JSONDecodeError:
                if attempt == max_retries - 1:
                    return {"점수": 0, "만점": max_score, "강점": "", "약점": "LLM 응답을 JSON으로 해석하지 못했어요.", "개선_제안": "잠시 후 다시 실행해주세요."}
            except Exception as exc:
                return {"점수": 0, "만점": max_score, "강점": "", "약점": f"평가 호출 중 오류가 발생했어요: {exc}", "개선_제안": "API 키와 네트워크 상태를 확인한 뒤 다시 실행해주세요."}

        return {"점수": 0, "만점": max_score, "강점": "", "약점": "평가에 실패했어요.", "개선_제안": "잠시 후 다시 실행해주세요."}

    def synthesize_feedback(
        self,
        team_name: str,
        mode: str,
        max_score: int,
        item_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        prompt = f"""
다음 항목별 평가를 바탕으로 참가자에게 보여줄 전체 총평과 다음 액션 아이템 3개를 작성하세요.

팀명: {team_name}
평가 모드: {mode}
만점: {max_score}
항목별 평가:
{json.dumps(item_results, ensure_ascii=False, indent=2)}

반드시 아래 JSON 형식으로만 응답하세요.
{{
  "다음_액션_아이템": ["구체 액션 1", "구체 액션 2", "구체 액션 3"],
  "전체_총평": "친절한 한국어 한 단락 총평"
}}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_message},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(response.choices[0].message.content)
            actions = parsed.get("다음_액션_아이템") or []
            if not isinstance(actions, list):
                actions = [str(actions)]
            parsed["다음_액션_아이템"] = [str(action) for action in actions[:3]]
            parsed["전체_총평"] = str(parsed.get("전체_총평", ""))
            return parsed
        except Exception as exc:
            return {
                "다음_액션_아이템": ["평가 항목별 개선 제안을 먼저 확인해보세요."],
                "전체_총평": f"전체 총평 생성 중 오류가 발생했어요: {exc}",
            }
    
    def review_evaluation(
        self,
        data: str,
        criteria: str,
        initial_score: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        평가 결과를 재검토
        
        Args:
            data: 원본 데이터
            criteria: 평가 기준
            initial_score: 초기 평가 결과
            
        Returns:
            재검토 결과 딕셔너리
        """
        from evaluation_criteria import REVIEW_CRITERIA
        
        review_prompt = REVIEW_CRITERIA.format(
            data=data,
            criteria=criteria,
            initial_score=json.dumps(initial_score, ensure_ascii=False, indent=2)
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """
                        You are an expert workflow evaluator specializing in n8n JSON workflows, LLM-based automation, and Upstage API utilization analysis.
                        Your job is to strictly evaluate the submitted workflow and project description using the provided scoring rubrics.
                        You must never hallucinate, never assume the existence of missing nodes, and evaluate solely based on the JSON/text that is explicitly given.
                        
                        ⚠️ **CRITICAL: Strict Scoring Principles**
                        - Score very strictly. Do not give points unless criteria are perfectly met.
                        - "Almost complete" or "mostly good" is NOT sufficient. Only award points when criteria are fully satisfied.
                        - When uncertain or unclear, give conservative low scores.
                        - Do not award points for items that do not fully meet the criteria.
                        - Do NOT be generous with scores. Evaluate strictly and fairly.
                        - Be conservative and rigorous in your evaluation.
                        """
                    },
                    {
                        "role": "user",
                        "content": review_prompt
                    }
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content
            parsed_result = json.loads(result)
            
            return parsed_result
            
        except Exception as e:
            print(f"재검토 실패: {e}")
            return {
                "재검토_결과": "유지",
                "최종_점수": initial_score,
                "재검토_의견": f"재검토 중 오류 발생: {str(e)}"
            }


def safe_json_load(file_path: str) -> Optional[Dict[str, Any]]:
    """
    JSON 파일을 안전하게 로드
    
    Args:
        file_path: JSON 파일 경로
        
    Returns:
        파싱된 JSON 객체 또는 None
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None
    except Exception as e:
        print(f"파일 로드 오류: {e}")
        return None
