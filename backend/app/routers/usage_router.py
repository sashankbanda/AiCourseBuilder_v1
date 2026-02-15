from fastapi import APIRouter, Depends
from ..dependencies import get_current_user
from ..config.db import Database

router = APIRouter(
    prefix="/api/usage",
    tags=["usage"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/")
async def get_usage(user: dict = Depends(get_current_user)):
    user_id = user["id"]

    # Total tokens
    total_rows = await Database.fetch(
        "SELECT COALESCE(SUM(tokens), 0) as total FROM usage_logs WHERE user_id = $1",
        user_id,
    )
    total_tokens = total_rows[0]["total"] if total_rows else 0

    # Recent history
    history_rows = await Database.fetch(
        """
        SELECT ul.tokens, ul.model, ul.created_at, c.title as course_title
        FROM usage_logs ul
        LEFT JOIN courses c ON c.id = ul.course_id
        WHERE ul.user_id = $1
        ORDER BY ul.created_at DESC
        LIMIT 20
        """,
        user_id,
    )

    history = [
        {
            "tokens": row["tokens"],
            "model": row["model"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "course_title": row["course_title"] or "Unknown Course",
        }
        for row in history_rows
    ]

    return {"totalTokens": total_tokens, "history": history}
