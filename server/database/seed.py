"""
Database seeder.
Creates one default admin account on first startup if the users table is empty.
Demo doctor and nurse accounts are also seeded for testing.

All seeded accounts have is_approved=True so they can log in immediately.
Self-registered users start with is_approved=False until admin assigns a role.

SECURITY: Change ALL default passwords immediately after first login.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from auth.utils import hash_password
from database.base import AsyncSessionLocal
from database.models import User

logger = logging.getLogger(__name__)


SEED_USERS = [
    {
        "username": "admin",
        "email": "admin@health.facility",
        "full_name": "System Administrator",
        "password": "Admin@12345!",
        "role": "admin",
    },
    {
        "username": "dr_joseph",
        "email": "drjoseph@health.facility",
        "full_name": "Dr. Joseph Omuyonga",
        "password": "Doctor@12345!",
        "role": "doctor",
    },
    {
        "username": "nurse_patrick",
        "email": "nursepatrick@health.facility",
        "full_name": "Nurse Patrick Mutuko",
        "password": "Nurse@12345!",
        "role": "nurse",
    },
]


async def seed_database():
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(User).limit(1))
            if result.scalars().first():
                logger.info("Database already seeded — skipping.")
                return

            logger.info("Seeding database with default accounts…")
            now = datetime.now(timezone.utc)

            for data in SEED_USERS:
                user = User(
                    username = data["username"],
                    email = data["email"],
                    full_name = data["full_name"],
                    password_hash = hash_password(data["password"]),
                    role = data["role"],
                    is_approved = True,   # seeded accounts are pre-approved
                    is_active = True,
                    must_change_password = False,
                    password_changed_at = now,
                )
                db.add(user)

            await db.commit()
            logger.warning(
                "\n" + "=" * 60 +
                "\n  DEFAULT CREDENTIALS - CHANGE IMMEDIATELY AFTER FIRST LOGIN" +
                "\n  admin       / Admin@12345!" +
                "\n  dr_smith    / Doctor@12345!  (doctor)" +
                "\n  nurse_jones / Nurse@12345!   (nurse)" +
                "\n" + "=" * 60
            )

        except Exception as exc:
            await db.rollback()
            logger.error("Seeding failed: %s", exc)
            raise