from app.db.session import SessionLocal
from app.models.models import User


def main() -> None:
    # Creates a database session for a one-off inspection query.
    db = SessionLocal()

    try:
        # Executes a lightweight COUNT query to verify schema + connectivity.
        count = db.query(User).count()
        print(f"Users in DB: {count}")
    finally:
        # Ensures connection cleanup even if query fails.
        db.close()


if __name__ == "__main__":
    main()