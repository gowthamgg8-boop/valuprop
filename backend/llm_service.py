"""
ValUprop.in — LLM Service (Abstracted)
llm_service.py

Abstracts the LLM provider so we can swap OpenAI → Claude → self-hosted
without rewriting the rest of the backend.

Current provider: Anthropic Claude (claude-sonnet-4-5)

COST ESTIMATE (Anthropic Claude):
  Free estimate:   ~500 tokens → Rs.1–2 per request
  Detailed report: ~3000 tokens + web search → Rs.15–20 per request
  At Rs.199 price point: sustainable.

SETUP:
  pip install anthropic
  Add ANTHROPIC_API_KEY to .env

═══════════════════════════════════════════════════════════════════
LLM GUARDRAILS (added 2026-05-17)
═══════════════════════════════════════════════════════════════════
Every LLM call routes through call_llm / call_llm_with_search, so the
guardrails here cover the whole app:

  INPUT  — sanitize_user_input() neutralizes prompt-injection patterns
           in user-supplied free text (address, property name, etc.)
           and caps length.

  OUTPUT — validate_llm_output() scans the model response for unsafe
           claims and softens them in place.
"""

import os
import re
import json
import logging
from typing import Optional

logger = logging.getLogger("valuprop.llm")

PROVIDER      = os.getenv("LLM_PROVIDER", "anthropic")     # "openai" | "anthropic"
OPENAI_KEY    = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

OPENAI_MODEL    = os.getenv("OPENAI_MODEL",    "gpt-4o-mini")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
if DEV_MODE:
    OPENAI_MODEL = "gpt-4o-mini"


# ═══════════════════════════════════════════════════════════════════
# LLM GUARDRAILS — input sanitization
# ═══════════════════════════════════════════════════════════════════

MAX_FIELD_LENGTH = 400

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions", re.I),
    re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior|the\s+above)", re.I),
    re.compile(r"forget\s+(?:everything|all|the\s+above|previous)", re.I),
    re.compile(r"you\s+are\s+now\s+(?:a|an)\b", re.I),
    re.compile(r"new\s+instructions?\s*:", re.I),
    re.compile(r"system\s+(?:prompt|message|override)", re.I),
    re.compile(r"</?(?:system|assistant|human)>", re.I),
    re.compile(r"^\s*(?:system|assistant|human)\s*:", re.I | re.M),
    re.compile(r"act\s+as\s+(?:a|an|if)\b", re.I),
    re.compile(r"pretend\s+(?:to\s+be|you)", re.I),
    re.compile(r"reveal\s+(?:your|the)\s+(?:system\s+)?(?:prompt|instructions)", re.I),
]


