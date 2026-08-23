"""Real network transport for the QA loop (stdlib urllib only).

This is the ONLY module that touches the network. Everything else takes
an injectable callable so unit tests stay offline. The request/response
BUILDERS here are pure (`_build_request`, `_build_pg_query`,
`_build_telegram`) and are what the tests exercise; the `execute` /
`sse_post` / `pg_rest_query` / telegram-sender wrappers add the actual
urlopen call on top.

Secrets rule: request HEADERS carry the Supabase service key, so nothing
in this module ever logs a header, a URL with embedded auth, or an env
secret value.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from lib import store  # reuse USER_AGENT + BASE_URL + service-key reader

DEFAULT_TIMEOUT_S = 30
TELEGRAM_API = "https://api.telegram.org"

# PostgREST reads of the app's real tables use the PUBLIC schema, unlike
# store.py which targets the qa.* schema.
PUBLIC_PROFILE = "public"


# --- network seam (monkeypatched in the rare test that needs it) ---------

def _urlopen(req, timeout):
    return urllib.request.urlopen(req, timeout=timeout)


def _read_json(resp):
    body = resp.read()
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


# --- generic executor for store.py payloads ------------------------------

def _build_request(request):
    """Pure: turn a store-style request dict into (url, method, headers,
    body_bytes). `query` is url-encoded onto the URL; `json` is encoded as
    the body (None -> no body)."""
    url = request["url"]
    query = request.get("query") or {}
    if query:
        sep = "&" if "?" in url else "?"
        url = url + sep + urllib.parse.urlencode(query)
    method = request.get("method", "GET").upper()
    headers = dict(request.get("headers") or {})
    body = None
    payload = request.get("json")
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    return url, method, headers, body


def execute(request, timeout=DEFAULT_TIMEOUT_S):
    """Perform a store-style request. Returns {"status", "json"}.

    Raises urllib.error.URLError on transport failure (the caller decides
    what a failure means; store writes are best-effort, marker queries are
    gate-critical)."""
    url, method, headers, body = _build_request(request)
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = _urlopen(req, timeout)
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "json": _read_json(exc)}
    with resp:
        return {"status": getattr(resp, "status", 200), "json": _read_json(resp)}


# --- chat SSE POST -------------------------------------------------------

def sse_post(url, payload, timeout_s=60, headers=None):
    """POST JSON to a streaming endpoint; return the list of raw text lines.

    marker._parse_stream consumes these `data:` lines. No auth header is
    attached (prod chat is unauthenticated); an Origin/UA may be passed in
    via headers."""
    body = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json", "User-Agent": store.USER_AGENT}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    lines = []
    resp = _urlopen(req, timeout_s)
    with resp:
        for raw in resp:
            lines.append(raw.decode("utf-8", "replace").rstrip("\n"))
    return lines


def status_get(url, timeout_s=DEFAULT_TIMEOUT_S, headers=None):
    """GET returning {"status", "json"} without raising on 4xx/5xx.

    Used by security probes (a 401/403/429 is data, not an error) and the
    /health/ready preflight."""
    hdrs = {"User-Agent": store.USER_AGENT}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs, method="GET")
    try:
        resp = _urlopen(req, timeout_s)
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "json": _read_json(exc), "headers": {}}
    with resp:
        return {
            "status": getattr(resp, "status", 200),
            "json": _read_json(resp),
            "headers": dict(resp.headers.items()),
        }


def post_status(url, payload, timeout_s=DEFAULT_TIMEOUT_S, headers=None):
    """POST JSON and return {"status", "json"} WITHOUT streaming and WITHOUT
    raising on 4xx/5xx. Used by the oversized-message probe (expects 422),
    which is a rejected request, not a chat exercise."""
    body = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json", "User-Agent": store.USER_AGENT}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        resp = _urlopen(req, timeout_s)
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "json": _read_json(exc)}
    with resp:
        return {"status": getattr(resp, "status", 200), "json": _read_json(resp)}


def options_cors(url, origin, method="POST", timeout_s=DEFAULT_TIMEOUT_S):
    """Send a CORS preflight; return {"status", "acao"} where acao is the
    Access-Control-Allow-Origin response header or None.

    A disallowed origin comes back WITHOUT that header (Starlette returns
    the header absent, and often a 400) - never a 403."""
    hdrs = {
        "User-Agent": store.USER_AGENT,
        "Origin": origin,
        "Access-Control-Request-Method": method,
    }
    req = urllib.request.Request(url, headers=hdrs, method="OPTIONS")
    try:
        resp = _urlopen(req, timeout_s)
    except urllib.error.HTTPError as exc:
        acao = exc.headers.get("Access-Control-Allow-Origin") if exc.headers else None
        return {"status": exc.code, "acao": acao}
    with resp:
        return {
            "status": getattr(resp, "status", 200),
            "acao": resp.headers.get("Access-Control-Allow-Origin"),
        }


# --- PostgREST query_fn for marker.assert_marker_intact ------------------

def _public_headers():
    key = store._service_key()
    return {
        "apikey": key,
        "Authorization": "Bearer %s" % key,
        "Accept": "application/json",
        "User-Agent": store.USER_AGENT,
        "Accept-Profile": PUBLIC_PROFILE,
    }


def _build_pg_query(kind, params):
    """Pure: build (url, query_dict) for a marker query kind against the
    public conversation_messages table. No auth here (headers added at
    send time)."""
    base = store.BASE_URL + "/rest/v1/conversation_messages"
    if kind == "rows_for_session":
        return base, {
            "select": "session_id",
            "session_id": "eq.%s" % params["session_id"],
        }
    if kind == "orphan_scan":
        # conversation_messages has no user_id column; attribute a leaked row
        # by the content marker the caller embedded in every probe message.
        prefix = params.get("prefix", "qa-auto-")
        return base, {
            "select": "id,session_id",
            "content": "like.*%s*" % params["content_marker"],
            "created_at": "gte.%s" % params["window_start"],
            "session_id": "not.like.%s*" % prefix,
        }
    raise ValueError("unknown marker query kind: %r" % kind)


def pg_rest_query(kind, params, timeout=DEFAULT_TIMEOUT_S):
    """Real query_fn for marker.assert_marker_intact. Returns a list of row
    dicts. RAISES on any HTTP/transport error - the marker gate treats an
    exception as NOT-proven (never silently green)."""
    url, query = _build_pg_query(kind, params)
    full = url + "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(full, headers=_public_headers(), method="GET")
    resp = _urlopen(req, timeout)
    with resp:
        rows = _read_json(resp)
    if not isinstance(rows, list):
        raise ValueError("PostgREST %s returned non-list" % kind)
    return rows


# --- Telegram sender (the P1 notify channel Habib chose) -----------------

def _build_telegram(token, chat_id, message):
    """Pure: (url, payload) for Telegram sendMessage. Token is in the URL
    path per Telegram's API - callers must never log the returned url."""
    url = "%s/bot%s/sendMessage" % (TELEGRAM_API, token)
    return url, {"chat_id": chat_id, "text": message, "disable_web_page_preview": True}


def make_telegram_sender(token, chat_id, timeout=DEFAULT_TIMEOUT_S):
    """Return a callable(message) -> {"status", "json"} that POSTs to
    Telegram. The token lives only in the closure and the request URL - it
    is never logged or echoed."""

    def _send(message):
        url, payload = _build_telegram(token, chat_id, message)
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            resp = _urlopen(req, timeout)
        except urllib.error.HTTPError as exc:
            return {"status": exc.code, "json": _read_json(exc)}
        with resp:
            return {"status": getattr(resp, "status", 200), "json": _read_json(resp)}

    return _send
