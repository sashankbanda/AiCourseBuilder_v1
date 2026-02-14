import os
import asyncio
from typing import Callable, Any
from .planner_agent import PlannerAgent
from .content_agent import ContentAgent
from .verifier_agent import VerifierAgent
from .difficulty_manager import DifficultyManager
from ..services.youtube_service import search_videos
from ..services.transcript_extractor import extract_transcript
from ..services.transcript_summarizer_service import summarize_transcript


class Orchestrator:
    def __init__(self, send_event: Callable[[str, Any], None]):
        self.planner = PlannerAgent()
        self.content_agent = ContentAgent()
        self.verifier = VerifierAgent()
        self.send_event = send_event

    async def plan_course(self, topic: str):
        await self.send_event('progress', {'percent': 10, 'message': "📋 Planner Agent: Analyzing Instructional Design..."})
        plan = await self.planner.plan_curriculum(topic)
        await self.send_event('progress', {'percent': 20, 'message': f"📋 Planner: Designed {plan['type']} course with {len(plan['lessons'])} lessons."})
        return plan

    async def execute_course(self, course_id: str, plan: dict, user_id: str, topic: str):
        difficulty_manager = DifficultyManager()
        results = []
        completed_lessons = 0
        total_lessons = len(plan['lessons'])

        for lesson_plan in plan['lessons']:
            # Adaptive Difficulty Check
            difficulty_mode = await difficulty_manager.determine_difficulty(user_id, course_id)

            percent = 20 + int((completed_lessons / total_lessons) * 70)
            await self.send_event('progress', {
                'percent': percent,
                'message': f"🎥 [{difficulty_mode}] Searching content for: \"{lesson_plan['title']}\"..."
            })

            # A. Search Video
            search_query = lesson_plan.get('search_queries', [lesson_plan['title']])[0]
            videos = await search_videos(search_query)
            
            if not videos:
                print(f"No video found for {lesson_plan['title']}")
                results.append(self._create_empty_lesson(lesson_plan))
                completed_lessons += 1
                continue
                
            video = videos[0]
            video_id = video['id']['videoId']

            if not video_id:
                print(f"No valid video ID found for {lesson_plan['title']}")
                results.append(self._create_empty_lesson(lesson_plan))
                completed_lessons += 1
                continue

            # B. Extract Transcript (official captions → Whisper fallback)
            await self.send_event('progress', {
                'message': f"📝 Extracting transcript for: \"{lesson_plan['title']}\"..."
            })

            try:
                transcript_text = await extract_transcript(video_id)
            except Exception as err:
                print(f"Transcript extraction failed for {lesson_plan['title']}: {err}")
                results.append(self._create_empty_lesson(lesson_plan))
                completed_lessons += 1
                continue

            if not transcript_text:
                print(f"Empty transcript for {lesson_plan['title']}")
                results.append(self._create_empty_lesson(lesson_plan))
                completed_lessons += 1
                continue

            # C. Summarize transcript (TF-IDF + Groq LLM polishing)
            await self.send_event('progress', {
                'message': f"📊 Summarizing transcript for: \"{lesson_plan['title']}\"..."
            })
            summary_data = await summarize_transcript(transcript_text)

            # D. Generate lesson content via LLM (Content Agent)
            await self.send_event('progress', {
                'message': f"🧠 Content Agent ({difficulty_mode}): Generating lesson content..."
            })

            # 1. Extract Salient Phrases
            phrases_data = await self.content_agent.extract_salient_phrases([transcript_text])
            phrases = phrases_data.get('phrases', [])

            # 2. Generate Draft
            generated_content = await self.content_agent.generate_lesson_content(
                transcript_text, phrases, lesson_plan.get('cognitive_level', 'understand'), difficulty_mode
            )

            # Merge summarizer notes into generated content if available
            if summary_data.get('notes'):
                generated_content['notes'] = summary_data['notes']

            # E. Verification Loop
            attempts = 0
            is_valid = False

            while not is_valid and attempts < 2:
                await self.send_event('progress', {
                    'message': f"🛡️ Verifier Agent: Validating attempt {attempts + 1}..."
                })
                
                verification = await self.verifier.verify_content(
                    transcript_text,
                    generated_content.get('content', ''),
                    generated_content.get('quiz_data', {}).get('questions', [])
                )

                if verification.get('valid'):
                    is_valid = True
                    print("✅ Verification Passed")
                else:
                    print(f"❌ Verification Failed: {verification.get('feedback')}")
                    attempts += 1
                    if attempts == 2:
                        print("Max retries reached, using best effort.")
                        is_valid = True

            results.append({
                "title": lesson_plan['title'],
                "content": generated_content.get('content', ''),
                "videos": [{
                    "id": video_id,
                    "title": video['snippet']['title'],
                    "thumbnail": video['snippet']['thumbnails']['high']['url']
                }],
                "notes": generated_content.get('notes', ''),
                "quiz_data": generated_content.get('quiz_data', {}),
                "cognitive_level": lesson_plan.get('cognitive_level'),
                "pedagogical_metadata": {
                    "objectives": lesson_plan.get('objectives'),
                    "difficulty_mode": difficulty_mode,
                    "challenge_question": generated_content.get('challenge_question')
                }
            })

            completed_lessons += 1

        return results

    def _create_empty_lesson(self, plan: dict):
        return {
            "title": plan['title'],
            "content": "Content could not be generated.",
            "videos": [],
            "notes": "N/A",
            "quiz_data": { "questions": [] },
            "cognitive_level": plan.get('cognitive_level', 'understand'),
            "pedagogical_metadata": {}
        }


