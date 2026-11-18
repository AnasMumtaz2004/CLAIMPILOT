from contextlib import contextmanager
from sqlalchemy.engine import make_url

from langgraph.checkpoint.postgres import PostgresSaver

from config import settings


def get_psycopg_database_url():
    url = make_url(settings.database_url)

    # LangGraph PostgresSaver uses psycopg.
    if url.drivername.startswith("postgresql+"):
        url = url.set(drivername="postgresql")

    elif url.drivername == "postgres":
        url = url.set(drivername="postgresql")

    return url.render_as_string(
        hide_password=False
    )


@contextmanager
def open_checkpointer():
    database_url = get_psycopg_database_url()

    with PostgresSaver.from_conn_string(
        database_url
    ) as checkpointer:
        yield checkpointer