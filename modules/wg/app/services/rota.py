from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chore, ChoreEntry, ChoreSwap, Member, RotaConfig
from app.timezone import berlin_today, week_start

# spec.md §3.2: a chore_entry beats everything else, so a real "done" by a
# substitute always wins over the computed absence/missed/open status.
# Phase 2 adds the absence check (no Absence model exists yet) - see
# docs/roadmap.md "Phase 2 · Alltag".
STATUS_DONE = "done"
STATUS_SKIPPED = "skipped"
STATUS_MISSED = "missed"
STATUS_OPEN = "open"


def latest_rota_config(db: Session, week: date) -> RotaConfig | None:
    # Tie-break on id too: two configs can share a valid_from (e.g. two
    # membership changes before anyone looks at the preview, or "ab dieser
    # Woche neu festlegen" clicked twice) - without this, ordering by
    # valid_from alone leaves it to the database which one "wins".
    return db.scalars(
        select(RotaConfig)
        .where(RotaConfig.valid_from <= week)
        .order_by(RotaConfig.valid_from.desc(), RotaConfig.id.desc())
        .limit(1)
    ).first()


def base_assignment(config: RotaConfig | None, week: date) -> dict[int, int | None]:
    """chore_id -> member_id | None, per spec.md §3.1 - before swaps."""
    if config is None:
        return {}
    weeks_elapsed = (week - config.valid_from).days // 7
    n = len(config.slots)
    result: dict[int, int | None] = {chore_id: None for chore_id in config.chore_ids}
    for slot, member_id in enumerate(config.slots):
        if member_id is None:
            continue
        index = (slot + weeks_elapsed) % n
        if index < len(config.chore_ids):
            result[config.chore_ids[index]] = member_id
    return result


def apply_swaps(
    db: Session, week: date, assignment_map: dict[int, int | None]
) -> dict[int, int | None]:
    """Each swap trades member_a's and member_b's chores *from the
    unswapped assignment* - multiple swaps in the same week are
    independent of each other, not chained."""
    swaps = db.scalars(select(ChoreSwap).where(ChoreSwap.week == week)).all()
    if not swaps:
        return dict(assignment_map)

    result = dict(assignment_map)
    for swap in swaps:
        chore_a = next(
            (cid for cid, mid in assignment_map.items() if mid == swap.member_a_id), None
        )
        chore_b = next(
            (cid for cid, mid in assignment_map.items() if mid == swap.member_b_id), None
        )
        if chore_a is not None:
            result[chore_a] = swap.member_b_id
        if chore_b is not None:
            result[chore_b] = swap.member_a_id
    return result


def assignment(db: Session, week: date) -> dict[int, int | None]:
    """chore_id -> member_id | None for `week`, swaps included."""
    config = latest_rota_config(db, week)
    return apply_swaps(db, week, base_assignment(config, week))


def get_chore_entry(db: Session, week: date, chore_id: int) -> ChoreEntry | None:
    return db.scalars(
        select(ChoreEntry).where(ChoreEntry.week == week, ChoreEntry.chore_id == chore_id)
    ).first()


def chore_status(
    db: Session,
    week: date,
    chore_id: int,
    assigned_member_id: int | None,
    *,
    today: date | None = None,
) -> tuple[str, ChoreEntry | None]:
    """The status to show for one chore/week per spec.md §3.2's order of
    checks: a real entry first, then (Phase 2: absence,) then missed/open."""
    entry = get_chore_entry(db, week, chore_id)
    if entry is not None:
        return entry.status, entry

    if week < week_start(today or berlin_today()):
        return STATUS_MISSED, None

    return STATUS_OPEN, None


def active_chores(db: Session) -> list[Chore]:
    return list(db.scalars(select(Chore).where(Chore.active.is_(True)).order_by(Chore.position)))


