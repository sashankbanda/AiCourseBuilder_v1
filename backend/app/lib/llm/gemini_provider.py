import google.generativeai as genai
from .llm_provider import LLMProvider
from typing import Optional
import os

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    async def generate(self, prompt: str, options: Optional[dict] = None) -> str:
        try:
            generation_config = {}
            if options and options.get('json'):
                generation_config['response_mime_type'] = 'application/json'

            response = self.model.generate_content(prompt, generation_config=generation_config)
            return response.text
        except Exception as e:
            print(f"Gemini Error: {e}")
            raise e
