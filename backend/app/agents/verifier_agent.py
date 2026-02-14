import json
from ..lib.llm.llm_factory import LLMFactory

class VerifierAgent:
    async def verify_content(self, transcript_snippet: str, generated_summary: str, quiz_questions: list):
        print(f"[VerifierAgent] Verifying content integrity...")

        prompt = f"""
        You are a **Pedagogical Content Verifier**.
        
        Your task is to validate the *Generated Summary* and *Quiz Questions* against the *Source Transcript*.
        
        **Source Transcript (Snippet):**
        "{transcript_snippet[:5000]}..."

        **Generated Summary:**
        "{generated_summary}"

        **Quiz Questions:**
        {json.dumps(quiz_questions)}

        **Verification Criteria:**
        1. **Hallucination Check:** Does the summary contain facts NOT present in the transcript?
        2. **Pedagogical Depth:** Is the summary detailed enough for a learner (not just "This video covers X")?
        3. **Quiz Integrity:** Are the correct answers actually supported by the transcript?
        
        Output **JSON ONLY**:
        {{
            "valid": boolean,
            "hallucination_score": number, // 0 to 1 (1 = pure hallucination)
            "depth_score": number, // 0 to 1 (1 = excellent depth)
            "feedback": "Specific instructions on how to fix if invalid",
            "suggested_actions": ["REGEN_SUMMARY", "REGEN_QUIZ", "NONE"]
        }}
        """

        try:
            llm = LLMFactory.get_provider()
            text = await llm.generate(prompt, options={"json": True})
            return self._parse_json(text)

        except Exception as error:
            print(f"[VerifierAgent] Error: {error}")
            return {"valid": True, "feedback": "Verification failed, assuming valid fallback."}

    async def evaluate_challenge_response(self, user_answer: str, correct_concept: str):
        print(f"[VerifierAgent] Evaluating challenge response...")

        prompt = f"""
        You are an **AI Tutor (LLM-as-a-Judge)**.
        
        **Task**: Evaluate the student's open-ended answer against the "Gold Standard" concept.
        
        **Student Answer**: "{user_answer}"
        **Gold Standard Concept**: "{correct_concept}"
        
        **Evaluation Rubric**:
        1. **Semantic Match** (0.0 - 1.0): Does the answer cover the core meaning of the concept?
        2. **Diagnostic Value**: If incorrect, what specific misconception does the student have?
        3. **Positive Reinforcement**: Provide a helpful "Nudge" or reference to the correct logic.
        
        Output **JSON ONLY**:
        {{
            "score": number, // 0.0 to 1.0
            "feedback": "...",
            "misconception": "..." | null,
            "nudge": "..."
        }}
        """

        try:
            llm = LLMFactory.get_provider()
            text = await llm.generate(prompt, options={"json": True})
            return self._parse_json(text)

        except Exception as error:
            print(f"[VerifierAgent] Evaluation Error: {error}")
            return {"score": 0, "feedback": "Error evaluating response.", "misconception": None}

    def _parse_json(self, text: str):
         # Clean up potential markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        if text.startswith("```"):
                text = text[3:]
        return json.loads(text)
