"""api_suite - marker-gated chat exercises + stateless security probes.

CONTAINMENT LAW (from the dual-verify, non-negotiable):
  * Conversations run STRICTLY SEQUENTIALLY. Parallelizing turns of one
    conversation, or reusing a user across concurrent conversations,
    detonates the server's UUID-swap race and breaks containment.
    Parallelizing api_suite is FORBIDDEN.
  * ONE session per conversation; `rand` varies per CONVERSATION; the
    user_id from turn 1's done event is threaded into EVERY later turn.
  * No chat exercise runs unless config marker_gate_proven is true. The
    only way to flip it true is a live `--prove-marker` run that passes
    assert_marker_intact against real persistence, reviewed by a human.

Security probes are single stateless requests (not conversations), so
they run even when the chat gate is closed - but never in dry_run.
"""

import sys

from lib import marker
from runners._base import EXIT_BREACH, EXIT_OK, emit, finding, main

RUNNER = "api_suite"

# One session per conversation; turns run in order; user_id threaded.
CONVERSATIONS = (
    {"name": "espresso", "turns": ("Best espresso machine under $500?",)},
    {
        "name": "cordless-vacuum",
        "turns": (
            "I need a cordless vacuum",
            "For hardwood floors and pet hair, around $300",
        ),
    },
    {
        "name": "robot-vacuum",
        "turns": (
            "Recommend a robot vacuum",
            "Which of those handles thick carpet best?",
        ),
    },
)

# Admin endpoints that MUST reject an unauthenticated caller. errors/chart
# is a KNOWN GAP (backend admin.py:478 has no auth dep) - it currently
# returns 200 and should surface as HIGH every run until backend is fixed.
ADMIN_PROBES = (
    ("/v1/admin/config", "GET"),
    ("/v1/admin/metrics", "GET"),
    ("/v1/admin/users", "GET"),
    ("/v1/admin/metrics/errors/chart", "GET"),
)

EVIL_ORIGIN = "https://qa-evil.invalid"


# --- provider honesty ----------------------------------------------------

def _provider_honesty(convo_name, turn_index, done):
    """A degraded provider must be reflected: if any provider_coverage entry
    reports error/timed_out, completeness must not be 'full'."""
    if not isinstance(done, dict):
        return [
            finding(
                "provider-honesty",
                "no-done-event",
                "%s#%d" % (convo_name, turn_index),
                "high",
                "no done event parsed from chat stream",
            )
        ]
    completeness = done.get("completeness")
    meta = done.get("response_metadata") or {}
    coverage = meta.get("provider_coverage") or []
    degraded_providers = [
        c for c in coverage if isinstance(c, dict) and c.get("status") in ("error", "timed_out")
    ]
    if completeness is None:
        return [
            finding(
                "provider-honesty",
                "missing-completeness",
                "%s#%d" % (convo_name, turn_index),
                "medium",
                "done event carried no completeness field",
            )
        ]
    if degraded_providers and completeness == "full":
        names = ",".join(str(c.get("provider")) for c in degraded_providers)
        return [
            finding(
                "provider-honesty",
                "hidden-degradation",
                "%s#%d" % (convo_name, turn_index),
                "high",
                "completeness=full despite degraded providers: %s" % names,
            )
        ]
    return []


# --- one conversation (sequential) ---------------------------------------

def _run_conversation(ctx, convo, window_start):
    session = marker.mint_session(ctx.now_fn(), ctx.rand_fn())
    turns = convo["turns"]
    findings = []
    user_id = None
    for i, message in enumerate(turns):
        # Embed the qa-auto session string in the message so a re-keyed
        # (leaked) row is attributable by content in the orphan scan.
        marked = "%s\n\n[qa-ref:%s]" % (message, session)
        ok, returned_uid, done = marker.chat_turn_full(
            ctx.post_fn, session, marked, user_id=user_id
        )
        if not ok:
            findings.append(
                finding(
                    "api",
                    "chat-turn-failed",
                    "%s#%d" % (convo["name"], i),
                    "high",
                    "chat turn %d failed for %s" % (i, convo["name"]),
                )
            )
        findings.extend(_provider_honesty(convo["name"], i, done))
        # Thread the FIRST captured user_id into every later turn; never let a
        # later turn's None clobber it.
        if user_id is None and returned_uid is not None:
            user_id = returned_uid
        # Containment guard: sending a later turn WITHOUT a user_id is the
        # documented UUID-swap detonator - refuse rather than breach prod.
        if user_id is None and i < len(turns) - 1:
            findings.append(
                finding(
                    "marker",
                    "turn-no-user-id",
                    "%s#%d" % (convo["name"], i),
                    "high",
                    "turn %d returned no user_id; refusing to send turn %d "
                    "(would breach containment)" % (i, i + 1),
                )
            )
            return findings, True, i + 1

    messages_per_turn = int(ctx.config.get("messages_per_turn", 2))
    expected = len(turns) * messages_per_turn
    settle_interval = float(ctx.config.get("marker_settle_interval_s", 2.0))
    settle_attempts = int(ctx.config.get("marker_settle_attempts", 15))
    ok_marker, reason = marker.assert_marker_intact(
        ctx.query_fn,
        session,
        expected_turns=expected,
        content_marker=session,
        window_start=window_start,
        settle_sleep=lambda: ctx.sleep_fn(settle_interval),
        settle_attempts=settle_attempts,
    )
    breached = not ok_marker
    if breached:
        findings.append(
            finding(
                "marker",
                "containment-breach",
                convo["name"],
                "high",
                "marker breach on %s: %s" % (convo["name"], reason),
            )
        )
    return findings, breached, len(turns)


