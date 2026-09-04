"""Minimal OpenAI-compatible chat client.

Works with any provider that implements the /chat/completions API
(OpenAI, DeepSeek, OpenRouter, Ollama, ...).
"""

from __future__ import annotations

import json
import re
from typing import Any

import requests


class LLMError(RuntimeError):
    """Raised when the LLM call fails."""


class LLMClient:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = 120

    def chat(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except requests.RequestException as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"Unexpected LLM response: {exc}") from exc

    def chat_json(
        self, system: str, user: str, temperature: float = 0.2, max_tokens: int = 2000
    ) -> dict:
        raw = self.chat(
            system, user, temperature=temperature, max_tokens=max_tokens, json_mode=True
        )
        return parse_json_object(raw)


def parse_json_object(raw: str) -> dict:
    """Parse a JSON object out of a model response, tolerating extra
    markdown fences or prose around it."""
    text = raw.strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except ValueError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            value = json.loads(match.group(0))
            if isinstance(value, dict):
                return value
        except ValueError:
            pass
    raise LLMError(f"Could not parse JSON from model response: {raw[:500]}")
