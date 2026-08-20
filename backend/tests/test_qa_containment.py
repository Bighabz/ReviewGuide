"""
QA containment tests.

Synthetic QA traffic is marked by session_id prefix ``qa-auto-``. It must never
appear in user-visible aggregates (admin metrics, charts) or in the admin
/conversations listing.

Approach: the DB session is mocked (AsyncMock) exactly like sibling tests in
tests/test_chat_api.py, and the SQL text / WHERE clause built by each endpoint
is asserted to contain the exclusion predicate. This directly verifies every
aggregate query applies the filter.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.v1 import admin as admin_module
from app.api.v1.chat import list_conversations

QA_EXCLUDE_PREDICATE = "session_id NOT LIKE 'qa-auto-%'"


def _make_session():
    """Mock DB session matching the AsyncMock pattern used across the suite."""
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(
            fetchone=MagicMock(return_value=(0,)),
            fetchall=MagicMock(return_value=[]),
            all=MagicMock(return_value=[]),
        )
    )
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


def _sql_of(call):
    """Extract SQL text from a db.execute call, for text() and Core statements."""
    stmt = call.args[0]
    if hasattr(stmt, "text"):
        return stmt.text
    return str(stmt)


class TestMetricsAggregatesExcludeQA:
    """B1/B3(a)+(b): the 4 conversation_messages aggregates exclude qa-auto."""

    @pytest.mark.asyncio
    async def test_get_metrics_aggregate_queries_exclude_qa_auto(self):
        """All three SQL aggregates in get_metrics carry the exclusion predicate."""
        session = _make_session()
        with patch.object(admin_module, "fetch_langfuse_errors", return_value=[]):
            await admin_module.get_metrics(db=session, _admin={"type": "admin"})

        assert session.execute.await_count == 3, (
            f"expected 3 aggregate queries, got {session.execute.await_count}"
        )
        for call in session.execute.await_args_list:
            sql = _sql_of(call)
            assert QA_EXCLUDE_PREDICATE in sql, f"missing exclusion in: {sql}"

    @pytest.mark.asyncio
    async def test_get_chart_data_query_excludes_qa_auto(self):
        """The DATE_TRUNC bucket query in get_chart_data carries the exclusion."""
        session = _make_session()
        await admin_module.get_chart_data(timeframe="1h", db=session, _admin={"type": "admin"})

        assert session.execute.await_count == 1
        sql = _sql_of(session.execute.await_args_list[0])
        assert QA_EXCLUDE_PREDICATE in sql
        assert "DATE_TRUNC('minute', created_at)" in sql  # bucket grouping preserved
        assert "role = 'user'" in sql  # user-message filter preserved

    @pytest.mark.asyncio
    async def test_get_chart_data_24h_query_excludes_qa_auto(self):
        """The 24h branch buckets by hour and also excludes qa-auto."""
        session = _make_session()
        await admin_module.get_chart_data(timeframe="24h", db=session, _admin={"type": "admin"})

        sql = _sql_of(session.execute.await_args_list[0])
        assert QA_EXCLUDE_PREDICATE in sql
        assert "DATE_TRUNC('hour', created_at)" in sql


class TestConversationsListingExcludesQA:
    """B2/B3(c): the admin branch of GET /conversations excludes qa-auto."""

    @pytest.mark.asyncio
    async def test_admin_listing_excludes_qa_auto_sessions(self):
        session = _make_session()
        await list_conversations(
            session_id=None,
            session_ids=None,
            db=session,
            current_user={"type": "admin"},
        )

        assert session.execute.await_count == 1
        compiled = str(
            session.execute.await_args_list[0].args[0].compile(
                compile_kwargs={"literal_binds": True}
            )
        ).lower()
        assert "not like" in compiled, (
            f"expected a NOT LIKE exclusion on session_id, got: {compiled}"
        )
        assert "session_id" in compiled and "qa-auto-%" in compiled

    @pytest.mark.asyncio
    async def test_non_admin_listing_behavior_unchanged(self):
        """Non-admin callers keep the session_id allow-list filter, no qa-auto filter."""
        session = _make_session()
        await list_conversations(
            session_id="real-session-1",
            session_ids=None,
            db=session,
            current_user=None,
        )

        compiled = session.execute.await_args_list[0].args[0].compile(
            compile_kwargs={"literal_binds": True}
        )
        assert "real-session-1" in str(compiled)
        assert "qa-auto-%" not in str(compiled)


class TestExclusionPredicateDocumentation:
    """B3(d): all 4 aggregate SQL strings carry the production-owned predicate."""

    @pytest.mark.asyncio
    async def test_all_aggregate_sql_contains_production_predicate(self):
        from app.api.v1.admin import _QA_EXCLUDE_PREDICATE

        # metrics: 3 aggregates
        session = _make_session()
        with patch.object(admin_module, "fetch_langfuse_errors", return_value=[]):
            await admin_module.get_metrics(db=session, _admin={"type": "admin"})
        metrics_sql = [_sql_of(call) for call in session.execute.await_args_list]
        assert len(metrics_sql) == 3

        # chart: 1 aggregate per timeframe branch
        session_1h = _make_session()
        await admin_module.get_chart_data(timeframe="1h", db=session_1h, _admin={"type": "admin"})
        session_24h = _make_session()
        await admin_module.get_chart_data(timeframe="24h", db=session_24h, _admin={"type": "admin"})

        chart_sql = [
            _sql_of(session_1h.execute.await_args_list[0]),
            _sql_of(session_24h.execute.await_args_list[0]),
        ]

        for sql in metrics_sql + chart_sql:
            assert _QA_EXCLUDE_PREDICATE in sql, (
                f"aggregate SQL missing production predicate: {sql}"
            )
