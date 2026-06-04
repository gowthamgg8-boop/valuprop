"""
ValUprop.in — LLM Service (Abstracted)
llm_service.py

Abstracts the LLM provider so we can swap OpenAI → Claude → self-hosted
without rewriting the rest of the backend.

Current provider: OpenAI GPT-4o-mini
Swap to Claude:   change PROVIDER = "anthropic" in .env

COST ESTIMATE (OpenAI GPT-4o-mini):
  Free estimate:   ~₹1–2 per request
  Detailed report: ~₹4–5 per request
  At ₹99 price point: sustainable.

SETUP:
  pip install openai
  Add OPENAI_API_KEY to .env

═══════════════════════════════════════════════════════════════════
LLM GUARDRAILS (added 2026-05-17)
═══════════════════════════════════════════════════════════════════
Every LLM call routes through call_llm / call_llm_with_search, so the
guardrails here cover the whole app:

  INPUT  — sanitize_user_input() neutralizes prompt-injection patterns
           in user-supplied free text (address, property name, etc.)
           and caps length. Sanitizes rather than rejects, so a real
           property at "12 System Street" still works.

  OUTPUT — validate_llm_output() scans the model's response for unsafe
           claims (absolute promises, direct buy/sell advice) and
           softens them in place to safe, informational phrasing.
           Softening events are logged for review.
"""

import os
import re
import json
import logging
from typing import Optional

logger = logging.getLogger("valuprop.llm")

PROVIDER      = os.getenv("LLM_PROVIDER", "openai")        # "openai" | "anthropic"
OPENAI_KEY    = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Model config — cheap fast model for MVP
OPENAI_MODEL    = os.getenv("OPENAI_MODEL",    "gpt-4o-mini")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

# Dev mode uses cheaper/faster model
DEV_MODE        = os.getenv("DEV_MODE", "false").lower() == "true"
if DEV_MODE:
    OPENAI_MODEL = "gpt-4o-mini"  # already cheap, keep same


# ═══════════════════════════════════════════════════════════════════
# LLM GUARDRAILS — input sanitization
# ═══════════════════════════════════════════════════════════════════

# Max length for any single user-supplied free-text field once it is
# embedded in a prompt. Long enough for a real Indian address; short
# enough that a giant payload cannot push real instructions out of
# the context window.
MAX_FIELD_LENGTH = 400

# Prompt-injection patterns. Each is neutralized (not rejected) — the
# matched text is replaced with a harmless placeholder so a property
# genuinely located on, say, "Ignore Street" still gets valued.
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions", re.I),
    re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior|the\s+above)", re.I),
    re.compile(r"forget\s+(?:everything|all|the\s+above|previous)", re.I),
    re.compile(r"you\s+are\s+now\s+(?:a|an)\b", re.I),
    re.compile(r"new\s+instructions?\s*:", re.I),
    re.compile(r"system\s+(?:prompt|message|override)", re.I),
    re.compile(r"</?(?:system|assistant|human)>", re.I),  # fake role tags
    re.compile(r"^\s*(?:system|assistant|human)\s*:", re.I | re.M),  # role-label lines
    re.compile(r"act\s+as\s+(?:a|an|if)\b", re.I),
    re.compile(r"pretend\s+(?:to\s+be|you)", re.I),
    re.compile(r"reveal\s+(?:your|the)\s+(?:system\s+)?(?:prompt|instructions)", re.I),
]


def sanitize_user_input(text: str) -> str:
    """Neutralize prompt-injection patterns in user-supplied free text
    and cap its length. Returns cleaned text safe to embed in a prompt.

    Non-destructive by intent: matched injection phrases are replaced
    with '[removed]' rather than the whole input being rejected, so a
    legitimate property is never blocked by an unlucky street name.
    """
    if not text:
        return ""
    cleaned = str(text)

    # Cap length first — bounds everything downstream.
    if len(cleaned) > MAX_FIELD_LENGTH:
        cleaned = cleaned[:MAX_FIELD_LENGTH]

    # Neutralize injection patterns.
    hit = False
    for pat in _INJECTION_PATTERNS:
        if pat.search(cleaned):
            hit = True
            cleaned = pat.sub("[removed]", cleaned)

    # Collapse excessive whitespace/newlines an attacker might use to
    # visually separate an injected instruction block.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{4,}", "   ", cleaned)

    if hit:
        logger.warning("LLM guardrail: prompt-injection pattern neutralized in user input")

    return cleaned.strip()


# ═══════════════════════════════════════════════════════════════════
# LLM GUARDRAILS — output validation
# ═══════════════════════════════════════════════════════════════════

