"""Gemini client (Google AI Studio free tier): text generation with model fallback, embeddings, token accounting."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from hhgoa.tg import env

BASE = "https://generativelanguage.googleapis.com/v1beta/models"
GEN_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3-flash-preview", "gemini-2.5-flash"]
EMBED_MODEL = "gemini-embedding-001"
DIM = 768


class Gemini:
    def __init__(self) -> None:
        self.key = env().get("GEMINI_API_KEY", "")
        self.client = httpx.Client(timeout=120, headers={"x-goog-api-key": self.key})
        self.tokens = 0
        self.last_model = ""

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    def generate_json(self, system: str, prompt: str, temperature: float = 0.2) -> dict[str, Any]:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
        }
        last = ""
        for attempt in range(3):
            for model in GEN_MODELS:
                try:
                    r = self.client.post(f"{BASE}/{model}:generateContent", json=body)
                except httpx.HTTPError as exc:
                    last = f"{model}: {exc}"
                    continue
                if r.status_code != 200:
                    last = f"{model}: {r.status_code} {r.text[:120]}"
                    continue
                j = r.json()
                self.tokens += int(j.get("usageMetadata", {}).get("totalTokenCount", 0))
                parts = j.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                try:
                    self.last_model = model
                    return json.loads(text)
                except json.JSONDecodeError:
                    last = f"{model}: bad JSON"
            time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"Gemini unavailable: {last}")

    def embed(self, texts: list[str], task: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 100):
            reqs = [{"model": f"models/{EMBED_MODEL}", "content": {"parts": [{"text": t[:6000]}]},
                     "taskType": task, "outputDimensionality": DIM} for t in texts[i:i + 100]]
            for attempt in range(5):
                r = self.client.post(f"{BASE}/{EMBED_MODEL}:batchEmbedContents", json={"requests": reqs})
                if r.status_code == 200:
                    out += [e["values"] for e in r.json()["embeddings"]]
                    break
                time.sleep(10 * (attempt + 1))
            else:
                raise RuntimeError(f"embedding failed: {r.status_code} {r.text[:200]}")
        return out