def sanitize_user_input(text: str) -> str:
    if not text:
        return ""
    cleaned = str(text)
    if len(cleaned) > MAX_FIELD_LENGTH:
        cleaned = cleaned[:MAX_FIELD_LENGTH]
    hit = False
    for pat in _INJECTION_PATTERNS:
        if pat.search(cleaned):
            hit = True
            cleaned = pat.sub("[removed]", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{4,}", "   ", cleaned)
    if hit:
        logger.warning("LLM guardrail: prompt-injection pattern neutralized in user input")
    return cleaned.strip()


# ═══════════════════════════════════════════════════════════════════
# LLM GUARDRAILS — output validation
# ═══════════════════════════════════════════════════════════════════

_OUTPUT_SOFTEN_RULES = [
    (re.compile(r"\bguaranteed?\s+(?:to\s+)?(?:appreciate|return|profit|grow)\w*", re.I),
     "likely to appreciate based on past trends"),
    (re.compile(r"\bwill\s+(?:definitely|certainly|surely)\s+(?:appreciate|increase|rise|grow)\w*", re.I),
     "may appreciate based on observed trends"),
    (re.compile(r"\bassured\s+returns?\b", re.I), "potential returns"),
    (re.compile(r"\bguaranteed?\s+(?:investment|profit|gains?)\b", re.I), "potential investment outcome"),
    (re.compile(r"\b(?:100%|completely|absolutely)\s+safe\s+investment\b", re.I), "a relatively stable investment option"),
    (re.compile(r"\bno\s+risk\b", re.I), "lower relative risk"),
    (re.compile(r"\brisk[- ]free\b", re.I), "lower-risk"),
    (re.compile(r"\byou\s+should\s+(?:definitely\s+)?buy\b", re.I), "you may consider this property"),
    (re.compile(r"\byou\s+should\s+(?:definitely\s+)?sell\b", re.I), "you may wish to review your options"),
    (re.compile(r"\bwe\s+recommend\s+(?:buying|purchasing|selling)\b", re.I), "this analysis suggests reviewing"),
    (re.compile(r"\b(?:must|definitely)\s+(?:buy|invest|purchase)\s+(?:now|immediately|today)\b", re.I), "could be worth evaluating"),
    (re.compile(r"\bbest\s+time\s+to\s+buy\b", re.I), "a period worth evaluating"),
]


def _tidy_after_soften(text: str) -> str:
    text = re.sub(r"\b(the)\s+(a|an|the)\b", r"\2", text, flags=re.I)
    text = re.sub(r"\b(a|an)\s+(a|an|the)\b", r"\2", text, flags=re.I)
    text = re.sub(r"  +", " ", text)
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    return text


def validate_llm_output(text: str) -> str:
    if not text:
        return text
    cleaned = text
    softened = 0
    for pat, replacement in _OUTPUT_SOFTEN_RULES:
        cleaned, n = pat.subn(replacement, cleaned)
        softened += n
    if softened:
        cleaned = _tidy_after_soften(cleaned)
        logger.warning(f"LLM guardrail: softened {softened} unsafe claim(s) in model output")
    return cleaned


def _sanitize_prompt_pair(system_prompt: str, user_prompt: str) -> tuple:
    return system_prompt, sanitize_user_input(user_prompt)


async def call_llm(
    system_prompt: str,
    user_prompt:   str,
    max_tokens:    int   = 1500,
    temperature:   float = 0.3,
    expect_json:   bool  = False,
) -> str:
    system_prompt, user_prompt = _sanitize_prompt_pair(system_prompt, user_prompt)
    if PROVIDER == "anthropic":
        result = await _call_anthropic(system_prompt, user_prompt, max_tokens, temperature, expect_json)
    else:
        result = await _call_openai(system_prompt, user_prompt, max_tokens, temperature, expect_json)
    if not expect_json:
        result = validate_llm_output(result)
    return result


async def _call_openai(
    system_prompt: str, user_prompt: str,
    max_tokens: int, temperature: float, expect_json: bool,
) -> str:
    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY not set in .env")
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_KEY)
        kwargs = dict(
            model=OPENAI_MODEL, max_tokens=max_tokens, temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )
        if expect_json:
            kwargs["response_format"] = {"type": "json_object"}
        response = await client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content or ""
        logger.info(f"OpenAI usage — prompt: {response.usage.prompt_tokens}, completion: {response.usage.completion_tokens}")
        return text.strip()
    except Exception as e:
        logger.error(f"OpenAI call failed: {e}")
        raise RuntimeError(f"LLM call failed: {e}")


async def _call_anthropic(
    system_prompt: str, user_prompt: str,
    max_tokens: int, temperature: float, expect_json: bool,
) -> str:
    if not ANTHROPIC_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_KEY)
        sys_content = system_prompt
        if expect_json:
            sys_content += "\n\nRespond ONLY with valid JSON. No markdown, no preamble, no backticks."
        message = await client.messages.create(
            model=ANTHROPIC_MODEL, max_tokens=max_tokens,
            system=sys_content,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = message.content[0].text if message.content else ""
        logger.info(f"Anthropic usage — input: {message.usage.input_tokens}, output: {message.usage.output_tokens}")
        return text.strip()
    except Exception as e:
        logger.error(f"Anthropic call failed: {e}")
        raise RuntimeError(f"LLM call failed: {e}")


# ═══════════════════════════════════════════════════════════════════
# WEB SEARCH ENABLED LLM CALL — for paid reports only
# ═══════════════════════════════════════════════════════════════════

async def call_llm_with_search(
    system_prompt: str,
    user_prompt:   str,
    max_tokens:    int  = 4000,
    max_searches:  int  = 5,
    expect_json:   bool = True,
) -> str:
    """
    Call Claude with web_search tool enabled.
    Used for paid valuation reports — Claude searches for current market data
    then synthesizes into a JSON report.
    """
    if PROVIDER != "anthropic":
        raise RuntimeError("Web search is only supported via Anthropic provider")
    if not ANTHROPIC_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    system_prompt, user_prompt = _sanitize_prompt_pair(system_prompt, user_prompt)

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_KEY)

        sys_content = system_prompt
        if expect_json:
            sys_content += (
                "\n\nAfter completing your web research, provide your final answer "
                "as valid JSON only. No markdown, no preamble, no backticks around the JSON."
            )

        message = await client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=sys_content,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[{
                "type":     "web_search_20250305",
                "name":     "web_search",
                "max_uses": max_searches,
                "user_location": {
                    "type":    "approximate",
                    "country": "IN",
                    "timezone":"Asia/Kolkata",
                },
            }],
        )

        # Extract the final text block (after all tool uses)
        final_text = ""
        searches_done = 0
        sources = []
        for block in message.content:
            if block.type == "text":
                final_text = block.text   # last text block wins
            elif block.type == "server_tool_use" and block.name == "web_search":
                searches_done += 1
            elif block.type == "web_search_tool_result":
                for result in (block.content or []):
                    if hasattr(result, "url") and hasattr(result, "title"):
                        sources.append({"url": result.url, "title": result.title})

        # ── FIXED: safe usage stats extraction ───────────────────
        # Previously crashed with: 'dict' object has no attribute 'web_search_requests'
        # because the Anthropic SDK may return usage as a dict or object depending on version.
        try:
            stu = getattr(message.usage, "server_tool_use", None)
            if stu is None:
                web_count = searches_done
            elif isinstance(stu, dict):
                web_count = stu.get("web_search_requests", searches_done)
            else:
                web_count = getattr(stu, "web_search_requests", searches_done)
        except Exception:
            web_count = searches_done
        # ─────────────────────────────────────────────────────────

        logger.info(
            f"Anthropic+search — input:{message.usage.input_tokens} "
            f"output:{message.usage.output_tokens} "
            f"searches:{web_count} sources:{len(sources)}"
        )
        return final_text.strip()

    except Exception as e:
        logger.error(f"Anthropic web search call failed: {e}")
        raise RuntimeError(f"LLM web search call failed: {e}")


