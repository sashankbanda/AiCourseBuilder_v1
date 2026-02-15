# AI Course Builder

AI-powered application that generates personalized learning courses from YouTube content, with auto-transcription and smart summarization.

## Prerequisites

- **Python 3.10+** — [python.org](https://www.python.org/downloads/)
- **Node.js 16+** — [nodejs.org](https://nodejs.org/)
- **FFmpeg** — [ffmpeg.org](https://ffmpeg.org/download.html) (must be in PATH)
- **PostgreSQL** — local or cloud ([Neon](https://neon.tech))

## Setup

### 1. Clone & install frontend

```bash
npm install
```

### 2. Install backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
cd ..
```

### 3. Configure environment

Copy `.env.example` to `.env` and fill in:

```
DATABASE_URL=postgresql://user:password@host:port/database?sslmode=require
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
JWT_SECRET=any_random_string
```

Get API keys:
- **Gemini**: [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
- **Groq**: [console.groq.com/keys](https://console.groq.com/keys)

### 4. Initialize database

Run `schema.sql` against your PostgreSQL database:

```bash
psql "YOUR_DATABASE_URL" -f backend/schema.sql
```

Or paste the contents of `backend/schema.sql` into your database client (pgAdmin, Neon console, etc.).

## Run

**Terminal 1 — Backend:**
```bash
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 5000
```

**Terminal 2 — Frontend:**
```bash
npm run dev
```

Open **http://localhost:8080** in your browser.

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Backend | Python, FastAPI, PostgreSQL |
| AI | Google Gemini (content), Groq LLM (summarization) |
| Transcription | YouTube captions → Whisper fallback |
