"""LLM Runtime — Sử dụng Groq API thay cho Google GenAI.

Model assignment (Groq):
  - Actor (attempt 1):  llama-3.3-70b-versatile         (model trung bình, dễ sai → tạo cơ hội Reflexion)
  - Actor (attempt 2+): openai/gpt-oss-120b             (model mạnh nhất + reflection memory → sửa lỗi)
  - Evaluator:          qwen/qwen3-32b                  (reasoning tốt, chấm điểm chính xác, tiết kiệm)
  - Reflector:          qwen/qwen3-32b                  (reasoning tốt, phân tích lỗi sâu)
"""

from __future__ import annotations

import json
import os
import re
import time

from dotenv import load_dotenv
from groq import Groq

from .prompts import ACTOR_SYSTEM, EVALUATOR_SYSTEM, REFLECTOR_SYSTEM
from .schemas import JudgeResult, QAExample, ReflectionEntry

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
load_dotenv()

_client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))

ACTOR_MODEL_WEAK = "llama-3.3-70b-versatile"  # Attempt 1: model trung bình → dễ sai hơn
ACTOR_MODEL_STRONG = "openai/gpt-oss-120b"  # Attempt 2+ / ReAct: model mạnh nhất
EVALUATOR_MODEL = "qwen/qwen3-32b"  # Evaluator: reasoning tốt, JSON output
REFLECTOR_MODEL = "qwen/qwen3-32b"  # Reflector: phân tích lỗi, đề xuất strategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _call_llm(model: str, system_prompt: str, user_prompt: str) -> tuple[str, int, int]:
    """Call Groq LLM and return (response_text, token_count, latency_ms).

    Includes retry logic with exponential backoff for rate limit (429) errors.
    """
    max_retries = 2
    base_delay = 15  # seconds — Groq free tier has very low TPM

    for attempt in range(max_retries + 1):
        try:
            start = time.perf_counter()

            completion = _client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_completion_tokens=1024,
                top_p=1,
                stream=False,
                stop=None,
            )

            latency_ms = int((time.perf_counter() - start) * 1000)

            text = completion.choices[0].message.content or ""

            # Token count from API metadata
            token_count = 0
            if completion.usage:
                token_count = (completion.usage.prompt_tokens or 0) + (
                    completion.usage.completion_tokens or 0
                )

            # Rate limit protection — wait 12s between calls (Groq free: 6000 TPM)
            time.sleep(12)

            return text.strip(), token_count, latency_ms

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate_limit" in error_str:
                wait = base_delay * (2**attempt)  # exponential backoff
                print(
                    f"  ⏳ Rate limited on {model}, retrying in {wait}s (attempt {attempt+1}/{max_retries})..."
                )
                time.sleep(wait)
            else:
                raise  # Re-raise non-rate-limit errors

    # If all retries exhausted, raise
    raise RuntimeError(
        f"Rate limit exceeded after {max_retries} retries for model {model}"
    )


def _parse_json(text: str) -> dict:
    """Extract JSON object from LLM response, handling markdown fences."""
    # Try to find JSON in markdown code blocks first
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # Try to find raw JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No JSON found in response: {text[:200]}")


