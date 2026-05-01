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
"""

import os
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
    """
    if PROVIDER == "anthropic":
        return await _call_anthropic(system_prompt, user_prompt, max_tokens, temperature, expect_json)
    else:
        return await _call_openai(system_prompt, user_prompt, max_tokens, temperature, expect_json)


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
