from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import User
from database.schemas import LoginRequest
from database.schemas import RegisterRequest
from services.auth_service import get_current_user
from services.auth_service import login_customer
from services.auth_service import login_staff
from services.auth_service import register_customer
from services.auth_service import user_to_dict

router = APIRouter(prefix="/auth")


@router.post("/register")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new customer account."""
    return register_customer(db, body)


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Log in a customer."""
    return login_customer(db, body)


@router.post("/staff/login")
def staff_login(body: LoginRequest, db: Session = Depends(get_db)):
    """Log in a staff member."""
    return login_staff(db, body)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    """Return the current user."""
    return user_to_dict(user)