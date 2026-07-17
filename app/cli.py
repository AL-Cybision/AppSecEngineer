import argparse
import asyncio
import getpass

from email_validator import validate_email
from sqlalchemy import select

from app.database import SessionFactory
from app.models import Role, User
from app.security import hash_password


async def create_admin(email: str) -> None:
    normalized = validate_email(email, check_deliverability=False).normalized.lower()
    password = getpass.getpass("Administrator password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    if not 12 <= len(password) <= 128:
        raise SystemExit("Password must contain 12 to 128 characters")
    async with SessionFactory() as db:
        if await db.scalar(select(User).where(User.email == normalized)):
            raise SystemExit("User already exists")
        db.add(User(email=normalized, password_hash=hash_password(password), role=Role.ADMIN))
        await db.commit()
    print(f"Created administrator {normalized}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="expenseguard")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create-admin")
    create.add_argument("email")
    args = parser.parse_args()
    if args.command == "create-admin":
        asyncio.run(create_admin(args.email))


if __name__ == "__main__":
    main()
