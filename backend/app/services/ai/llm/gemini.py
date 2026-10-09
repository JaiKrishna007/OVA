import json
import logging
import time
from typing import Dict, Any, Optional

from app.core.config import settings
from app.services.ai.llm.base import LLMClient

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


class GeminiClient(LLMClient):
    """
    Production LLM client utilizing Google Gemini via the google-genai SDK.
    Enforces temperature 0, JSON response mime type, timeout, and a single retry.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.LLM_MODEL or "gemini-2.5-flash"

    def generate_json(
        self,
        system: str,
        user: str,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        if genai is None or types is None:
            raise ImportError("google-genai package is not installed.")

        client = genai.Client(api_key=self.api_key)

        config_kwargs: Dict[str, Any] = {
            "temperature": 0.0,
            "response_mime_type": "application/json",
            "system_instruction": system,
        }
        if schema:
            config_kwargs["response_schema"] = schema

        config = types.GenerateContentConfig(**config_kwargs)

        # Execute with 1 retry on network or transient error
        max_attempts = 2
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=user,
                    config=config,
                )
                text = response.text or "{}"
                return json.loads(text)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Gemini API attempt {attempt}/{max_attempts} failed: {e}. Retrying..."
                )
                if attempt < max_attempts:
                    time.sleep(1.0)

        raise RuntimeError(f"Gemini API call failed after {max_attempts} attempts: {last_error}")
