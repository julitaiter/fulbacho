"""Run from any working directory: python api/scripts/bootstrap_superuser.py."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    # Optional bootstrap must work even when no DB settings are configured.
    if not all(os.getenv(key, "").strip() for key in (
        "BOOTSTRAP_SUPERUSER_EMAIL", "BOOTSTRAP_SUPERUSER_PASSWORD", "BOOTSTRAP_SUPERUSER_NAME"
    )):
        print("Superuser bootstrap: skipped (optional variables incomplete).")
        return
    from app.core.database import SessionLocal
    from app.modules.auth.bootstrap import bootstrap_superuser

    with SessionLocal() as db:
        outcome = bootstrap_superuser(db)
    print(f"Superuser bootstrap: {outcome}.")


if __name__ == "__main__":
    main()
