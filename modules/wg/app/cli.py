from __future__ import annotations

import argparse
import secrets
import sys
import tomllib
from datetime import date
from pathlib import Path

import segno
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Chore, ExpenseCategory, InfoPage, Member, RotaConfig, Setting
from app.services.backup import run_backup
from app.services.members import create_member


def _get_setting(db: Session, key: str) -> str:
    setting = db.get(Setting, key)
    if setting is None:
        raise RuntimeError(f"Setting '{key}' fehlt - wurde `init` schon ausgeführt?")
    return setting.value


def _print_link(token: str) -> None:
    link = f"{settings.app_base_url}/join/{token}"
    print(f"Beitrittslink: {link}")
    segno.make(link).terminal(compact=True)


def cmd_init(seed_path: Path) -> None:
    with SessionLocal() as db:
        if db.scalar(select(Setting).limit(1)) is not None:
            print("Datenbank ist nicht leer - init abgebrochen.")
            sys.exit(1)

        data = tomllib.loads(seed_path.read_text())
        wg = data["wg"]

        join_token = secrets.token_urlsafe(32)
        db.add_all(
            [
                Setting(key="wg_name", value=wg["name"]),
                Setting(key="default_language", value=wg["default_language"]),
                Setting(key="join_token", value=join_token),
                Setting(key="cookie_version", value="1"),
                Setting(key="admin_ntfy_topic", value=f"wg-admin-{secrets.token_hex(4)}"),
            ]
        )

        members: dict[str, Member] = {}
        for position, member_data in enumerate(data["members"]):
            member = create_member(
                db,
                name=member_data["name"],
                color=member_data["color"],
                language=member_data.get("language", wg["default_language"]),
                position=position,
                joined_on=date.today(),
            )
            members[member.name] = member

        chores: dict[str, Chore] = {}
        for position, chore_data in enumerate(data["chores"]):
            chore = Chore(
                key=chore_data["key"],
                name_de=chore_data["name_de"],
                name_en=chore_data["name_en"],
                position=position,
            )
            db.add(chore)
            chores[chore.key] = chore
        db.flush()  # need ids for rota_configs below

        rota = data["rota"]
        chore_ids = [chore.id for chore in chores.values()]
        slots = [members[rota["start"][key]].id for key in chores]
        db.add(
            RotaConfig(
                valid_from=date.fromisoformat(rota["start_week"]),
                chore_ids=chore_ids,
                slots=slots,
                created_by=None,
            )
        )

        for position, category_data in enumerate(data["expense_categories"]):
            db.add(
                ExpenseCategory(
                    key=category_data["key"],
                    name_de=category_data["name_de"],
                    name_en=category_data["name_en"],
                    position=position,
                )
            )

        # supplies (Phase 2) is intentionally skipped - no model/table yet.
        for position, page_data in enumerate(data.get("info_pages", [])):
            db.add(InfoPage(title=page_data["title"], body=page_data["body"], position=position))

        db.commit()

    print(f"{len(members)} Mitglieder, {len(chores)} Aufgaben angelegt.")
    _print_link(join_token)


def cmd_show_link() -> None:
    with SessionLocal() as db:
        token = _get_setting(db, "join_token")
    _print_link(token)


def cmd_rotate_link() -> None:
    with SessionLocal() as db:
        setting = db.get(Setting, "join_token")
        if setting is None:
            raise RuntimeError("Setting 'join_token' fehlt - wurde `init` schon ausgeführt?")
        setting.value = secrets.token_urlsafe(32)
        db.commit()
        token = setting.value
    print("Neuer Beitrittslink (der alte funktioniert nicht mehr):")
    _print_link(token)


def cmd_logout_all() -> None:
    with SessionLocal() as db:
        setting = db.get(Setting, "cookie_version")
        if setting is None:
            raise RuntimeError("Setting 'cookie_version' fehlt - wurde `init` schon ausgeführt?")
        setting.value = str(int(setting.value) + 1)
        db.commit()
    print("Alle Geräte sind abgemeldet.")


def cmd_backup() -> None:
    target = run_backup()
    print(f"Backup gespeichert: {target}")


def cmd_add_member(name: str) -> None:
    with SessionLocal() as db:
        existing_positions = db.scalars(select(Member.position)).all()
        position = max(existing_positions, default=-1) + 1
        member = create_member(
            db,
            name=name,
            color=position % 8,
            language=_get_setting(db, "default_language"),
            position=position,
            joined_on=date.today(),
        )
        db.commit()
        print(f"Mitglied angelegt: {member.name} (id={member.id})")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Seed-Daten einlesen (nur bei leerer DB)")
    init_parser.add_argument("--seed", type=Path, required=True)

    subparsers.add_parser("show-link", help="Beitrittslink anzeigen")
    subparsers.add_parser("rotate-link", help="Beitrittslink erneuern")
    subparsers.add_parser("logout-all", help="Alle Geräte abmelden")
    subparsers.add_parser("backup", help="Sofortiges Backup")

    add_member_parser = subparsers.add_parser("add-member", help="Notfall-Werkzeug")
    add_member_parser.add_argument("name")

    args = parser.parse_args(argv)

    if args.command == "init":
        cmd_init(args.seed)
    elif args.command == "show-link":
        cmd_show_link()
    elif args.command == "rotate-link":
        cmd_rotate_link()
    elif args.command == "logout-all":
        cmd_logout_all()
    elif args.command == "backup":
        cmd_backup()
    elif args.command == "add-member":
        cmd_add_member(args.name)


if __name__ == "__main__":
    main()
