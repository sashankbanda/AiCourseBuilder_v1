from fastapi import APIRouter, HTTPException
from ..config.db import Database
import jwt
import os
import hashlib
import secrets

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
)


def _hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """Hash password with salt using SHA-256."""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}", salt


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash."""
    salt, hash_val = stored_hash.split(":", 1)
    check = hashlib.sha256((salt + password).encode()).hexdigest()
    return check == hash_val


def _create_token(user_id: str, email: str) -> str:
    """Create JWT token."""
    import datetime
    secret = os.environ.get("JWT_SECRET", "development_secret_key_12345")
    payload = {
        "id": str(user_id),
        "email": email,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@router.post("/register")
async def register(body: dict):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    full_name = body.get("full_name", "")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    # Check if user exists
    existing = await Database.fetch("SELECT id FROM users WHERE email = $1", email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Create user
    password_hash, _ = _hash_password(password)
    rows = await Database.fetch(
        "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id, email",
        email, password_hash,
    )
    user = dict(rows[0])

    # Create profile if full_name provided
    if full_name:
        await Database.execute(
            "INSERT INTO profiles (user_id, full_name) VALUES ($1, $2)",
            user["id"], full_name,
        )

    token = _create_token(user["id"], user["email"])
    return {"id": str(user["id"]), "email": user["email"], "token": token}


@router.post("/login")
async def login(body: dict):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    rows = await Database.fetch(
        "SELECT id, email, password_hash FROM users WHERE email = $1", email
    )
    if not rows:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = dict(rows[0])
    if not _verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _create_token(user["id"], user["email"])
    return {"id": str(user["id"]), "email": user["email"], "token": token}
