import json
from ..config.defaults import COURSE_DEFAULTS
from ..lib.llm.llm_factory import LLMFactory


class ContentAgent:
    async def extract_salient_phrases(self, transcripts: list[str]):
        combined_text = "\n".join(transcripts)[:30000]
        prompt = """
        Analyze the following transcripts. Extract a list of **Salient Topic Phrases**.
        These are the core technical terms, concepts, and definitions that MUST be covered.
        
        Output JSON: { "phrases": ["term1", "term2"] }
        """
        
        llm = LLMFactory.get_provider()
        text = await llm.generate(combined_text + "\n\n" + prompt, options={"json": True})
        return self._parse_json(text)

    async def generate_lesson_content(self, transcript: str, salient_phrases: list[str], cognitive_level: str, difficulty_mode: str = 'Standard'):
        print(f"[ContentAgent] Generating content for level: {cognitive_level}, Mode: {difficulty_mode}")

        difficulty_instruction = ""
        if difficulty_mode == 'Remedial':
            difficulty_instruction = "**ADAPTATION: REMEDIAL MODE**. Simplify all technical jargon. Use concrete analogies for every abstract concept. Focus on foundations."
        elif difficulty_mode == 'Advanced':
            difficulty_instruction = "**ADAPTATION: ADVANCED MODE**. Skip basic definitions. Focus on synthesis, critique, and real-world application. Assume prior knowledge."

        prompt = f"""
        You are an Expert Educator. 
        Target Cognitive Level: **{cognitive_level.upper()}** (Bloom's Taxonomy).
        {difficulty_instruction}
        
        **Source Material:**
        "{transcript[:20000]}..."
        
        **Mandatory Salient Phrases to Include:**
        {json.dumps(salient_phrases)}

        Tasks:
        1. **Summary**: Write a detailed summary maximizing coverage of the salient phrases. Avoid redundancy.
        2. **Notes**: Structured markdown notes.
        3. **Quiz**: Create {COURSE_DEFAULTS.QUIZ_QUESTION_COUNT} questions.
           - **Experts-Informed Distractors**: Use "Opposite Facts" and "Incorrect Combinations".
        4. **Deep Thinking Challenge**: Create ONE open-ended question that requires synthesis or application of concepts. It must NOT be a simple fact recall.
        
        Output JSON:
        {{
            "content": "Detailed summary...",
            "notes": "Markdown notes...",
            "quiz_data": {{ 
                "questions": [ {{ "question": "...", "options": ["A","B","C","D"], "correctAnswer": 0 }} ] 
            }},
            "challenge_question": {{
                "question": "...",
                "key_concept": "The core concept the user should mention in their answer."
            }}
        }}
        """

        try:
            llm = LLMFactory.get_provider()
            text = await llm.generate(prompt, options={"json": True})
            return self._parse_json(text)
        except Exception as e:
            print(f"Content Generation Error: {e}")
            raise e

    def _parse_json(self, text: str):
        # Clean up potential markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        if text.startswith("```"):
            text = text[3:]
        return json.loads(text)

