# -*- coding: utf-8 -*-
"""Client gọi LLM theo giao diện OpenAI-compatible (chat/completions).

Cấu hình qua biến môi trường:
  ABAC_LLM_ENDPOINT  vd: https://api.openai.com/v1  hoặc http://localhost:11434/v1
  ABAC_LLM_MODEL     vd: gpt-4o-mini, llama3.1, qwen2.5:7b
  ABAC_LLM_API_KEY   (tùy chọn; model local thường không cần)
  ABAC_LLM_TIMEOUT   giây (mặc định 60)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from . import prompts


class LLMError(RuntimeError):
    pass


def parse_json_object(text: str) -> dict:
    """Bóc đối tượng JSON đầu tiên trong câu trả lời (chấp nhận có markdown fence)."""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise LLMError("không tìm thấy JSON trong câu trả lời")
    raw = text[start:end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(f"JSON không hợp lệ: {exc}") from exc


class LLMClient:
    def __init__(self, endpoint: str, model: str = "", api_key: str = "", timeout: int = 60):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "LLMClient | None":
        endpoint = os.environ.get("ABAC_LLM_ENDPOINT", "").strip()
        if not endpoint:
            return None
        return cls(
            endpoint=endpoint,
            model=os.environ.get("ABAC_LLM_MODEL", "").strip(),
            api_key=os.environ.get("ABAC_LLM_API_KEY", "").strip(),
            timeout=int(os.environ.get("ABAC_LLM_TIMEOUT", "60")),
        )

    def chat(self, messages: list[dict]) -> str:
        url = self.endpoint
        if not url.endswith("/chat/completions"):
            url = url + "/chat/completions"
        body = {
            "model": self.model or "default",
            "messages": messages,
            "temperature": 0,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                data = json.load(resp)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMError(f"gọi LLM thất bại: {exc}") from exc
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"phản hồi LLM sai định dạng: {exc}") from exc

    def extract(self, sentence: str, language: str = "auto") -> dict:
        return parse_json_object(self.chat(prompts.build_messages(sentence, language)))
