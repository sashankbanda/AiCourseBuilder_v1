import json
from ..lib.llm.llm_factory import LLMFactory

class PlannerAgent:
    async def plan_curriculum(self, topic: str, difficulty: str = 'Beginner'):
        print(f"[PlannerAgent] Planning curriculum for: {topic} (Difficulty: {difficulty})")

        prompt = f"""
        You are an Expert Instructional Designer following the **Dick and Carey Systems Approach Model**.
        
        Your task is to design a course curriculum for the topic: "{topic}".
        Target Audience Difficulty Level: **{difficulty}**.
        
        **Instructions based on Difficulty:**
        - **Beginner**: Focus on fundamental concepts, definitions, and basic understanding. Cognitive levels: Remember, Understand.
        - **Intermediate**: Focus on application, analysis, and combining concepts. Cognitive levels: Apply, Analyze.
        - **Advanced**: Focus on complex problem-solving, evaluation, and creation. Cognitive levels: Evaluate, Create.
        
        Step 1: **Instructional Analysis**
        - Identify the "Goal" of this course.
        - Determine the prerequisite skills required.
        - Break the goal into subordinate skills (subtopics).
        
        Step 2: **Performance Objectives**
        - For each subtopic, define what the learner will be able to do.
        - Classify the cognitive level (Bloom's Taxonomy).

        Step 3: **Generate Structure**
        - Based on the analysis, output a JSON structure.
        - Determine if this is a "Small" (1 lesson) or "Big" (3-5 lessons) topic.

        Output **JSON ONLY**:
        {{
            "type": "small" | "big",
            "goal": "...",
            "prerequisites": ["..."],
            "lessons": [
                {{
                    "title": "Lesson Title (Clear & Actionable)",
                    "objectives": "Learner will be able to...",
                    "cognitive_level": "remember" | "understand" | "apply" | "analyze" | "evaluate" | "create",
                    "search_queries": ["YouTube search query 1"]
                }}
            ]
        }}
        """

        try:
            llm = LLMFactory.get_provider()
            text = await llm.generate(prompt, options={"json": True})
            
            # Clean up potential markdown code blocks
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            if text.startswith("```"):
                 text = text[3:]

            plan = json.loads(text)
            return plan

        except Exception as error:
            print(f"[PlannerAgent] Error generating plan: {error}")
            # Fallback
            return {
                "type": "small",
                "goal": f"Learn basics of {topic}",
                "prerequisites": [],
                "lessons": [{
                    "title": f"Introduction to {topic}",
                    "objectives": "Understand basics",
                    "cognitive_level": "understand",
                    "search_queries": [f"{topic} tutorial"]
                }]
            }
