from datetime import datetime
from datetime import timezone

from database.connection import SessionLocal
from database.models import Policy
from database.models import User
from services.auth_service import find_user_by_email
from services.auth_service import hash_password

SEED_PASSWORD = "password123"

# The customers named in the policy schedules
CUSTOMERS = [
    {"email": "vikram.rao@example.com", "full_name": "Vikram Ananth Rao"},
    {"email": "aarav.kapoor@example.com", "full_name": "Aarav Rohan Kapoor"},
    {"email": "sunil.verma@example.com", "full_name": "Sunil Ramesh Verma"},
    {"email": "vikramaditya.malhotra@example.com", "full_name": "Vikramaditya Ananya Malhotra"},
]

# One entry per policy PDF, with values copied from its schedule.
# Add an entry for every other policy PDF. The policy number is on every page footer.
POLICIES = [
    {
        # Family floater. Co-payment depends on the zone, so it is left at 0 here
        "number": "POL-AST-2026-9942105-F02",
        "owner": "vikram.rao@example.com",
        "line": "health",
        "product": "AsterShield FamilyCare Plus",
        "sum_insured": 1000000,
        "deductible": 0,
        "copay": 0,
        "start": (2026, 2, 15),
        "end": (2027, 2, 14),
    },
    {
        # The sum insured is the Insured Declared Value (IDV)
        "number": "POL-AST-2026-5510943-V01",
        "owner": "aarav.kapoor@example.com",
        "line": "private_vehicle",
        "product": "AsterShield Private Car Comprehensive",
        "sum_insured": 600000,
        "deductible": 1000,
        "copay": 0,
        "start": (2026, 4, 5),
        "end": (2027, 4, 4),
    },
    {
        # The sum insured is the Declared Business Property Value. No deductible was found, check the PDF
        "number": "POL-AST-2026-3389012-B01",
        "owner": "sunil.verma@example.com",
        "line": "commercial",
        "product": "AsterShield BusinessGuard Package",
        "sum_insured": 3000000,
        "deductible": 0,
        "copay": 0,
        "start": (2026, 10, 19),
        "end": (2027, 10, 18),
    },
    {
        # Building 50,00,000 plus contents 10,00,000. The deductible depends on the peril, check the PDF
        "number": "POL-AST-2026-7789012-H01",
        "owner": "vikramaditya.malhotra@example.com",
        "line": "home",
        "product": "AsterShield Home Secure Plus",
        "sum_insured": 6000000,
        "deductible": 2000,
        "copay": 0,
        "start": (2026, 11, 1),
        "end": (2027, 10, 31),
    },
]


def main():
    """Create the customers and policies from the PDFs. Safe to run more than once."""
    db = SessionLocal()
    try:
        owners = {}
        for item in CUSTOMERS:
            user = find_user_by_email(db, item["email"])
            if not user:
                user = User(
                    email=item["email"],
                    password_hash=hash_password(SEED_PASSWORD),
                    full_name=item["full_name"],
                    role="customer",
                )
                db.add(user)
                db.flush()
                print(f"Created customer {item['email']}")
            owners[item["email"]] = user

        for item in POLICIES:
            existing = db.query(Policy).filter(Policy.policy_number == item["number"]).first()
            if existing:
                continue

            year, month, day = item["start"]
            start_date = datetime(year, month, day, tzinfo=timezone.utc)

            year, month, day = item["end"]
            end_date = datetime(year, month, day, 23, 59, 59, tzinfo=timezone.utc)

            policy = Policy(
                policy_number=item["number"],
                owner_id=owners[item["owner"]].id,
                line=item["line"],
                product=item["product"],
                sum_insured=item["sum_insured"],
                deductible=item["deductible"],
                copay_percent=item["copay"],
                start_date=start_date,
                end_date=end_date,
            )
            db.add(policy)
            print(f"Created policy {item['number']}")

        db.commit()
        print(f"Done. Password for all seeded customers: {SEED_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()