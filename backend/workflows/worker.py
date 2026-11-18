import argparse
import time

from datetime import timedelta

from sqlalchemy import or_

from database.connection import SessionLocal
from database.models import WorkflowEvent, utc_now

from workflows.claim_workflow import build_claim_workflow
from workflows.persistence import open_checkpointer


def claim_next_event(db):
    now = utc_now()

    event = (
        db.query(WorkflowEvent)
        .filter(
            WorkflowEvent.event_type.in_([
                "claim.submitted",
                "claim.info_received",
            ]),
            or_(
                WorkflowEvent.status == "pending",
                (
                    WorkflowEvent.status == "processing"
                ) & (
                    WorkflowEvent.claimed_at
                    < now - timedelta(minutes=10)
                ),
            ),
        )
        .order_by(WorkflowEvent.created_at.asc())
        .with_for_update(skip_locked=True)
        .first()
    )

    if event is None:
        db.rollback()
        return None

    event.status = "processing"
    event.claimed_at = now
    event.attempts += 1

    db.commit()

    return event.id, event.claim_id


def process_one_event():
    db = SessionLocal()

    try:
        claimed = claim_next_event(db)

        if not claimed:
            return False

        event_id, claim_id = claimed

        try:
            with open_checkpointer() as checkpointer:
                checkpointer.setup()

                graph = build_claim_workflow(
                    db,
                    checkpointer
                )

                graph.invoke(
                    {
                        "claim_id": claim_id
                    },
                    config={
                        "configurable": {
                            "thread_id": claim_id
                        }
                    }
                )

            event = (
                db.query(WorkflowEvent)
                .filter(WorkflowEvent.id == event_id)
                .first()
            )

            if event:
                event.status = "completed"
                event.completed_at = utc_now()
                event.last_error = None

            db.commit()

        except Exception as exc:
            db.rollback()

            event = (
                db.query(WorkflowEvent)
                .filter(WorkflowEvent.id == event_id)
                .first()
            )

            if event:
                event.status = (
                    "failed"
                    if event.attempts >= 3
                    else "pending"
                )

                event.last_error = str(exc)[:2000]
                event.claimed_at = None

                db.commit()

            raise

        return True

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="CLAIMPILOT workflow worker"
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one event"
    )

    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=3.0
    )

    args = parser.parse_args()

    while True:
        try:
            worked = process_one_event()

        except Exception as exc:
            print(f"Workflow event failed: {exc}")
            worked = False

        if args.once:
            break

        if not worked:
            time.sleep(
                max(args.poll_seconds, 0.5)
            )


if __name__ == "__main__":
    main()