# Unsafe output patterns mapped to safe, informational replacements.
# valUProp is an informational AI estimate, NOT a registered valuer or
# financial adviser — the model must never make absolute promises or
# give direct buy/sell instructions. Matches are softened in place.
_OUTPUT_SOFTEN_RULES = [
    # Absolute appreciation / return promises
    (re.compile(r"\bguaranteed?\s+(?:to\s+)?(?:appreciate|return|profit|grow)\w*", re.I),
     "likely to appreciate based on past trends"),
    (re.compile(r"\bwill\s+(?:definitely|certainly|surely)\s+(?:appreciate|increase|rise|grow)\w*", re.I),
     "may appreciate based on observed trends"),
    (re.compile(r"\bassured\s+returns?\b", re.I),
     "potential returns"),
    (re.compile(r"\bguaranteed?\s+(?:investment|profit|gains?)\b", re.I),
     "potential investment outcome"),
    (re.compile(r"\b(?:100%|completely|absolutely)\s+safe\s+investment\b", re.I),
     "a relatively stable investment option"),
    (re.compile(r"\bno\s+risk\b", re.I),
     "lower relative risk"),
    (re.compile(r"\brisk[- ]free\b", re.I),
     "lower-risk"),
    # Direct buy / sell advice
    (re.compile(r"\byou\s+should\s+(?:definitely\s+)?buy\b", re.I),
     "you may consider this property"),
    (re.compile(r"\byou\s+should\s+(?:definitely\s+)?sell\b", re.I),
     "you may wish to review your options"),
    (re.compile(r"\bwe\s+recommend\s+(?:buying|purchasing|selling)\b", re.I),
     "this analysis suggests reviewing"),
    (re.compile(r"\b(?:must|definitely)\s+(?:buy|invest|purchase)\s+(?:now|immediately|today)\b", re.I),
     "could be worth evaluating"),
    (re.compile(r"\bbest\s+time\s+to\s+buy\b", re.I),
     "a period worth evaluating"),
]


def _tidy_after_soften(text: str) -> str:
    """Repair small grammatical artifacts left by phrase replacement.

    Softening swaps a phrase mid-sentence without knowing its
    surroundings, which can leave doubled articles ("a a", "the the"),
    an article-then-article mismatch ("the a"), or doubled spaces.
    This pass cleans those up so a paid report still reads cleanly.
    """
    # Doubled / mismatched articles introduced by replacement.
    text = re.sub(r"\b(the)\s+(a|an|the)\b", r"\2", text, flags=re.I)
    text = re.sub(r"\b(a|an)\s+(a|an|the)\b", r"\2", text, flags=re.I)
    # Doubled spaces and space-before-punctuation.
    text = re.sub(r"  +", " ", text)
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    return text


def validate_llm_output(text: str) -> str:
    """Scan an LLM response for unsafe claims and soften them in place.

    Returns the cleaned text. Softening is deterministic — a known risky
    phrase maps to a known safe equivalent every time. Each softening is
    logged so a recurring trip indicates a prompt that needs fixing.
    """
    if not text:
        return text
    cleaned = text
    softened = 0
    for pat, replacement in _OUTPUT_SOFTEN_RULES:
        cleaned, n = pat.subn(replacement, cleaned)
        softened += n
    if softened:
        cleaned = _tidy_after_soften(cleaned)
        logger.warning(
            f"LLM guardrail: softened {softened} unsafe claim(s) in model output"
        )
    return cleaned


def _sanitize_prompt_pair(system_prompt: str, user_prompt: str) -> tuple:
    """Apply input guardrails. Only the user prompt is sanitized — the
    system prompt is developer-authored and trusted; the user prompt
    carries the user-supplied property fields."""
    return system_prompt, sanitize_user_input(user_prompt)


async def call_llm(
    system_prompt: str,
    user_prompt:   str,
    max_tokens:    int  = 1500,
    temperature:   float = 0.3,    # Low temp = more consistent valuations
    expect_json:   bool  = False,
) -> str:
    """
    Call the configured LLM provider.
    Returns the response text (or JSON string if expect_json=True).
    Raises RuntimeError on failure.

    Guardrails: user_prompt is sanitized before the call; the response
    is validated/softened before being returned. JSON responses skip
    output softening (structured data is validated by the caller) —
    softening runs on the prose the user actually reads.
    """
    system_prompt, user_prompt = _sanitize_prompt_pair(system_prompt, user_prompt)

    if PROVIDER == "anthropic":
        result = await _call_anthropic(system_prompt, user_prompt, max_tokens, temperature, expect_json)
    else:
        result = await _call_openai(system_prompt, user_prompt, max_tokens, temperature, expect_json)

    # Output guardrail — soften unsafe claims in free-text responses.
    # JSON responses are left intact here; the structured fields are
    # softened after parsing (see validate_report_dict below).
    if not expect_json:
        result = validate_llm_output(result)
    return result