# --- security probes (stateless, always-run-except-dry) ------------------

def _security_probes(ctx):
    findings = []
    backend = ctx.config["prod_backend"].rstrip("/")
    interval = float(ctx.config.get("security_probe_interval_s", 1.5))

    # Preflight readiness: abort probes if not ready (never hammer a
    # degraded prod).
    try:
        ready = ctx.http_get(backend + "/health/ready")
    except Exception as exc:  # noqa: BLE001
        return [
            finding(
                "security",
                "readiness-preflight-failed",
                "/health/ready",
                "info",
                "skipped probes: /health/ready unreachable (%s)" % exc,
            )
        ]
    if ready.get("status") != 200:
        return [
            finding(
                "security",
                "not-ready",
                "/health/ready",
                "info",
                "skipped probes: /health/ready status %s" % ready.get("status"),
            )
        ]
    manifest = (ready.get("json") or {}).get("manifest") or {}
    rate_limited = bool(manifest.get("rate_limiting_enabled"))

    def _spaced(fn):
        ctx.sleep_fn(interval)
        return fn()

    # 1-4: admin endpoints must not answer 200 unauthenticated.
    for path, _method in ADMIN_PROBES:
        try:
            resp = _spaced(lambda p=path: ctx.http_get(backend + p))
        except Exception as exc:  # noqa: BLE001
            findings.append(
                finding("security", "probe-error", path, "low", "probe error: %s" % exc)
            )
            continue
        status = resp.get("status")
        if status == 429 and rate_limited:
            continue  # tolerated: rate limiter answered before auth
        if status == 200:
            sev = "high"
            findings.append(
                finding(
                    "security",
                    "admin-unauthenticated-200",
                    path,
                    sev,
                    "unauthenticated %s returned 200 (expected 401/403)" % path,
                )
            )
        elif status not in (401, 403):
            findings.append(
                finding(
                    "security",
                    "admin-unexpected-status",
                    path,
                    "low",
                    "unauthenticated %s returned %s (expected 401/403)" % (path, status),
                )
            )

    # 5: oversized message must be rejected (422) before any chat happens.
    # Carry a qa-auto session id so that IF max_length ever regresses and the
    # probe is accepted as a real turn, the row stays inside containment and
    # is prunable (never an unmarked, invisible prod write).
    try:
        big = "x" * 5001
        # Derived from run_id (NOT the conversation rand sequence) so it is
        # prunable but does not perturb per-conversation session ids.
        probe_session = "%sprobe-%s" % (marker.MARKER_PREFIX, ctx.run_id)
        resp = _spaced(
            lambda: ctx.http_post(
                backend + "/v1/chat/stream",
                {"message": big, "session_id": probe_session},
            )
        )
        if resp.get("status") != 422:
            findings.append(
                finding(
                    "security",
                    "oversized-not-rejected",
                    "/v1/chat/stream",
                    "high",
                    "5001-char message returned %s (expected 422); a regressed "
                    "max_length would persist a real chat turn" % resp.get("status"),
                )
            )
    except Exception as exc:  # noqa: BLE001
        findings.append(
            finding("security", "probe-error", "/v1/chat/stream", "low", "probe error: %s" % exc)
        )

    # 6: hostile CORS origin must not be echoed back.
    try:
        cors = _spaced(
            lambda: ctx.http_options(
                backend + "/v1/chat/stream", EVIL_ORIGIN, "POST"
            )
        )
        acao = cors.get("acao")
        if acao and (acao == EVIL_ORIGIN or acao == "*"):
            findings.append(
                finding(
                    "security",
                    "cors-origin-reflected",
                    "/v1/chat/stream",
                    "high",
                    "hostile Origin reflected in Access-Control-Allow-Origin: %s" % acao,
                )
            )
    except Exception as exc:  # noqa: BLE001
        findings.append(
            finding("security", "probe-error", "cors", "low", "probe error: %s" % exc)
        )

    return findings


