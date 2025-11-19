"""
Perspective API wrapper for toxicity detection.
Simple wrapper around Google's Perspective API.
"""

import os
import time
from typing import Optional

try:
    from googleapiclient import discovery
    from googleapiclient.errors import HttpError

    PERSPECTIVE_AVAILABLE = True
except ImportError:
    PERSPECTIVE_AVAILABLE = False


class PerspectiveToxicity:
    """
    Google Perspective API toxicity detection.

    Returns toxicity score 0.0-1.0 (lower is better).
    Requires PERSPECTIVE_API_KEY environment variable.
    """

    def __init__(self, api_key: Optional[str] = None):
        if not PERSPECTIVE_AVAILABLE:
            raise ImportError("Install: pip install google-api-python-client")

        self.api_key = api_key or os.getenv("PERSPECTIVE_API_KEY")
        if not self.api_key:
            raise ValueError("Set PERSPECTIVE_API_KEY environment variable")

        self.client = None

    def _get_client(self):
        if self.client is None:
            self.client = discovery.build(
                "commentanalyzer",
                "v1alpha1",
                developerKey=self.api_key,
                discoveryServiceUrl="https://commentanalyzer.googleapis.com/$discovery/rest?version=v1alpha1",
                static_discovery=False,
            )
        return self.client

    def evaluate(self, text: str) -> dict:
        """
        Evaluate toxicity of text.

        Returns dict with:
        - score: float (0.0-1.0, primary TOXICITY score)
        - attributes: dict with all toxicity attributes
        - error: str (if failed)
        """
        if not text or not text.strip():
            return {"score": 0.0, "attributes": {}}

        if len(text) > 20000:
            return {"error": "Text too long (max 20KB)"}

        request = {
            "comment": {"text": text},
            "requestedAttributes": {
                "TOXICITY": {},
                "SEVERE_TOXICITY": {},
                "IDENTITY_ATTACK": {},
                "INSULT": {},
                "PROFANITY": {},
                "THREAT": {},
            },
        }

        for attempt in range(3):
            try:
                client = self._get_client()
                response = client.comments().analyze(body=request).execute()

                scores = {}
                for attr in request["requestedAttributes"].keys():
                    if attr in response.get("attributeScores", {}):
                        scores[attr.lower()] = response["attributeScores"][attr]["summaryScore"][
                            "value"
                        ]

                return {"score": scores.get("toxicity", 0.0), "attributes": scores}

            except HttpError as e:
                if e.resp.status == 429 and attempt < 2:  # Rate limit, retry
                    time.sleep(1 * (2**attempt))
                    continue
                return {"error": f"API error: {e.resp.status}"}
            except Exception as e:
                return {"error": str(e)}

        return {"error": "Failed after retries"}
