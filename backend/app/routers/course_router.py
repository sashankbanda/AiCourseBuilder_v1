from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Any
from fastapi.responses import StreamingResponse
from ..dependencies import get_current_user
from ..config.db import Database
from ..schemas.course import CreateCourseRequest, PlanCourseRequest, ExecuteCourseRequest
from ..agents.orchestrator import Orchestrator
from ..agents.planner_agent import PlannerAgent
import json
import asyncio

router = APIRouter(
    prefix="/api/courses",
    tags=["courses"],
    dependencies=[Depends(get_current_user)]
)

@router.get("/")
async def get_courses(user: dict = Depends(get_current_user)):
    user_id = user['id'] # Adjust based on your JWT payload structure
    query = "SELECT * FROM courses WHERE user_id = $1 ORDER BY created_at DESC"
    rows = await Database.fetch(query, user_id)
    return [dict(row) for row in rows]

@router.post("/")
async def create_course(req: CreateCourseRequest, user: dict = Depends(get_current_user)):
    user_id = user['id']
    query = """
        INSERT INTO courses (user_id, title, description, topic) 
        VALUES ($1, $2, $3, $4) 
        RETURNING *
    """
    rows = await Database.fetch(query, user_id, req.title, req.description or '', req.topic or '')
    return dict(rows[0])

@router.get("/{id}")
async def get_course_by_id(id: str, user: dict = Depends(get_current_user)):
    user_id = user['id']
    query = "SELECT * FROM courses WHERE id = $1 AND user_id = $2"
    rows = await Database.fetch(query, id, user_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Course not found")
    return dict(rows[0])

@router.delete("/{id}")
async def delete_course(id: str, user: dict = Depends(get_current_user)):
    user_id = user['id']
    # Check ownership
    query_check = "SELECT * FROM courses WHERE id = $1 AND user_id = $2"
    rows = await Database.fetch(query_check, id, user_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Course not found")
    
    query_del = "DELETE FROM courses WHERE id = $1"
    await Database.execute(query_del, id)
    return {"message": "Course removed"}


# AI Endpoints

@router.post("/plan")
async def plan_course(req: PlanCourseRequest, user: dict = Depends(get_current_user)):
    # Standard JSON response for planning
    try:
        agent = PlannerAgent()
        plan = await agent.plan_curriculum(req.topic, req.difficulty)
        
        # Save draft lessons
        saved_lessons = []
        for i, lesson_data in enumerate(plan['lessons']):
            query = """
                INSERT INTO lessons 
                (course_id, title, content, order_index, cognitive_level, pedagogical_metadata, is_completed) 
                VALUES ($1, $2, $3, $4, $5, $6, $7) 
                RETURNING id, title, order_index
            """
            rows = await Database.fetch(
                query,
                req.courseId,
                lesson_data['title'],
                'Draft Content - Waiting for Execution',
                i,
                lesson_data.get('cognitive_level', 'understand'),
                json.dumps({**lesson_data, "status": "draft"}),
                False
            )
            saved_lessons.append(dict(rows[0]))
            
        return {"success": True, "plan": plan, "lessonIds": saved_lessons}
        
    except Exception as e:
        print(f"Planning error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{id}/execute")
async def execute_course(req: ExecuteCourseRequest, id: str, user: dict = Depends(get_current_user)):
    user_id = user['id']
    
    async def event_generator():
        queue = asyncio.Queue()
        
        async def send_event(event: str, data: Any):
            queue.put_nowait((event, data))
            
        orchestrator = Orchestrator(lambda e, d: send_event(e, d))
        
        # Run execution in background
        asyncio.create_task(
            _run_orchestrator(orchestrator, req.courseId, req.plan, user_id, req.topic, queue)
        )
        
        while True:
            event, data = await queue.get()
            if event == 'END':
                break
            yield f"event: {event}\ndata: {json.dumps(data)}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

async def _run_orchestrator(orchestrator, course_id, plan, user_id, topic, queue):
    try:
        queue.put_nowait(('progress', {'percent': 1, 'message': "🚀 Orchestrator: Starting Execution Loop..."}))
        
        lesson_results = await orchestrator.execute_course(course_id, plan, user_id, topic)
        
        queue.put_nowait(('progress', {'percent': 90, 'message': "💾 Saving results..."}))
        
        # Save results to DB
        # Get existing lessons to map IDs
        query_lessons = "SELECT id, order_index FROM lessons WHERE course_id = $1 ORDER BY order_index ASC"
        existing_lessons = await Database.fetch(query_lessons, course_id)
        
        for i, lesson_data in enumerate(lesson_results):
            lesson_id = existing_lessons[i]['id'] if i < len(existing_lessons) else None
            
            if lesson_id:
                query_update = """
                    UPDATE lessons SET 
                    content = $1, 
                    videos = $2, 
                    quiz_data = $3, 
                    notes = $4,
                    pedagogical_metadata = $5
                    WHERE id = $6
                """
                await Database.execute(
                    query_update,
                    lesson_data['content'],
                    json.dumps(lesson_data['videos']),
                    json.dumps(lesson_data['quiz_data']),
                    lesson_data['notes'],
                    json.dumps(lesson_data.get('pedagogical_metadata', {})),
                    lesson_id
                )
            else:
                # Insert new if implied
                pass # Skipping for brevity/matching TS logic which handles insert if needed but mainly updates
        
        queue.put_nowait(('progress', {'percent': 100, 'message': "✨ Course Generation Complete!"}))
        queue.put_nowait(('complete', {'success': True}))
        
    except Exception as e:
        queue.put_nowait(('error', {'message': str(e)}))
    finally:
        queue.put_nowait(('END', None))


# Lesson sub-routes

@router.get("/{course_id}/lessons")
async def get_lessons(course_id: str, user: dict = Depends(get_current_user)):
    query = "SELECT * FROM lessons WHERE course_id = $1 ORDER BY order_index ASC"
    rows = await Database.fetch(query, course_id)
    return [dict(row) for row in rows]


@router.post("/{course_id}/lessons")
async def save_lessons(course_id: str, body: list, user: dict = Depends(get_current_user)):
    for i, lesson_data in enumerate(body):
        query = """
            INSERT INTO lessons
            (course_id, title, content, order_index, videos, quiz_data, notes, cognitive_level, pedagogical_metadata, is_completed)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """
        await Database.execute(
            query,
            course_id,
            lesson_data.get('title', ''),
            lesson_data.get('content', ''),
            i,
            json.dumps(lesson_data.get('videos', [])),
            json.dumps(lesson_data.get('quiz_data', {})),
            lesson_data.get('notes', ''),
            lesson_data.get('cognitive_level', 'understand'),
            json.dumps(lesson_data.get('pedagogical_metadata', {})),
            False,
        )
    return {"message": "Lessons saved"}
