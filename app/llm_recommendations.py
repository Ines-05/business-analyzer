from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from openai import OpenAI

GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"
DEFAULT_MODEL = "openai/gpt-5.2"
MAX_RECOMMENDATIONS = 5
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_RETRY_ATTEMPTS = 1

logger = logging.getLogger(__name__)


class RecommendationGenerationError(RuntimeError):
    def __init__(self, message: str, *, debug: dict[str, Any] | None = None):
        super().__init__(message)
        self.debug = debug or {}


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise RecommendationGenerationError("LLM returned an empty response.")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise RecommendationGenerationError("LLM response did not contain valid JSON.")
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise RecommendationGenerationError("LLM JSON could not be parsed.") from exc


def _normalize_priority(value: Any) -> str:
    label = str(value or "").strip().lower()
    if label == "high":
        return "High"
    if label == "low":
        return "Low"
    return "Medium"


def _normalize_recommendation(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None

    title = str(item.get("title") or "").strip()
    insight = str(item.get("insight") or "").strip()
    action = str(item.get("action") or "").strip()
    if not title or not insight or not action:
        return None

    priority = _normalize_priority(item.get("priority"))
    icon = str(item.get("icon") or "").strip()
    if not icon:
        icon = {"High": "Alert", "Medium": "Focus", "Low": "Idea"}[priority]

    return {
        "priority": priority,
        "icon": icon,
        "title": title[:120],
        "insight": insight[:600],
        "action": action[:400],
    }


def _build_prompt_payload(metrics: dict, company_name: str) -> dict:
    return {
        "company_name": company_name.strip() or "Unknown company",
        "kpis": metrics.get("kpis", {}),
        "revenue_trend": metrics.get("revenue_trend", []),
        "top_products": metrics.get("top_products", []),
        "product_share": metrics.get("product_share", []),
        "meta": metrics.get("meta", {}),
    }


def _response_format_json_schema() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "business_recommendations",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["recommendations"],
                "properties": {
                    "recommendations": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 5,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["priority", "icon", "title", "insight", "action"],
                            "properties": {
                                "priority": {"type": "string", "enum": ["High", "Medium", "Low"]},
                                "icon": {"type": "string"},
                                "title": {"type": "string"},
                                "insight": {"type": "string"},
                                "action": {"type": "string"},
                            },
                        },
                    }
                },
            },
        },
    }


def _response_format_legacy_json() -> dict[str, Any]:
    schema = _response_format_json_schema()["json_schema"]["schema"]
    return {
        "type": "json",
        "name": "business_recommendations",
        "description": "3-5 startup business recommendations with priorities and actions.",
        "schema": schema,
    }


def resolve_model(model: str | None = None) -> str:
    return (model or os.getenv("RECOMMENDATION_MODEL") or DEFAULT_MODEL).strip()


def resolve_timeout_seconds() -> float:
    raw = (os.getenv("AI_GATEWAY_TIMEOUT_SECONDS") or "").strip()
    if not raw:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    if value <= 0:
        return DEFAULT_TIMEOUT_SECONDS
    return value


def resolve_retry_attempts() -> int:
    raw = (os.getenv("AI_GATEWAY_RETRY_ATTEMPTS") or "").strip()
    if not raw:
        return DEFAULT_RETRY_ATTEMPTS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_RETRY_ATTEMPTS
    return max(0, value)


def _should_retry_gateway_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "timed out" in message
        or "timeout" in message
        or "temporarily unavailable" in message
        or "connection reset" in message
        or "502" in message
        or "503" in message
        or "504" in message
    )


def _create_completion_with_fallback(
    client: OpenAI,
    request_args: dict[str, Any],
    attempt_debug: dict[str, Any],
) -> Any:
    try:
        attempt_debug["response_format"] = "json_schema"
        return client.chat.completions.create(
            **request_args,
            response_format=_response_format_json_schema(),
        )
    except Exception as exc:
        message = str(exc)
        attempt_debug["json_schema_error"] = message
        if "response_format" not in message.lower():
            raise
        # Legacy JSON mode fallback for providers/models that reject json_schema.
        attempt_debug["response_format"] = "legacy_json"
        return client.chat.completions.create(
            **request_args,
            response_format=_response_format_legacy_json(),
        )


