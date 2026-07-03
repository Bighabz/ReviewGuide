"""
Create default admin user

Creates an admin user (username from ADMIN_SEED_USERNAME, default 'admin'). The
password MUST come from the ADMIN_SEED_PASSWORD env var — there is deliberately
no hardcoded default, so a DB reset can never seed a well-known credential.

Usage:
    ADMIN_SEED_PASSWORD='<strong-password>' python scripts/create_default_admin.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import init_db, close_db
from app.repositories.admin_user_repository import AdminUserRepository
from app.utils.auth import hash_password


async def create_default_admin():
    """Create default admin user if it doesn't exist"""
    print("Creating default admin user...")

    # Initialize database
    await init_db()

    # Import AsyncSessionLocal AFTER init_db() has run
    from app.core.database import AsyncSessionLocal

    username = os.environ.get("ADMIN_SEED_USERNAME", "admin")
    email = os.environ.get("ADMIN_SEED_EMAIL", "admin@reviewguide.ai")
    password = os.environ.get("ADMIN_SEED_PASSWORD")
    if not password:
        print("❌ ADMIN_SEED_PASSWORD is not set — refusing to seed a default password.")
        print("   Re-run: ADMIN_SEED_PASSWORD='<strong-password>' python scripts/create_default_admin.py")
        await close_db()
        sys.exit(1)
    if len(password) < 12:
        print("❌ ADMIN_SEED_PASSWORD must be at least 12 characters.")
        await close_db()
        sys.exit(1)

    # Create admin user
    async with AsyncSessionLocal() as db:
        repo = AdminUserRepository(db)

        # Check if admin user already exists
        existing_admin = await repo.get_by_username(username)

        if existing_admin:
            print(f"⚠️  Admin user '{username}' already exists, skipping creation")
        else:
            # Hash the password (never printed back)
            password_hash = hash_password(password)

            # Create new admin user
            await repo.create(
                username=username,
                email=email,
                password_hash=password_hash
            )
            print(f"✅ Admin user '{username}' created (password from ADMIN_SEED_PASSWORD)")

    # Close database
    await close_db()


if __name__ == "__main__":
    asyncio.run(create_default_admin())
