"""Seed the 8 demo users, the groups, and their memberships (idempotent).

Demo passwords are identical and intentionally weak -- this is a demo. The demo
password is documented in .env.example, never a real secret.

Usage:  uv run python scripts/seed_users.py
"""

from __future__ import annotations

from sqlmodel import select

from securerag.db.models import Group, User, UserGroup
from securerag.db.session import get_session, hash_password, init_db

GROUPS = ["all", "leadership", "hr", "finance", "engineering", "managers", "admin"]

# (id, name, email, role, groups) -- mirrors SPEC section 4.
USERS = [
    (
        "u_ceo",
        "Vikram Shah",
        "vikram.shah@acme.example",
        "CEO",
        ["leadership", "hr", "finance", "engineering", "all"],
    ),
    ("u_hrm", "Priya Mehta", "priya.mehta@acme.example", "HR Manager", ["hr", "managers", "all"]),
    ("u_hre", "Meera Joshi", "meera.joshi@acme.example", "HR Executive", ["hr", "all"]),
    ("u_fin", "Anita Desai", "anita.desai@acme.example", "Finance Analyst", ["finance", "all"]),
    (
        "u_engm",
        "Arjun Patel",
        "arjun.patel@acme.example",
        "Engineering Manager",
        ["engineering", "managers", "all"],
    ),
    (
        "u_eng",
        "Rahul Verma",
        "rahul.verma@acme.example",
        "Software Engineer",
        ["engineering", "all"],
    ),
    ("u_int", "Sneha Rao", "sneha.rao@acme.example", "Intern", ["all"]),
    ("u_admin", "Admin", "admin@acme.example", "Platform Admin", ["admin", "all"]),
]

DEMO_PASSWORD = "demo1234"  # documented in .env.example; demo only


def main() -> None:
    init_db()
    password_hash = hash_password(DEMO_PASSWORD)

    with get_session() as session:
        # Groups first; remember name -> id.
        name_to_id: dict[str, int] = {}
        for group_name in GROUPS:
            group = session.exec(select(Group).where(Group.name == group_name)).first()
            if group is None:
                group = Group(name=group_name)
                session.add(group)
                session.commit()
                session.refresh(group)
            name_to_id[group_name] = group.id

        # Users and their memberships (both idempotent).
        for user_id, name, email, role, groups in USERS:
            if session.get(User, user_id) is None:
                session.add(
                    User(id=user_id, name=name, email=email, role=role, password_hash=password_hash)
                )
                session.commit()
            for group_name in groups:
                gid = name_to_id[group_name]
                exists = session.exec(
                    select(UserGroup).where(UserGroup.user_id == user_id, UserGroup.group_id == gid)
                ).first()
                if exists is None:
                    session.add(UserGroup(user_id=user_id, group_id=gid))
            session.commit()

    print(f"Seeded {len(GROUPS)} groups and {len(USERS)} users.")
    print(f"Demo password for every user: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
