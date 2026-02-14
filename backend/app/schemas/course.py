from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class CreateCourseRequest(BaseModel):
    title: str
    description: Optional[str] = None
    topic: Optional[str] = None

class PlanCourseRequest(BaseModel):
    topic: str
    courseId: str
    difficulty: Optional[str] = "Standard"

class ExecuteCourseRequest(BaseModel):
    courseId: str
    plan: Dict[str, Any]
    topic: str
