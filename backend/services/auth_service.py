from datetime import datetime
from datetime import timedelta
from datetime import timezone
import bcrypt
import jwt
from fastapi import Depends
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from config import settings
from database.connection import get_db
from database.models import User

ALGORITHM = "HS256"
TOKEN_MINUTES = 480

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password):
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password, password_hash):
    """Check a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def make_token(user_id):
    """Create a JWT token for a user."""
    expires = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)
    payload = {
        "sub": user_id,
        "exp": expires,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def user_to_dict(user):
    """Convert a user to a dictionary."""
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
    }


def token_response(user):
    """Build the login response for a user."""
    return {
        "access_token": make_token(user.id),
        "token_type": "bearer",
        "user": user_to_dict(user),
    }


def find_user_by_email(db, email):
    """Return the user with this email, or None."""
    clean_email = email.strip().lower()
    return db.query(User).filter(User.email == clean_email).first()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Return the logged-in user from the bearer token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not logged in.")

    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return user


def require_customer(user: User = Depends(get_current_user)):
    """Allow only customers."""
    if user.role != "customer":
        raise HTTPException(status_code=403, detail="Customers only.")
    return user


def require_staff(user: User = Depends(get_current_user)):
    """Allow only staff."""
    if user.role == "customer":
        raise HTTPException(status_code=403, detail="Staff only.")
    return user


def register_customer(db, body):
    """Create a customer account and return a login response."""
    clean_email = body.email.strip().lower()
    existing = find_user_by_email(db, clean_email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered.")

    user = User(
        email=clean_email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role="customer",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return token_response(user)


def login_customer(db, body):
    """Check customer credentials and return a login response."""
    user = find_user_by_email(db, body.email)
    if not user or not check_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is wrong.")
    if user.role != "customer":
        raise HTTPException(status_code=403, detail="Staff accounts sign in on the staff page.")
    return token_response(user)


def login_staff(db, body):
    """Check staff credentials and return a login response."""
    user = find_user_by_email(db, body.email)
    if not user or not check_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is wrong.")
    if user.role == "customer":
        raise HTTPException(status_code=403, detail="This account is not a staff account.")
    return token_response(user)