def _build_context_str(example: QAExample) -> str:
    """Format context passages for the prompt."""
    parts = []
    for i, chunk in enumerate(example.context, 1):
        parts.append(f"[Passage {i}: {chunk.title}]\n{chunk.text}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Public API — same signatures as mock_runtime.py (+ token/latency returns)
# ---------------------------------------------------------------------------
def actor_answer(
    example: QAExample,
    attempt_id: int,
    agent_type: str,
    reflection_memory: list[str],
) -> tuple[str, int, int]:
    """Ask LLM to answer the question. Returns (answer, tokens, latency_ms).

    Strategy:
      - react agent:               luôn dùng model mạnh (chỉ có 1 lần thử duy nhất)
      - reflexion agent attempt 1:  dùng model yếu hơn → dễ sai → Reflector có việc
      - reflexion agent attempt 2+: dùng model mạnh + reflection memory → sửa lỗi
    """
    context_str = _build_context_str(example)

    user_prompt = f"Question: {example.question}\n\nContext:\n{context_str}"

    if reflection_memory:
        strategies = "\n".join(f"- {s}" for s in reflection_memory)
        user_prompt += (
            f"\n\nPrevious reflection strategies (follow these!):\n{strategies}"
        )

    # Chọn model theo agent_type và attempt_id
    if agent_type == "react":
        model = ACTOR_MODEL_STRONG  # ReAct: 1 shot duy nhất → dùng model mạnh
    elif attempt_id == 1:
        model = ACTOR_MODEL_WEAK  # Reflexion attempt 1 → model trung bình (dễ sai)
    else:
        model = ACTOR_MODEL_STRONG  # Reflexion attempt 2+ → model mạnh + memory

    text, tokens, latency = _call_llm(model, ACTOR_SYSTEM, user_prompt)

    # Clean up: remove quotes, periods, extra whitespace
    answer = text.strip().strip('"').strip("'").strip(".").strip()
    return answer, tokens, latency


def evaluator(example: QAExample, answer: str) -> tuple[JudgeResult, int, int]:
    """Ask LLM to evaluate the answer. Returns (JudgeResult, tokens, latency_ms)."""
    user_prompt = (
        f"Question: {example.question}\n"
        f"Gold answer: {example.gold_answer}\n"
        f"Predicted answer: {answer}\n\n"
        f"Evaluate and respond with JSON only."
    )

    text, tokens, latency = _call_llm(EVALUATOR_MODEL, EVALUATOR_SYSTEM, user_prompt)

    try:
        data = _parse_json(text)
        result = JudgeResult(
            score=int(data.get("score", 0)),
            reason=data.get("reason", "No reason provided"),
            missing_evidence=data.get("missing_evidence", []),
            spurious_claims=data.get("spurious_claims", []),
        )
    except (ValueError, json.JSONDecodeError, KeyError):
        # Fallback: simple string matching
        from .utils import normalize_answer

        is_correct = normalize_answer(example.gold_answer) == normalize_answer(answer)
        result = JudgeResult(
            score=1 if is_correct else 0,
            reason=f"Fallback evaluation (LLM parse failed): {'match' if is_correct else 'no match'}",
        )

    return result, tokens, latency


def reflector(
    example: QAExample, attempt_id: int, judge: JudgeResult
) -> tuple[ReflectionEntry, int, int]:
    """Ask LLM to reflect on the failure. Returns (ReflectionEntry, tokens, latency_ms)."""
    user_prompt = (
        f"Question: {example.question}\n"
        f"Attempt #{attempt_id} failed.\n"
        f"Evaluator reason: {judge.reason}\n"
        f"Missing evidence: {judge.missing_evidence}\n\n"
        f"Analyze the failure and respond with JSON only. Set attempt_id to {attempt_id}."
    )

    text, tokens, latency = _call_llm(REFLECTOR_MODEL, REFLECTOR_SYSTEM, user_prompt)

    try:
        data = _parse_json(text)
        entry = ReflectionEntry(
            attempt_id=data.get("attempt_id", attempt_id),
            failure_reason=data.get("failure_reason", judge.reason),
            lesson=data.get("lesson", "Need more careful reasoning."),
            next_strategy=data.get(
                "next_strategy", "Re-read all passages and complete every hop."
            ),
        )
    except (ValueError, json.JSONDecodeError, KeyError):
        # Fallback reflection
        entry = ReflectionEntry(
            attempt_id=attempt_id,
            failure_reason=judge.reason,
            lesson="Previous answer was incorrect; need to re-examine the context.",
            next_strategy="Re-read all passages carefully and complete every reasoning hop.",
        )

    return entry, tokens, latency
