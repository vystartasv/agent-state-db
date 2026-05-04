"""Tests for Agent State DB."""
import os
import tempfile
import pytest
from agent_state_db import AgentStateDB


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        yield AgentStateDB(db_path=db_path)


class TestAgents:
    def test_register(self, db):
        agent = db.register_agent("test", type="cron", cron_job_id="abc")
        assert agent["name"] == "test"
        assert agent["type"] == "cron"

    def test_register_upsert(self, db):
        a1 = db.register_agent("test", type="cron", cron_job_id="abc")
        a2 = db.register_agent("test", type="interactive", cron_job_id="xyz")
        assert a1["agent_id"] == a2["agent_id"]
        assert a2["type"] == "interactive"

    def test_lookup_by_name(self, db):
        db.register_agent("test", cron_job_id="abc")
        assert db.get_agent_by_name("test")["cron_job_id"] == "abc"

    def test_lookup_by_cron(self, db):
        db.register_agent("test", cron_job_id="abc")
        assert db.get_agent_by_cron_job_id("abc")["name"] == "test"


class TestRuns:
    def test_lifecycle(self, db):
        agent = db.register_agent("test")
        run_id = db.start_run(agent["agent_id"])
        db.finish_run(run_id, status="completed")
        run = db.get_run(run_id)
        assert run["status"] == "completed"

    def test_recent_failures(self, db):
        agent = db.register_agent("test")
        for _ in range(3):
            r = db.start_run(agent["agent_id"])
            db.finish_run(r, status="failed")
        assert db.get_recent_failures(agent["agent_id"]) == 3


class TestState:
    def test_atomic_increment(self, db):
        agent = db.register_agent("test")
        v1 = db.set_state(agent["agent_id"], "counter", 0)
        v2 = db.set_state(agent["agent_id"], "counter", 1)
        assert v1 == 1
        assert v2 == 2


class TestLocks:
    def test_acquire_release(self, db):
        agent = db.register_agent("test")
        assert db.acquire_lock("resource", agent["agent_id"])
        assert not db.acquire_lock("resource", "other")
        db.release_lock("resource", agent["agent_id"])
        assert db.check_lock("resource") is None
