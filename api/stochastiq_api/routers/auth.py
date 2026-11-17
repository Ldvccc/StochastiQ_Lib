from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import LoginIn, RegisterIn, TokenOut, UserOut
from ..security import create_token, hash_password, verify_password

router = APIRouter(tags=["comptes"])


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: Session = Depends(get_db)) -> User:
    """Crée un compte (e-mail unique, mot de passe d'au moins 10 caractères)."""
    if db.scalar(select(User).where(User.email == data.email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Un compte existe déjà avec cet e-mail.")
    user = User(email=data.email, name=data.name, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    return user


@router.post("/auth/login", response_model=TokenOut)
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    """Retourne un JWT valable ``JWT_EXPIRE_HOURS`` heures (12 par défaut)."""
    user = db.scalar(select(User).where(User.email == data.email))
    if user is None or not verify_password(user.password_hash, data.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou mot de passe incorrect.")
    settings = request.app.state.settings
    token = create_token(user.id, settings.secret_key, settings.jwt_expire_hours)
    return TokenOut(access_token=token, expires_in=settings.jwt_expire_hours * 3600)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
