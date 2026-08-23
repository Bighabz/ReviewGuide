-- qa.observations - IMMUTABLE per-run findings (build spec Increment 2).
--
-- Review-only file: it is NEVER executed by qa code or tests. Apply it by
-- hand through the Supabase management API (browser User-Agent required -
-- memory supabase-mgmt-api-cloudflare-ua) after human review.
--
-- Rationale (dual-verify, both reviewers): qa.findings unique(fingerprint)
-- would OVERWRITE prior-run observations and destroy the history P2 needs.
-- Observations are keyed (run_id, fingerprint) so every run's view of a
-- finding is preserved; runner_version lets a runner bump reset P2's
-- baseline instead of poisoning it. Lifecycle (NEW/OPEN/FIXED/REGRESSED)
-- is derived in P2 from this history, not stored here.

CREATE SCHEMA IF NOT EXISTS qa;

CREATE TABLE IF NOT EXISTS qa.observations (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id         text        NOT NULL,
    fingerprint    text        NOT NULL,
    dimension      text        NOT NULL,
    severity       text        NOT NULL,
    summary        text        NOT NULL,
    locus          text,
    status         text        NOT NULL,
    runner_version text        NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, fingerprint)
);

CREATE INDEX IF NOT EXISTS observations_fingerprint_idx
    ON qa.observations (fingerprint);
CREATE INDEX IF NOT EXISTS observations_run_id_idx
    ON qa.observations (run_id);

-- Service-role only: RLS on, no policies (matches qa.runs/findings/heartbeats).
ALTER TABLE qa.observations ENABLE ROW LEVEL SECURITY;
