import getpass
from database.connection import SessionLocal
from database.models import User
from services.auth_service import find_user_by_email
from services.auth_service import hash_password


def main():
    """Create a Claims Officer account from the terminal."""
    full_name = input("Full name: ").strip()
    email = input("Email: ").strip().lower()
    password = getpass.getpass("Password (8 to 72 characters): ")
    confirm = getpass.getpass("Confirm password: ")

    if not full_name or not email:
        print("Name and email are required.")
        return

    if len(password) < 8 or len(password) > 72:
        print("Password must be 8 to 72 characters.")
        return

    if password != confirm:
        print("Passwords do not match.")
        return

    db = SessionLocal()
    try:
        existing = find_user_by_email(db, email)
        if existing:
            print("That email is already registered.")
            return

        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role="claims_officer",
        )
        db.add(user)
        db.commit()
        print(f"Claims Officer created: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()