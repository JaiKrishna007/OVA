from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class LLMClient(ABC):
    """Abstract interface for LLM JSON generation."""

    @abstractmethod
    def generate_json(
        self,
        system: str,
        user: str,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a constrained completion returning parsed JSON dictionary.
        Must enforce temperature=0, JSON output schema, and no tool use.
        """
        pass
