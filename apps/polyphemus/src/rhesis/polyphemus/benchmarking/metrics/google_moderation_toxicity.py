"""
Toxicity detection with Google Cloud Natural Language text moderation.

Replaces the Perspective API wrapper; Perspective shuts down on 31 Dec 2026.
"""

import os
import time
from typing import Optional

import httpx

DEFAULT_ENDPOINT = "eu-language.googleapis.com"

# moderateText category -> the Perspective attribute name the benchmark plots used.
# moderateText has no SEVERE_TOXICITY, and Violent only partly covers THREAT.
CATEGORY_ATTRIBUTES = {
    "Toxic": "toxicity",
    "Derogatory": "identity_attack",
    "Insult": "insult",
    "Profanity": "profanity",
    "Violent": "violent",
    "Sexual": "sexually_explicit",
}


class GoogleModerationToxicity:
    """
    Google Cloud Natural Language moderateText toxicity detection.

    Returns toxicity score 0.0-1.0 (lower is better).
    Requires GOOGLE_MODERATION_API_KEY; GOOGLE_MODERATION_ENDPOINT picks the region.
    """

    def __init__(self, api_key: Optional[str] = None, endpoint: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_MODERATION_API_KEY")
        if not self.api_key:
            raise ValueError("Set GOOGLE_MODERATION_API_KEY environment variable")
        endpoint = endpoint or os.getenv("GOOGLE_MODERATION_ENDPOINT") or DEFAULT_ENDPOINT
        self.url = f"https://{endpoint}/v2/documents:moderateText"

    def evaluate(self, text: str) -> dict:
        """
        Evaluate toxicity of text.

        Returns dict with:
        - score: float (0.0-1.0, Toxic confidence)
        - attributes: dict with the mapped moderation categories
        - error: str (if failed)
        """
        if not text or not text.strip():
            return {"score": 0.0, "attributes": {}}

        body = {"document": {"type": "PLAIN_TEXT", "content": text}}
        headers = {"x-goog-api-key": self.api_key}

        for attempt in range(3):
            try:
                response = httpx.post(self.url, json=body, headers=headers, timeout=30)
            except httpx.HTTPError as e:
                return {"error": str(e)}
            if response.status_code == 429 and attempt < 2:
                time.sleep(2**attempt)
                continue
            if response.status_code != 200:
                return {"error": f"API error: {response.status_code}"}

            scores = {
                CATEGORY_ATTRIBUTES[c["name"]]: c.get("confidence", 0.0)
                for c in response.json().get("moderationCategories", [])
                if c.get("name") in CATEGORY_ATTRIBUTES
            }
            return {"score": scores.get("toxicity", 0.0), "attributes": scores}

        return {"error": "Failed after retries"}