def generate_recommendations_with_debug(
    metrics: dict, company_name: str = "", model: str | None = None
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    api_key = os.getenv("AI_GATEWAY_API_KEY", "").strip()
    if not api_key:
        raise RecommendationGenerationError(
            "AI_GATEWAY_API_KEY is missing; cannot generate LLM recommendations."
        )

    selected_model = resolve_model(model)
    timeout_seconds = resolve_timeout_seconds()
    retry_attempts = resolve_retry_attempts()
    client = OpenAI(api_key=api_key, base_url=GATEWAY_BASE_URL, timeout=timeout_seconds)

    system_prompt = (
        "You are a senior business analyst for SME/PME startups. "
        "Given KPI and sales trend data, produce concrete strategic recommendations. "
        "Each recommendation must reference at least one numeric signal from the data. "
        "Return only JSON with this schema: "
        '{"recommendations":[{"priority":"High|Medium|Low","icon":"string","title":"string","insight":"string","action":"string"}]}. '
        "Generate 3 to 5 recommendations."
        "Always respond in french, regardless of the input language."
    )
    user_payload = _build_prompt_payload(metrics=metrics, company_name=company_name)
    request_args = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
    }

    debug: dict[str, Any] = {
        "gateway_base_url": GATEWAY_BASE_URL,
        "model": selected_model,
        "timeout_seconds": timeout_seconds,
        "retry_attempts": retry_attempts,
        "payload_summary": {
            "company_name": user_payload.get("company_name"),
            "row_count": metrics.get("meta", {}).get("row_count"),
            "trend_points": len(metrics.get("revenue_trend", [])),
            "top_products": len(metrics.get("top_products", [])),
        },
        "attempts": [],
    }
    overall_start = time.perf_counter()

    logger.info(
        "LLM recommendation request started | model=%s timeout=%ss retries=%s",
        selected_model,
        timeout_seconds,
        retry_attempts,
    )

    response = None
    last_error: Exception | None = None
    attempts_total = retry_attempts + 1
    for attempt in range(attempts_total):
        attempt_debug: dict[str, Any] = {"attempt": attempt + 1}
        attempt_start = time.perf_counter()
        try:
            response = _create_completion_with_fallback(
                client=client,
                request_args=request_args,
                attempt_debug=attempt_debug,
            )
            attempt_debug["status"] = "ok"
            attempt_debug["duration_ms"] = round((time.perf_counter() - attempt_start) * 1000, 1)
            debug["attempts"].append(attempt_debug)
            break
        except Exception as exc:
            last_error = exc
            attempt_debug["status"] = "error"
            attempt_debug["error_type"] = type(exc).__name__
            attempt_debug["error"] = str(exc)
            attempt_debug["duration_ms"] = round((time.perf_counter() - attempt_start) * 1000, 1)
            debug["attempts"].append(attempt_debug)

            logger.warning(
                "LLM recommendation attempt failed | attempt=%s/%s error=%s",
                attempt + 1,
                attempts_total,
                exc,
            )

            if attempt >= retry_attempts or not _should_retry_gateway_error(exc):
                debug["duration_ms"] = round((time.perf_counter() - overall_start) * 1000, 1)
                raise RecommendationGenerationError(
                    f"Gateway request failed: {exc}",
                    debug=debug,
                ) from exc
            time.sleep(min(1.5 * (attempt + 1), 4.0))

    if response is None and last_error is not None:
        debug["duration_ms"] = round((time.perf_counter() - overall_start) * 1000, 1)
        raise RecommendationGenerationError(
            f"Gateway request failed: {last_error}",
            debug=debug,
        ) from last_error

    content = ""
    if response.choices and response.choices[0].message:
        content = response.choices[0].message.content or ""

    debug["response_id"] = getattr(response, "id", None)
    if response.choices:
        debug["finish_reason"] = getattr(response.choices[0], "finish_reason", None)
    debug["response_content_length"] = len(content)

    try:
        parsed = _extract_json(content)
    except RecommendationGenerationError as exc:
        debug["response_preview"] = content[:400]
        debug["duration_ms"] = round((time.perf_counter() - overall_start) * 1000, 1)
        raise RecommendationGenerationError(str(exc), debug=debug) from exc

    raw_items = parsed.get("recommendations", [])
    recommendations: list[dict[str, str]] = []
    for item in raw_items:
        normalized = _normalize_recommendation(item)
        if normalized:
            recommendations.append(normalized)
        if len(recommendations) >= MAX_RECOMMENDATIONS:
            break

    debug["raw_recommendations_count"] = len(raw_items) if isinstance(raw_items, list) else 0
    debug["normalized_recommendations_count"] = len(recommendations)
    debug["duration_ms"] = round((time.perf_counter() - overall_start) * 1000, 1)

    if len(recommendations) < 3:
        raise RecommendationGenerationError(
            "LLM response did not contain at least 3 valid recommendations.",
            debug=debug,
        )

    logger.info(
        "LLM recommendation request succeeded | model=%s recommendations=%s duration_ms=%s",
        selected_model,
        len(recommendations),
        debug["duration_ms"],
    )
    return recommendations, debug


def generate_recommendations(
    metrics: dict, company_name: str = "", model: str | None = None
) -> list[dict[str, str]]:
    recommendations, _ = generate_recommendations_with_debug(
        metrics=metrics,
        company_name=company_name,
        model=model,
    )
    return recommendations
