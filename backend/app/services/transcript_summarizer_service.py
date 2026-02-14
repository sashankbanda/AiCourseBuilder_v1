"""
Transcript Summarizer Service for AiCourseBuilder.

Ported from: https://github.com/sashankbanda/transcript_summarizer

Hybrid pipeline:
  1. Local extractive summarization (TF-IDF) reduces transcript to ~25%
  2. Optional Groq LLM polishes into structured markdown notes + quiz

Usage (within the app):
    result = await summarize_transcript(transcript_text)
    # result = {"notes": "...", "extracted_sentences": [...], "quiz_md": "..."}
"""

import asyncio
import logging
import math
import os
import re
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_RATIO = 0.25
MIN_SENTENCE_WORDS = 6

# fmt: off
STOPWORDS: set[str] = {
    "a","about","above","after","again","against","all","am","an","and","any",
    "are","aren't","as","at","be","because","been","before","being","below",
    "between","both","but","by","can","can't","cannot","could","couldn't","did",
    "didn't","do","does","doesn't","doing","don't","down","during","each","few",
    "for","from","further","get","got","had","hadn't","has","hasn't","have",
    "haven't","having","he","he'd","he'll","he's","her","here","here's","hers",
    "herself","him","himself","his","how","how's","i","i'd","i'll","i'm","i've",
    "if","in","into","is","isn't","it","it's","its","itself","just","know",
    "let","let's","like","make","me","might","more","most","my","myself","no",
    "nor","not","now","of","off","oh","ok","on","once","only","or","other",
    "ought","our","ours","ourselves","out","over","own","really","right","said",
    "same","say","she","she'd","she'll","she's","should","shouldn't","so",
    "some","such","take","than","that","that's","the","their","theirs","them",
    "themselves","then","there","there's","these","they","they'd","they'll",
    "they're","they've","thing","think","this","those","through","to","too",
    "under","until","up","us","very","want","was","wasn't","we","we'd","we'll",
    "we're","we've","well","were","weren't","what","what's","when","when's",
    "where","where's","which","while","who","who's","whom","why","why's","will",
    "with","won't","would","wouldn't","yeah","yes","yet","you","you'd","you'll",
    "you're","you've","your","yours","yourself","yourselves","going","gonna",
    "gotta","actually","basically","literally","stuff","things","kind","kinda",
}

ABBREVIATIONS: set[str] = {
    "dr","mr","mrs","ms","prof","sr","jr","st","ave","blvd",
    "gen","gov","sgt","cpl","pvt","capt","lt","col","maj",
    "etc","vs","fig","vol","dept","univ","inc","corp","ltd",
    "jan","feb","mar","apr","jun","jul","aug","sep","oct",
    "nov","dec","mon","tue","wed","thu","fri","sat","sun",
    "u.s","u.k","e.g","i.e","a.m","p.m",
}
# fmt: on

# ---------------------------------------------------------------------------
# Groq LLM prompts
# ---------------------------------------------------------------------------
NOTES_SYSTEM_PROMPT = """You are a study notes generator. You receive key sentences extracted from a lecture/video transcript.

Your job:
1. Organize them into clean, structured markdown notes
2. Add section headings based on topic shifts
3. Use bullet points for key facts
4. Keep the language concise and direct — no fluff
5. Do NOT add information that isn't in the extracted sentences
6. Use markdown formatting (##, -, **bold** for key terms)

Output ONLY the notes in markdown, nothing else."""

QUIZ_SYSTEM_PROMPT = """You are a quiz generator. You receive key sentences extracted from a lecture/video transcript.

Your job:
1. Generate multiple choice questions (MCQs) and short answer questions
2. Base questions ONLY on the content provided
3. For MCQs: provide 4 options (A-D) with one correct answer
4. For short answers: keep expected answers to 1-2 sentences
5. Output in this exact markdown format:

## Quiz

### Multiple Choice

**Q1. [question]**
- A) [option]
- B) [option]
- C) [option]
- D) [option]

**Answer:** [letter]

### Short Answer

**Q1. [question]**

**Answer:** [answer]

Output ONLY the quiz in markdown, nothing else."""


# ---------------------------------------------------------------------------
# Text processing
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """Normalize whitespace, remove timestamps and bracketed annotations."""
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"\d{1,2}:\d{2}(:\d{2})?", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    """Split text into sentences with abbreviation awareness."""
    tokens = text.split()
    breaks: list[int] = []

    for i, token in enumerate(tokens):
        if token.endswith((".", "!", "?")):
            word = token.rstrip(".!?").lower()
            if word not in ABBREVIATIONS and len(word) > 1:
                breaks.append(i)

    if not breaks:
        return [text] if len(tokens) >= MIN_SENTENCE_WORDS else []

    sentences: list[str] = []
    start = 0
    for brk in breaks:
        chunk = " ".join(tokens[start: brk + 1]).strip()
        if len(chunk.split()) >= MIN_SENTENCE_WORDS:
            sentences.append(chunk)
        start = brk + 1

    if start < len(tokens):
        chunk = " ".join(tokens[start:]).strip()
        if len(chunk.split()) >= MIN_SENTENCE_WORDS:
            sentences.append(chunk)

    return sentences


# ---------------------------------------------------------------------------
# TF-IDF scoring
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"\w+", text.lower()) if w not in STOPWORDS]


