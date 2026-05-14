# routes/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src import service
from src.schema import UserCreate, UserLogin, PasswordUpdate
from src.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: Session = Depends(get_db)):
    result = service.create_user(db, data)
    if result is service.CreateUserResult.USER_EXISTS:
        raise HTTPException(409, "帳號已被使用")
    return {"message": "註冊成功"}


@router.post("/login")
def login(data: UserLogin, db: Session = Depends(get_db)):
    result = service.login(db, data)
    if not result.success:
        # 忽略 result.reason，統一回 401，避免 user enumeration
        raise HTTPException(401, "帳號或密碼錯誤")
    return {"access_token": result.token, "token_type": "bearer"}