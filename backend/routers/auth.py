"""Authentication Endpoints.
=======================

REST API endpoints for authentication and authorization.
Provides login, register, token refresh, and API key management.

Features:
- JWT token generation and validation
- API key authentication
- bcrypt password hashing
- Role-based access control (RBAC)
- Database-backed user storage

ENDPOINTS:
- POST /api/v1/auth/login - Login with username/password
- POST /api/v1/auth/register - Register new user
- POST /api/v1/auth/refresh - Refresh access token
- POST /api/v1/auth/api-key - Create new API key
- GET /api/v1/auth/me - Get current user info
- DELETE /api/v1/auth/api-key/{key_id} - Revoke API key
"""

from __future__ import annotations

import hmac
import logging
import os
import secrets
import sqlite3
import time
from typing import TYPE_CHECKING

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from backend.rbac import Role

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Authentication"])

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# JWT Configuration
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required!")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# ═══════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str = "viewer"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    disabled: bool = False


class APIKeyCreateResponse(BaseModel):
    api_key: str
    key_id: str
    message: str = "Store this key securely. It will not be shown again."


class APIKeyInfo(BaseModel):
    key_id: str
    name: str
    created_at: float
    last_used: float | None = None
    disabled: bool = False


# ═══════════════════════════════════════════════════════════════════════════
# DATABASE LAYER
# ═══════════════════════════════════════════════════════════════════════════


class UserDB:
    """User database with SQLite backend."""

    def __init__(self) -> None:
        self._db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "db", "auth.db"
        )
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL,
                hashed_password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                disabled INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                last_login REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                hashed_key TEXT NOT NULL,
                created_at REAL NOT NULL,
                last_used REAL,
                disabled INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.commit()
        conn.close()
        self._ensure_default_users()

    def _ensure_default_users(self) -> None:
        """Create default users if not exist."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        defaults = [
            ("admin-001", "admin", "admin@fireai.local", "admin123", "admin"),
            ("engineer-001", "engineer", "engineer@fireai.local", "engineer123", "engineer"),
            ("viewer-001", "viewer", "viewer@fireai.local", "viewer123", "viewer"),
        ]

        for user_id, username, email, password, role in defaults:
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if not cursor.fetchone():
                hashed = hash_password(password)
                cursor.execute(
                    "INSERT INTO users (id, username, email, hashed_password, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, username, email, hashed, role, time.time())
                )
                logger.info(f"Created default user: {username}")

        conn.commit()
        conn.close()

    def get_user(self, username: str) -> dict | None:
        """Get user by username."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username = ? AND disabled = 0",
            (username,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> dict | None:
        """Get user by ID."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE id = ? AND disabled = 0",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def create_user(
        self,
        user_id: str,
        username: str,
        email: str,
        hashed_password: str,
        role: str,
    ) -> dict:
        """Create a new user."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (id, username, email, hashed_password, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, email, hashed_password, role, time.time())
        )
        conn.commit()
        conn.close()
        return {"id": user_id, "username": username, "email": email, "role": role}

    def update_last_login(self, user_id: str) -> None:
        """Update last login timestamp."""
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (time.time(), user_id)
        )
        conn.commit()
        conn.close()

    def create_api_key(
        self,
        key_id: str,
        user_id: str,
        name: str,
        hashed_key: str,
    ) -> dict:
        """Create a new API key."""
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "INSERT INTO api_keys (key_id, user_id, name, hashed_key, created_at) VALUES (?, ?, ?, ?, ?)",
            (key_id, user_id, name, hashed_key, time.time())
        )
        conn.commit()
        conn.close()
        return {"key_id": key_id, "user_id": user_id, "name": name}

    def get_api_key(self, key_id: str) -> dict | None:
        """Get API key by key_id."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM api_keys WHERE key_id = ? AND disabled = 0",
            (key_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_all_api_keys(self) -> list[dict]:
        """Get all API keys (for verification)."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM api_keys WHERE disabled = 0")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_user_api_keys(self, user_id: str) -> list[dict]:
        """Get all API keys for a user."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT key_id, name, created_at, last_used, disabled FROM api_keys WHERE user_id = ?",
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        conn = sqlite3.connect(self._db_path)
        conn.execute("UPDATE api_keys SET disabled = 1 WHERE key_id = ?", (key_id,))
        conn.commit()
        affected = conn.total_changes
        conn.close()
        return affected > 0

    def update_api_key_usage(self, key_id: str) -> None:
        """Update API key last used timestamp."""
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "UPDATE api_keys SET last_used = ? WHERE key_id = ?",
            (time.time(), key_id)
        )
        conn.commit()
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# SECURITY UTILITIES
# ═══════════════════════════════════════════════════════════════════════════


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


# Global database instance (after hash_password is defined)
user_db = UserDB()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def hash_api_key(api_key: str) -> str:
    """Hash API key for storage using bcrypt."""
    return bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()


def verify_api_key_hash(plain_key: str, hashed: str) -> bool:
    """Verify API key against stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_key.encode(), hashed.encode())
    except Exception:
        return False


def generate_api_key() -> tuple[str, str]:
    """Generate new API key. Returns (plain_key, key_id)."""
    plain_key = f"sk_{secrets.token_urlsafe(32)}"
    key_id = f"key_{secrets.token_hex(8)}"
    return plain_key, key_id