def rebuild_rota(
    db: Session,
    *,
    effective_from: date,
    member_ids_in_position_order: list[int],
    chore_ids_in_order: list[int],
    created_by: int | None,
) -> RotaConfig:
    """New rota_config effective from `effective_from`, per spec.md §3.3.
    Continuity: anyone keeping both their membership and chore keeps their
    already-"next" assignment; everyone else fills the remaining slots,
    chore slots first, in position order."""
    old_config = latest_rota_config(db, effective_from)
    old_assignment = base_assignment(old_config, effective_from)

    slot_count = max(len(member_ids_in_position_order), len(chore_ids_in_order))
    slots: list[int | None] = [None] * slot_count
    placed: set[int] = set()

    for chore_id, member_id in old_assignment.items():
        if member_id in member_ids_in_position_order and chore_id in chore_ids_in_order:
            slots[chore_ids_in_order.index(chore_id)] = member_id
            placed.add(member_id)

    remaining_members = [m for m in member_ids_in_position_order if m not in placed]
    free_slots = [i for i in range(slot_count) if slots[i] is None]
    free_slots.sort(key=lambda i: (i >= len(chore_ids_in_order), i))

    for member_id, slot_index in zip(remaining_members, free_slots, strict=False):
        slots[slot_index] = member_id

    config = RotaConfig(
        valid_from=effective_from,
        chore_ids=list(chore_ids_in_order),
        slots=slots,
        created_by=created_by,
    )
    db.add(config)
    return config


def mark_done(
    db: Session, *, week: date, chore_id: int, assigned_member_id: int | None, done_by: int
) -> ChoreEntry:
    entry = get_chore_entry(db, week, chore_id)
    if entry is None:
        entry = ChoreEntry(week=week, chore_id=chore_id)
        db.add(entry)
    entry.assigned_member_id = assigned_member_id
    entry.status = STATUS_DONE
    entry.reason = None
    entry.done_by_member_id = done_by
    entry.acted_at = datetime.now(UTC)
    return entry


def mark_skipped(
    db: Session,
    *,
    week: date,
    chore_id: int,
    assigned_member_id: int | None,
    done_by: int,
    reason: str,
) -> ChoreEntry:
    entry = get_chore_entry(db, week, chore_id)
    if entry is None:
        entry = ChoreEntry(week=week, chore_id=chore_id)
        db.add(entry)
    entry.assigned_member_id = assigned_member_id
    entry.status = STATUS_SKIPPED
    entry.reason = reason
    entry.done_by_member_id = done_by
    entry.acted_at = datetime.now(UTC)
    return entry


def undo(db: Session, *, week: date, chore_id: int) -> bool:
    entry = get_chore_entry(db, week, chore_id)
    if entry is None:
        return False
    db.delete(entry)
    return True


def rows_in_chore_order(
    db: Session,
    chores: list[Chore],
    week: date,
    members: dict[int, Member],
    my_member_id: int,
) -> list[dict]:
    """One row per chore, in the fixed `chores` order - needed wherever
    several weeks are shown side by side (e.g. /chores' upcoming-weeks
    table), so a column always means the same chore across every row.
    Shared by /chores and the Start page's "Putzplan diese Woche" card."""
    assignment_map = assignment(db, week)
    rows = []
    for chore in chores:
        assigned_id = assignment_map.get(chore.id)
        status, entry = chore_status(db, week, chore.id, assigned_id)
        rows.append(
            {
                "chore": chore,
                "assigned_member": members.get(assigned_id) if assigned_id else None,
                "status": status,
                "entry": entry,
                "is_mine": assigned_id == my_member_id,
            }
        )
    return rows


def rows_for_week(
    db: Session,
    chores: list[Chore],
    week: date,
    members: dict[int, Member],
    my_member_id: int,
) -> list[dict]:
    """Same rows, but with the viewer's own chore moved first - for a
    single-week card, per design.md §5.2/§5.4. Never use this for a table
    spanning several weeks (see rows_in_chore_order)."""
    rows = rows_in_chore_order(db, chores, week, members, my_member_id)
    rows.sort(key=lambda row: row["is_mine"] is False)
    return rows


def rebuild_for_current_membership(
    db: Session, *, effective_from: date, created_by: int | None
) -> RotaConfig:
    """rebuild_rota() using whoever/whatever is active right now, in
    position order - the common case per spec.md §3.3's trigger list
    (member added/deactivated, chore added/deactivated, explicit
    "Rotation neu festlegen")."""
    member_ids = [
        m.id
        for m in db.scalars(select(Member).where(Member.active.is_(True)).order_by(Member.position))
    ]
    chore_ids = [c.id for c in active_chores(db)]
    return rebuild_rota(
        db,
        effective_from=effective_from,
        member_ids_in_position_order=member_ids,
        chore_ids_in_order=chore_ids,
        created_by=created_by,
    )