def compute_tfidf(sentences: list[str]) -> dict[str, float]:
    if not sentences:
        return {}

    n_docs = len(sentences)
    corpus_words = _tokenize(" ".join(sentences))
    total_words = len(corpus_words) or 1

    tf: dict[str, float] = {}
    for word, count in Counter(corpus_words).items():
        tf[word] = count / total_words

    df: dict[str, int] = {}
    for sentence in sentences:
        for word in set(_tokenize(sentence)):
            df[word] = df.get(word, 0) + 1

    tfidf: dict[str, float] = {}
    for word in tf:
        idf = math.log((n_docs + 1) / (df.get(word, 0) + 1)) + 1
        tfidf[word] = tf[word] * idf

    return tfidf


def score_sentences(sentences: list[str], tfidf: dict[str, float]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for sentence in sentences:
        words = _tokenize(sentence)
        if not words:
            scores[sentence] = 0.0
            continue
        scores[sentence] = sum(tfidf.get(w, 0) for w in words) / len(words)
    return scores


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def remove_duplicates(sentences: list[str], threshold: float = 0.75) -> list[str]:
    unique: list[str] = []
    for sentence in sentences:
        words_a = set(sentence.lower().split())
        is_dup = False
        for existing in unique:
            words_b = set(existing.lower().split())
            intersection = len(words_a & words_b)
            union = len(words_a | words_b)
            if union > 0 and (intersection / union) > threshold:
                is_dup = True
                break
        if not is_dup:
            unique.append(sentence)
    return unique


# ---------------------------------------------------------------------------
# Extractive summarization
# ---------------------------------------------------------------------------

def extract_key_sentences(text: str, ratio: float = DEFAULT_RATIO) -> list[str]:
    """
    Full extractive pipeline: clean → split → deduplicate → score → select top.
    Returns key sentences in original order.
    """
    text = clean_text(text)
    sentences = split_sentences(text)

    if not sentences:
        logger.warning("No usable sentences found in transcript")
        return []

    sentences = remove_duplicates(sentences)
    logger.info("After dedup: %d sentences", len(sentences))

    tfidf = compute_tfidf(sentences)
    scores = score_sentences(sentences, tfidf)

    select_count = max(3, int(len(sentences) * ratio))
    ranked = sorted(scores, key=scores.get, reverse=True)
    top = set(ranked[:select_count])

    # Preserve original order
    extracted = [s for s in sentences if s in top]
    logger.info("Extracted %d key sentences (%.0f%% of %d)",
                len(extracted), (len(extracted) / len(sentences)) * 100, len(sentences))
    return extracted


# ---------------------------------------------------------------------------
# Groq LLM integration
# ---------------------------------------------------------------------------

def _get_groq_client():
    """Initialize Groq client. Returns None if unavailable."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY not set — skipping LLM processing")
        return None

    try:
        from groq import Groq
        return Groq(api_key=api_key)
    except ImportError:
        logger.warning("groq package not installed — skipping LLM processing")
        return None
    except Exception as e:
        logger.error("Failed to initialize Groq client: %s", e)
        return None


def _call_groq(client, system_prompt: str, user_content: str) -> Optional[str]:
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            max_tokens=2048,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error("Groq API call failed: %s", e)
        return None


def _polish_notes(extracted_sentences: list[str]) -> Optional[str]:
    client = _get_groq_client()
    if not client:
        return None

    user_content = "Here are the key sentences extracted from a transcript:\n\n"
    user_content += "\n".join(f"- {s}" for s in extracted_sentences)

    logger.info("Sending %d sentences to Groq for note polishing", len(extracted_sentences))
    result = _call_groq(client, NOTES_SYSTEM_PROMPT, user_content)
    if result:
        logger.info("LLM notes generated successfully")
    return result


def _generate_quiz_md(extracted_sentences: list[str], num_questions: int = 5) -> Optional[str]:
    client = _get_groq_client()
    if not client:
        return None

    user_content = (
        f"Generate {num_questions} questions from these key transcript sentences:\n\n"
    )
    user_content += "\n".join(f"- {s}" for s in extracted_sentences)

    logger.info("Sending %d sentences to Groq for quiz generation", len(extracted_sentences))
    result = _call_groq(client, QUIZ_SYSTEM_PROMPT, user_content)
    if result:
        logger.info("Quiz generated successfully")
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def summarize_transcript(
    transcript_text: str,
    use_llm: bool = True,
    generate_quiz: bool = True,
) -> dict:
    """
    Summarize a transcript using TF-IDF extraction + optional Groq LLM polishing.

    Args:
        transcript_text: Raw transcript text.
        use_llm: If True, polish notes with Groq (falls back to extractive if unavailable).
        generate_quiz: If True, also generate quiz via Groq.

    Returns:
        {
            "notes": str,               # Structured markdown notes
            "extracted_sentences": list, # Raw key sentences from TF-IDF
            "quiz_md": str | None,       # Quiz in markdown (if requested)
        }
    """
    loop = asyncio.get_event_loop()

    # Step 1: Extractive summarization (CPU-bound, run in executor)
    extracted = await loop.run_in_executor(None, extract_key_sentences, transcript_text)

    if not extracted:
        return {
            "notes": "No usable content could be extracted from the transcript.",
            "extracted_sentences": [],
            "quiz_md": None,
        }

    # Step 2: LLM polishing (I/O-bound Groq API call, run in executor)
    notes = None
    quiz_md = None

    if use_llm:
        notes = await loop.run_in_executor(None, _polish_notes, extracted)
        if generate_quiz:
            quiz_md = await loop.run_in_executor(None, _generate_quiz_md, extracted)

    # Fallback to bullet-point formatting if LLM unavailable
    if not notes:
        notes = "\n".join(f"- {s}" for s in extracted)

    return {
        "notes": notes,
        "extracted_sentences": extracted,
        "quiz_md": quiz_md,
    }
