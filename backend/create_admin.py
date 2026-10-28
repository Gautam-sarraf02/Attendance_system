#!/usr/bin/env python3
"""
Secure CLI tool to initialize or manage the system Administrator account.
Ensures production deployments do not rely on hardcoded credentials.

Usage:
    Interactive prompt:
        python create_admin.py

    Non-interactive via CLI args:
        python create_admin.py --username sysadmin --email sysadmin@college.edu --password SecurePassword123

    Non-interactive via Environment Variables:
        INITIAL_ADMIN_USERNAME=sysadmin INITIAL_ADMIN_PASSWORD=SecurePassword123 INITIAL_ADMIN_EMAIL=sysadmin@college.edu python create_admin.py
"""

import sys
import os
import argparse
import getpass
from pathlib import Path

# Add backend directory to sys.path so app modules can be imported
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal, engine, Base
from app.models.user import User
from app.auth.jwt_handler import get_password_hash


def create_admin(username: str, email: str, password: str, full_name: str = "System Administrator"):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        username = username.strip()
        email = email.strip() if email else None

        if len(password) < 8:
            print("Error: Password must be at least 8 characters long for security.", file=sys.stderr)
            return False

        existing = db.query(User).filter(User.username == username).first()
        if existing:
            if existing.role != "admin":
                print(f"User '{username}' already exists with role '{existing.role}'. Promoting to admin...", file=sys.stderr)
                existing.role = "admin"
                existing.password_hash = get_password_hash(password)
                existing.is_active = True
                db.commit()
                print(f"Successfully promoted '{username}' to administrator.")
                return True
            else:
                print(f"Administrator '{username}' already exists. Updating password...", file=sys.stderr)
                existing.password_hash = get_password_hash(password)
                existing.is_active = True
                db.commit()
                print(f"Successfully updated password for administrator '{username}'.")
                return True

        admin_user = User(
            username=username,
            password_hash=get_password_hash(password),
            full_name=full_name,
            email=email,
            role="admin",
            is_active=True
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        print(f"Successfully created administrator account: '{username}' (ID: {admin_user.id}).")
        return True
    except Exception as e:
        db.rollback()
        print(f"Error creating admin account: {e}", file=sys.stderr)
        return False
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Create or update initial Administrator account.")
    parser.add_argument("--username", help="Administrator username")
    parser.add_argument("--email", help="Administrator email address")
    parser.add_argument("--password", help="Administrator password (min 8 chars)")
    parser.add_argument("--full-name", default="System Administrator", help="Administrator display name")

    args = parser.parse_args()

    username = args.username or os.getenv("INITIAL_ADMIN_USERNAME")
    email = args.email or os.getenv("INITIAL_ADMIN_EMAIL")
    password = args.password or os.getenv("INITIAL_ADMIN_PASSWORD")
    full_name = args.full_name or os.getenv("INITIAL_ADMIN_FULL_NAME", "System Administrator")

    # If any required fields are missing, prompt interactively
    if not username:
        try:
            username = input("Enter admin username: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

    if not email:
        try:
            email = input("Enter admin email address: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

    if not password:
        try:
            while True:
                pwd1 = getpass.getpass("Enter admin password (min 8 characters): ")
                if len(pwd1) < 8:
                    print("Password must be at least 8 characters long. Please try again.")
                    continue
                pwd2 = getpass.getpass("Confirm admin password: ")
                if pwd1 != pwd2:
                    print("Passwords do not match. Please try again.")
                    continue
                password = pwd1
                break
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

    success = create_admin(username=username, email=email, password=password, full_name=full_name)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
