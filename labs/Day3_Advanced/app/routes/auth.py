from fastapi import APIRouter, HTTPException, status
from fastapi.security import HTTPBearer
from app.config import settings
from app.constants import DEMO_USERS
from jose import jwt
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext

router = APIRouter()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

USERS_DB = {
    username: {
        "username": username,
        "hashed_password": pwd_context.hash(credentials["password"]),
        "role": credentials["role"],
    }
    for username, credentials in DEMO_USERS.items()
}


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@router.post("/login")
async def login(username: str, password: str):
    """Login endpoint."""
    user = USERS_DB.get(username)
    if not user or not pwd_context.verify(password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token = create_access_token(data={"sub": username})
    return {"access_token": access_token, "token_type": "bearer"}
