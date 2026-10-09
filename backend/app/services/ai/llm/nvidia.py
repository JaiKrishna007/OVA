import json
import logging
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

from app.core.config import settings
from app.services.ai.llm.base import LLMClient

logger = logging.getLogger(__name__)


class NvidiaClient(LLMClient):
    """
    Production LLM client utilizing NVIDIA NIM OpenAI-compatible API.
    Selected Model: meta/llama-3.2-11b-vision-instruct (verified active, low latency, robust JSON extraction).
    Enforces temperature 0.0, JSON output schema constraints, and 1 retry.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or settings.NVIDIA_API_KEY
        self.model = model or settings.LLM_MODEL or "meta/llama-3.2-11b-vision-instruct"
        self.base_url = (base_url or settings.NVIDIA_BASE_URL).rstrip("/")

    def generate_json(
        self,
        system: str,
        user: str,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY is not configured.")

        url = f"{self.base_url}/chat/completions"

        # Constrain prompt with system instructions
        sys_prompt = system
        if schema:
            sys_prompt += (
                f"\n\nCRITICAL OUTPUT INSTRUCTION:\n"
                f"You must extract and return the concrete clinical data from the input as a valid JSON document conforming to this structure:\n"
                f"{json.dumps(schema, indent=2)}\n"
                f"Populate the JSON fields with the extracted clinical facts. Do NOT return the schema definition itself. Return ONLY valid JSON with no markdown wrapping or preamble."
            )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user},
            ],
            "temperature": 0.0,
            "max_tokens": 2048,
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        max_attempts = 2
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                req = urllib.request.Request(url, data=data_bytes, headers=headers)
                with urllib.request.urlopen(req, timeout=35) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    choices = resp_data.get("choices", [])
                    if not choices:
                        return {}
                    content = choices[0].get("message", {}).get("content", "").strip()

                    # Strip markdown code blocks if present
                    if "```json" in content:
                        content = content.split("```json", 1)[1].split("```", 1)[0].strip()
                    elif "```" in content:
                        content = content.split("```", 1)[1].split("```", 1)[0].strip()

                    return json.loads(content)
            except urllib.error.HTTPError as he:
                err_body = he.read().decode("utf-8", errors="ignore")
                last_error = Exception(f"NVIDIA API HTTP {he.code}: {err_body}")
                logger.warning(
                    f"NVIDIA API attempt {attempt}/{max_attempts} failed: {last_error}. Retrying..."
                )
                time.sleep(1.0)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"NVIDIA API attempt {attempt}/{max_attempts} failed: {e}. Retrying..."
                )
                time.sleep(1.0)

        raise RuntimeError(
            f"Failed to generate JSON via NVIDIA model {self.model} after {max_attempts} attempts: {last_error}"
        )
