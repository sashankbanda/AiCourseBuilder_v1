from fastapi import APIRouter, Depends, HTTPException
from ..dependencies import get_current_user
from ..config.db import Database
import json

router = APIRouter(
    prefix="/api/lessons",
    tags=["lessons"],
    dependencies=[Depends(get_current_user)],
)


@router.put("/{lesson_id}")
async def update_lesson(lesson_id: str, body: dict, user: dict = Depends(get_current_user)):
    # Build dynamic update
    fields = []
    values = []
    idx = 1

    allowed = {
        "content": str, "notes": str, "is_completed": bool, "quiz_score": int,
    }
    json_fields = {"videos", "quiz_data", "pedagogical_metadata"}

    for key in allowed:
        if key in body:
            fields.append(f"{key} = ${idx}")
            values.append(body[key])
            idx += 1

    for key in json_fields:
        if key in body:
            fields.append(f"{key} = ${idx}")
            values.append(json.dumps(body[key]))
            idx += 1

    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.append(lesson_id)
    query = f"UPDATE lessons SET {', '.join(fields)} WHERE id = ${idx} RETURNING *"
    rows = await Database.fetch(query, *values)

    if not rows:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return dict(rows[0])
