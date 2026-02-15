from groq import Groq
from .llm_provider import LLMProvider
from typing import Optional
import os
import asyncio

class GroqProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"

    async def generate(self, prompt: str, options: Optional[dict] = None) -> str:
        try:
            kwargs = {
                "messages": [{"role": "user", "content": prompt}],
                "model": self.model,
            }
            if options and options.get('json'):
                kwargs['response_format'] = {"type": "json_object"}

            chat_completion = await asyncio.to_thread(
                self.client.chat.completions.create, **kwargs
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Groq Error: {e}")
            raise e

