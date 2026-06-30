from app.db.session import SessionLocal
from app.models.models import IdentityRegistry, VerificationStatus

def seed_identity_registry():
    db = SessionLocal()
    try:
        records = [
            IdentityRegistry(nin="12345678901", full_name="Chidera Okonkwo", phone_number="09034679837"),
            IdentityRegistry(nin="98765432109", full_name="Amaka Nwosu",     phone_number="08098765432"),
            IdentityRegistry(nin="11122233344", full_name="Emeka Adeyemi",   phone_number="07011122233"),
        ]
        db.add_all(records)
        db.commit()
        print("Identity registry seeded.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_identity_registry()