def parse_json_response(text: str) -> dict:
    """Safely parse JSON from LLM response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    text = text.strip()
    try:
        data = json.loads(text)
        if "section_a" in data or "section_b" in data:
            return data
        extracted = _extract_report_fields(data)
        if extracted.get("section_a") or extracted.get("section_b"):
            return extracted
        return data
    except json.JSONDecodeError:
        pass
    try:
        fixed = _repair_truncated_json(text)
        if fixed:
            return fixed
    except Exception:
        pass
    try:
        extracted = _regex_extract_fields(text)
        if extracted.get("section_a") or extracted.get("section_b"):
            logger.warning("JSON parse: used regex fallback extraction")
            return extracted
    except Exception:
        pass
    logger.error(f"JSON parse failed completely\nRaw text: {text[:500]}")
    raise ValueError("LLM returned invalid JSON — could not extract report fields")


def _extract_report_fields(data: dict, depth: int = 0) -> dict:
    if depth > 5:
        return {}
    result = {}
    report_keys = {
        "section_a","section_b","section_c","section_d","section_e",
        "section_f","section_g","value_lo","value_hi","confidence",
        "comparables","land_value_lo","land_value_hi",
        "building_value_lo","building_value_hi","adj_value_lo","adj_value_hi",
        "micro_market","pricing_signals","risk_diligence",
    }
    if isinstance(data, dict):
        found = {k: v for k, v in data.items() if k in report_keys}
        if found:
            result.update(found)
        for v in data.values():
            if isinstance(v, dict):
                nested = _extract_report_fields(v, depth+1)
                for k, val in nested.items():
                    if k not in result:
                        result[k] = val
    return result


def _repair_truncated_json(text: str) -> dict:
    opens  = text.count("{") - text.count("}")
    closes = text.count("[") - text.count("]")
    if opens > 0 or closes > 0:
        fixed = text + "]" * max(0, closes) + "}" * max(0, opens)
        try:
            data = json.loads(fixed)
            return _extract_report_fields(data) or data
        except Exception:
            pass
    return {}


def _regex_extract_fields(text: str) -> dict:
    result = {}
    pattern = re.compile(
        r'"(section_[a-g]|value_lo|value_hi|confidence|micro_market|pricing_signals|risk_diligence)"\s*:\s*("(?:[^"\\]|\\.)*"|[-\d.]+)',
        re.S
    )
    for match in pattern.finditer(text):
        key = match.group(1)
        val = match.group(2)
        if val.startswith('"'): 
            val = val[1:-1].replace('\\"''"').replace("\\n", "\n")
        else:
            try:
                val = float(val)
            except Exception:
                pass
        result[key] = val
    return result


def validate_report_dict(data):
    """Recursively soften unsafe claims in all string values of a parsed report dict."""
    if isinstance(data, dict):
        return {k: validate_report_dict(v) for k, v in data.items()}
    if isinstance(data, list):
        return [validate_report_dict(v) for v in data]
    if isinstance(data, str):
        return validate_llm_output(data)
    return data