def create_access_token(data: dict) -> str:
    """Create JWT access token."""
    from datetime import datetime, timedelta, timezone

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({
        "exp": expire.timestamp(),
        "iat": datetime.now(timezone.utc).timestamp()
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token."""
    from datetime import datetime, timedelta, timezone

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({
        "exp": expire.timestamp(),
        "iat": datetime.now(timezone.utc).timestamp()
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict | None:
    """Verify and decode JWT token."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid token")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# USER CLASS
# ═══════════════════════════════════════════════════════════════════════════


class User:
    """User data structure."""

    def __init__(
        self,
        id: str,
        username: str,
        email: str,
        role: Role,
        disabled: bool = False,
    ) -> None:
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        self.disabled = disabled

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value if isinstance(self.role, Role) else self.role,
            "disabled": self.disabled
        }


# ═══════════════════════════════════════════════════════════════════════════
# DEPENDENCIES
# ═══════════════════════════════════════════════════════════════════════════


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Depends(api_key_header),
) -> User:
    """Get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Try API key first
    if api_key:
        user = verify_api_key_auth(api_key)
        if user:
            return user

    # Try bearer token
    if credentials:
        payload = verify_token(credentials.credentials)
        if payload:
            user_data = user_db.get_user_by_id(payload.get("user_id"))
            if user_data:
                return User(
                    id=user_data["id"],
                    username=user_data["username"],
                    email=user_data["email"],
                    role=Role(user_data["role"]),
                    disabled=bool(user_data["disabled"])
                )

    raise credentials_exception


def verify_api_key_auth(plain_key: str) -> User | None:
    """Verify API key and return user."""
    # Get all active API keys and check
    all_keys = user_db.get_all_api_keys()

    for key_data in all_keys:
        if verify_api_key_hash(plain_key, key_data["hashed_key"]):
            # Update last used
            user_db.update_api_key_usage(key_data["key_id"])

            # Get user
            user_data = user_db.get_user_by_id(key_data["user_id"])
            if user_data:
                return User(
                    id=user_data["id"],
                    username=user_data["username"],
                    email=user_data["email"],
                    role=Role(user_data["role"]),
                    disabled=bool(user_data["disabled"])
                )

    return None


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Require admin role."""
    if current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> TokenResponse:
    """Authenticate user and return JWT tokens.

    Demo credentials:
    - admin / admin123
    - engineer / engineer123
    - viewer / viewer123
    """
    user_data = user_db.get_user(request.username)

    if not user_data or not verify_password(request.password, user_data["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    if user_data["disabled"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )

    # Update last login
    user_db.update_last_login(user_data["id"])

    # Create tokens
    token_data = {
        "sub": user_data["username"],
        "role": user_data["role"],
        "user_id": user_data["id"]
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    logger.info(f"User {user_data['username']} logged in successfully")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/register", response_model=UserResponse)
async def register(request: RegisterRequest, _: User = Depends(get_admin_user)) -> UserResponse:
    """Register a new user (admin only)."""
    # Check if username exists
    if user_db.get_user(request.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    # Validate role
    try:
        role = Role(request.role.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {[r.value for r in Role]}"
        )

    # Create user
    user_id = f"user-{secrets.token_hex(4)}"
    hashed_password = hash_password(request.password)

    user_db.create_user(
        user_id=user_id,
        username=request.username,
        email=request.email,
        hashed_password=hashed_password,
        role=role.value
    )

    logger.info(f"New user registered: {request.username} with role {role.value}")

    return UserResponse(
        id=user_id,
        username=request.username,
        email=request.email,
        role=role.value,
        disabled=False
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest) -> TokenResponse:
    """Refresh access token using refresh token."""
    payload = verify_token(request.refresh_token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    user_data = user_db.get_user_by_id(payload.get("user_id"))
    if not user_data or user_data["disabled"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled"
        )

    # Create new tokens
    token_data = {
        "sub": user_data["username"],
        "role": user_data["role"],
        "user_id": user_data["id"]
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/api-key", response_model=APIKeyCreateResponse)
async def create_api_key(current_user: User = Depends(get_current_user)) -> APIKeyCreateResponse:
    """Create a new API key for the current user."""
    plain_key, key_id = generate_api_key()
    hashed_key = hash_api_key(plain_key)

    user_db.create_api_key(
        key_id=key_id,
        user_id=current_user.id,
        name=f"Key for {current_user.username}",
        hashed_key=hashed_key
    )

    logger.info(f"API key created for user {current_user.username}")

    return APIKeyCreateResponse(
        api_key=plain_key,
        key_id=key_id
    )


@router.get("/api-keys", response_model=list[APIKeyInfo])
async def list_api_keys(current_user: User = Depends(get_current_user)) -> list[APIKeyInfo]:
    """List all API keys for the current user."""
    keys = user_db.get_user_api_keys(current_user.id)
    return [
        APIKeyInfo(
            key_id=k["key_id"],
            name=k["name"],
            created_at=k["created_at"],
            last_used=k.get("last_used"),
            disabled=bool(k.get("disabled", 0))
        )
        for k in keys
    ]


@router.delete("/api-key/{key_id}")
async def revoke_api_key(key_id: str, current_user: User = Depends(get_current_user)) -> dict:
    """Revoke an API key."""
    key_data = user_db.get_api_key(key_id)

    if not key_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    if key_data["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot revoke API key belonging to another user"
        )

    user_db.revoke_api_key(key_id)
    logger.info(f"API key {key_id} revoked by {current_user.username}")

    return {"message": "API key revoked successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Get current user information."""
    return UserResponse(**current_user.to_dict())
