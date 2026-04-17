import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session as SASession

from database import Base, get_db
from domain import identity, media, projects, platforms, ai, automation, enterprise  # noqa: F401 — registers models
from main import app

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    _engine = create_engine(
        TEST_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=_engine)
    yield _engine
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture()
def db(engine):
    # Wrap each test in a transaction + savepoint so that db.commit() inside
    # _seed_workspace is visible within the test but rolls back at teardown.
    # Without this, committed rows persist across tests and cause UNIQUE errors.
    connection = engine.connect()
    transaction = connection.begin()
    session = SASession(bind=connection)
    connection.begin_nested()  # savepoint

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, tx):
        if tx.nested and not tx.parent.nested:
            connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ── helpers ────────────────────────────────────────────────────────────────────

def _seed_workspace(db, slug: str, name: str) -> tuple[str, str]:
    """Create workspace + user + membership + auth session. Returns (workspace_id, token)."""
    from uuid import uuid4
    from domain.identity import AuthSession, Membership, User, Workspace

    ws = Workspace(name=name, slug=slug, plan_tier="starter", storage_quota_mb=1024, raw_retention_days=7)
    db.add(ws)
    db.flush()

    user = User(email=f"{slug}@test.local", name=name)
    db.add(user)
    db.flush()

    m = Membership(workspace_id=ws.id, user_id=user.id, role="owner")
    db.add(m)
    db.flush()

    token = str(uuid4())
    session = AuthSession(user_id=user.id, workspace_id=ws.id, token=token)
    db.add(session)
    db.commit()
    return ws.id, token


@pytest.fixture()
def workspace_a(db):
    return _seed_workspace(db, "ws-a", "Workspace A")


@pytest.fixture()
def workspace_b(db):
    return _seed_workspace(db, "ws-b", "Workspace B")