async def _call_openai(
    system_prompt: str,
    user_prompt:   str,
    max_tokens:    int,
    temperature:   float,
    expect_json:   bool,
) -> str:
    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY not set in .env")

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_KEY)

        kwargs = dict(
            model       = OPENAI_MODEL,
            max_tokens  = max_tokens,
            temperature = temperature,
            messages    = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )
        if expect_json:
            kwargs["response_format"] = {"type": "json_object"}

        response = await client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content or ""
        logger.info(f"OpenAI usage — prompt: {response.usage.prompt_tokens}, "
                    f"completion: {response.usage.completion_tokens}")
        return text.strip()

    except Exception as e:
        logger.error(f"OpenAI call failed: {e}")
        raise RuntimeError(f"LLM call failed: {e}")


async def _call_anthropic(
    system_prompt: str,
    user_prompt:   str,
    max_tokens:    int,
    temperature:   float,
    expect_json:   bool,
) -> str:
    if not ANTHROPIC_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env")

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_KEY)

        sys_content = system_prompt
        if expect_json:
            sys_content += "\n\nRespond ONLY with valid JSON. No markdown, no preamble, no backticks."

        message = await client.messages.create(
            model      = ANTHROPIC_MODEL,
            max_tokens = max_tokens,
            system     = sys_content,
            messages   = [{"role": "user", "content": user_prompt}],
        )
        text = message.content[0].text if message.content else ""
        logger.info(f"Anthropic usage — input: {message.usage.input_tokens}, "
                    f"output: {message.usage.output_tokens}")
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
    Used for paid valuation reports — Claude searches MagicBricks/99acres/etc.
    via Anthropic's official web_search server tool, then synthesizes findings
    into a JSON report.

    Cost: ~$0.10 per call (search adds $10 per 1000 searches → ~₹15-20)
    Speed: 20-40 seconds (multiple search calls)

    Guardrails: user_prompt is sanitized before the call. JSON output is
    returned as-is here; callers should run validate_report_dict() on the
    parsed structure to soften the prose fields.
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
            model      = ANTHROPIC_MODEL,
            max_tokens = max_tokens,
            system     = sys_content,
            messages   = [{"role": "user", "content": user_prompt}],
            tools      = [{
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

        # Extract the FINAL text block (after all tool uses)
        # Claude's response contains: text → server_tool_use → web_search_tool_result → text → ... → final text
        final_text = ""
        searches_done = 0
        sources = []
        for block in message.content:
            if block.type == "text":
                final_text = block.text  # last text block wins
            elif block.type == "server_tool_use" and block.name == "web_search":
                searches_done += 1
            elif block.type == "web_search_tool_result":
                for result in (block.content or []):
                    if hasattr(result, "url") and hasattr(result, "title"):
                        sources.append({"url": result.url, "title": result.title})

        usage = message.usage
        try:
            web_count = getattr(usage, "server_tool_use", None)
            if web_count and hasattr(web_count, "web_search_requests"):
                web_count = web_count.web_search_requests
            elif isinstance(web_count, dict):
                web_count = web_count.get("web_search_requests", searches_done)
            else:
                web_count = searches_done
        except Exception:
            web_count = searches_done
        logger.info(
            f"Anthropic+search — input:{usage.input_tokens} output:{usage.output_tokens} "
            f"searches:{web_count} sources:{len(sources)}"
        )
        return final_text.strip()

    except Exception as e:
        logger.error(f"Anthropic web search call failed: {e}")
        raise RuntimeError(f"LLM web search call failed: {e}")


def parse_json_response(text: str) -> dict:
    """
    Safely parse JSON from LLM response.
    Handles cases where model wraps JSON in ```json ... ``` markdown.
    """
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse failed: {e}\nRaw text: {text[:500]}")
        raise ValueError(f"LLM returned invalid JSON: {e}")


# ═══════════════════════════════════════════════════════════════════
# LLM GUARDRAILS — output validation for parsed JSON reports
# ═══════════════════════════════════════════════════════════════════

def validate_report_dict(data):
    """Recursively apply validate_llm_output() to every string value in a
    parsed LLM JSON structure (report sections, risk points, opinions).

    The paid/free report JSON is nested (sections, lists of risk points,
    comparables). This walks the whole structure and softens unsafe
    claims in every prose field, leaving numbers and keys untouched.

    Call this on the dict returned by parse_json_response() before the
    report is stored or shown to the user.
    """
    if isinstance(data, dict):
        return {k: validate_report_dict(v) for k, v in data.items()}
    if isinstance(data, list):
        return [validate_report_dict(v) for v in data]
    if isinstance(data, str):
        return validate_llm_output(data)
    return data
