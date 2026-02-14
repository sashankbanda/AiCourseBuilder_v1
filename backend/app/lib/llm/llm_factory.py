import os
from .llm_provider import LLMProvider
from .gemini_provider import GeminiProvider
from .groq_provider import GroqProvider

class LLMFactory:
    _instance: LLMProvider = None

    @classmethod
    def get_provider(cls) -> LLMProvider:
        if cls._instance:
            return cls._instance

        provider_type = os.environ.get('LLM_PROVIDER', 'gemini')

        if provider_type == 'groq':
            api_key = os.environ.get('GROQ_API_KEY')
            if not api_key:
                raise ValueError("GROQ_API_KEY is not set")
            cls._instance = GroqProvider(api_key)
            print("[LLMFactory] Using Groq Provider")
        else:
            api_key = os.environ.get('GEMINI_API_KEY')
            if not api_key:
                raise ValueError("GEMINI_API_KEY is not set")
            cls._instance = GeminiProvider(api_key)
            print("[LLMFactory] Using Gemini Provider")

        return cls._instance
