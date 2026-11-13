import time
import uuid

from database.models import AgentExecutionLog


def make_trace_config(agent_name, agent_version, run_id, claim_id):
    """Build the LangChain config that names a run for LangSmith. It holds IDs only, no personal data."""
    return {
        "run_name": f"{agent_name}_agent",
        "run_id": uuid.UUID(run_id),
        "tags": [agent_name, f"v{agent_version}"],
        "metadata": {
            "claim_id": claim_id,
            "agent": agent_name,
            "agent_version": agent_version,
            # LangSmith groups runs with the same thread_id, so one claim is one thread
            "thread_id": claim_id,
        },
    }


def save_log(db, run_id, claim_id, agent_name, agent_version, model_name, status, input_summary, output, error, duration_ms):
    """Save one row in agent_execution_logs."""
    row = AgentExecutionLog(
        run_id=run_id,
        claim_id=claim_id,
        agent_name=agent_name,
        agent_version=agent_version,
        model_name=model_name,
        status=status,
        input_summary=input_summary,
        output=output,
        error=error,
        duration_ms=duration_ms,
    )
    db.add(row)
    db.commit()


def run_with_log(db, agent_name, agent_version, model_name, claim_id, input_summary, work):
    """Run work(run_id) and save a log row, whether it succeeds or fails."""
    run_id = str(uuid.uuid4())
    started = time.monotonic()

    try:
        output = work(run_id)
    except Exception as error:
        # Undo any half-finished database work, save the failure, then pass the error on
        db.rollback()
        duration_ms = int((time.monotonic() - started) * 1000)
        save_log(db, run_id, claim_id, agent_name, agent_version, model_name, "failed", input_summary, None, str(error)[:1000], duration_ms)
        raise

    duration_ms = int((time.monotonic() - started) * 1000)
    save_log(db, run_id, claim_id, agent_name, agent_version, model_name, "success", input_summary, output, None, duration_ms)
    return output