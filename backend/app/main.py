from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

from .routers import course_router
from .config.db import Database

app = FastAPI(title="AiCourseBuilder Backend")

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(course_router.router)

@app.on_event("startup")
async def startup():
    await Database.get_pool()

@app.on_event("shutdown")
async def shutdown():
    await Database.close()

@app.get("/")
async def read_root():
    return {"message": "AiCourseBuilder Python Backend is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
