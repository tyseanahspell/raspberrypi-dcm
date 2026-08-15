import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import LoginRequest, PasswordChange, TokenResponse, UserOut
from app.security import create_access_token, verify_password
from app.services import change_password

router = APIRouter(prefix="/auth", tags=["auth"])
_login_attempts: dict[str, list[float]] = defaultdict(list)


def _enforce_login_budget(request: Request) -> None:
    host = request.client.host if request.client else "unknown"
    now = time.time()
    recent = [stamp for stamp in _login_attempts[host] if now - stamp < 300]
    if len(recent) >= 12:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")
    recent.append(now)
    _login_attempts[host] = recent


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    _enforce_login_budget(request)
    user = db.query(User).filter(User.username == body.username).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(user.username), username=user.username)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(username=user.username)


@router.post("/password", response_model=UserOut)
def update_password(
    body: PasswordChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    try:
        change_password(db, user, body.current_password, body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UserOut(username=user.username)
