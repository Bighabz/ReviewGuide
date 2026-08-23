"""Tests for httpio REQUEST BUILDERS only - pure, no network.

The urlopen-backed wrappers (execute/sse_post/pg_rest_query/telegram) are
never invoked here; only the pure _build_* helpers are exercised.
"""

import urllib.parse

import pytest

from lib import httpio


def test_build_request_encodes_query_and_body():
    url, method, headers, body = httpio._build_request(
        {
            "method": "post",
            "url": "https://x.example/rest/v1/runs",
            "headers": {"apikey": "k"},
            "query": {"run_id": "eq.r1", "select": "a,b"},
            "json": {"a": 1},
        }
    )
    assert method == "POST"
    assert headers == {"apikey": "k"}
    assert body == b'{"a": 1}'
    base, qs = url.split("?", 1)
    assert base.endswith("/rest/v1/runs")
    assert dict(urllib.parse.parse_qsl(qs)) == {"run_id": "eq.r1", "select": "a,b"}


def test_build_request_no_body_when_json_absent():
    _url, method, _headers, body = httpio._build_request(
        {"method": "GET", "url": "https://x.example/health"}
    )
    assert method == "GET"
    assert body is None


def test_build_pg_query_rows_for_session():
    url, query = httpio._build_pg_query("rows_for_session", {"session_id": "qa-auto-1"})
    assert url.endswith("/rest/v1/conversation_messages")
    assert query["session_id"] == "eq.qa-auto-1"
    assert query["select"] == "session_id"


def test_build_pg_query_orphan_scan_keys_on_content_not_user_id():
    _url, query = httpio._build_pg_query(
        "orphan_scan",
        {
            "content_marker": "qa-auto-20260822-ab",
            "window_start": "2026-08-22T00:00:00Z",
            "prefix": "qa-auto-",
        },
    )
    # conversation_messages has no user_id column: attribute by content.
    assert query["content"] == "like.*qa-auto-20260822-ab*"
    assert query["created_at"] == "gte.2026-08-22T00:00:00Z"
    assert "user_id" not in query
    # NOT-LIKE excludes the qa-auto namespace (the negative orphan scan).
    assert query["session_id"] == "not.like.qa-auto-*"


def test_build_pg_query_unknown_kind_raises():
    with pytest.raises(ValueError):
        httpio._build_pg_query("nonsense", {})


def test_build_telegram_puts_token_in_path_not_payload():
    url, payload = httpio._build_telegram("TOK123", "999", "hello")
    assert url.endswith("/botTOK123/sendMessage")
    assert payload["chat_id"] == "999"
    assert payload["text"] == "hello"
    assert "TOK123" not in repr(payload)  # token only in the URL path