# --- prove-marker (the live gate) ----------------------------------------

def _prove_marker(ctx):
    """Run EXACTLY one 2-turn conversation live and prove containment.

    Prints MARKER_GATE_GREEN on success (operator then flips config
    marker_gate_proven). On any failure/exception exits EXIT_BREACH. Never
    flips config itself."""
    convo = {"name": "prove-marker", "turns": ("I need a cordless vacuum", "Around $300 for pet hair")}
    window_start = ctx.now_fn()
    try:
        findings, breached, _turns = _run_conversation(ctx, convo, window_start)
    except Exception as exc:  # noqa: BLE001
        emit(
            ctx,
            RUNNER,
            [finding("marker", "prove-marker-error", "prove-marker", "high", "prove-marker crashed: %s" % exc)],
            extra={"prove_marker": True, "result": "error"},
        )
        sys.stderr.write("MARKER_GATE_RED: prove-marker crashed: %s\n" % exc)
        return EXIT_BREACH
    if breached:
        emit(ctx, RUNNER, findings, extra={"prove_marker": True, "result": "breach"})
        sys.stderr.write(
            "MARKER_GATE_RED: containment not proven. Do NOT set marker_gate_proven.\n"
        )
        return EXIT_BREACH
    emit(ctx, RUNNER, findings, extra={"prove_marker": True, "result": "green"})
    sys.stdout.write(
        "MARKER_GATE_GREEN: live 2-turn containment proven.\n"
        "Next: set qa/config.json marker_gate_proven=true (human review) to "
        "unlock api_suite chat exercises.\n"
    )
    return EXIT_OK


# --- entry ---------------------------------------------------------------

def run(ctx, args):
    if getattr(args, "prove_marker", False):
        return _prove_marker(ctx)

    # dry_run: absolutely no network. Emit a skipped summary and prove (via
    # the guard context) that no seam was touched.
    if ctx.dry_run:
        emit(
            ctx,
            RUNNER,
            [finding("api", "dry-run", RUNNER, "info", "dry_run: no prod calls made")],
            extra={"skipped": True, "spend_estimate_usd": 0},
        )
        return EXIT_OK

    findings = list(_security_probes(ctx))

    if not ctx.config.get("marker_gate_proven"):
        findings.append(
            finding(
                "marker",
                "marker-gate-unproven",
                RUNNER,
                "high",
                "marker gate not proven; skipping all chat conversations "
                "(run api_suite --prove-marker first, then set marker_gate_proven)",
            )
        )
        emit(ctx, RUNNER, findings, extra={"chat_skipped": True, "spend_estimate_usd": 0})
        return EXIT_OK

    per_prompt = float(ctx.config.get("per_prompt_usd", 0.02))
    cap = int(ctx.config.get("chat_prompts_per_day", 6))
    window_start = ctx.now_fn()
    breached = False
    turns_used = 0
    for convo in CONVERSATIONS:
        if turns_used + len(convo["turns"]) > cap:
            findings.append(
                finding(
                    "cost",
                    "prompt-cap-reached",
                    RUNNER,
                    "info",
                    "chat_prompts_per_day cap (%d) reached; remaining conversations skipped" % cap,
                )
            )
            break
        try:
            convo_findings, convo_breached, turns = _run_conversation(ctx, convo, window_start)
        except Exception as exc:  # noqa: BLE001
            # A raise from the network seams (sse_post/pg_rest_query raise by
            # design) must NOT become EXIT_CRASH - that would lose all findings
            # and skip emit() while real prod turns may already have landed.
            # Treat as a containment breach: emit + EXIT_BREACH.
            findings.append(
                finding(
                    "marker",
                    "conversation-error",
                    convo["name"],
                    "high",
                    "conversation %s raised (treated as breach): %s" % (convo["name"], exc),
                )
            )
            breached = True
            findings.append(
                finding(
                    "marker",
                    "run-aborted-on-breach",
                    RUNNER,
                    "high",
                    "conversation %s errored; aborting remaining conversations" % convo["name"],
                )
            )
            break
        findings.extend(convo_findings)
        turns_used += turns
        if convo_breached:
            breached = True
            findings.append(
                finding(
                    "marker",
                    "run-aborted-on-breach",
                    RUNNER,
                    "high",
                    "containment breach in %s; aborting remaining conversations" % convo["name"],
                )
            )
            break  # abort remaining conversations

    emit(
        ctx,
        RUNNER,
        findings,
        extra={
            "spend_estimate_usd": round(turns_used * per_prompt, 4),
            "turns_used": turns_used,
            "breach": breached,
        },
    )
    return EXIT_BREACH if breached else EXIT_OK


if __name__ == "__main__":
    sys.exit(main(RUNNER, run))
