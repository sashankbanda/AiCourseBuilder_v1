from abc import ABC, abstractmethod
from typing import Optional

class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, options: Optional[dict] = None) -> str:
        pass
