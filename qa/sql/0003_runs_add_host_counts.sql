-- qa.runs predated the store adapter and lacked host + counts (store.py
-- start_run/finish_run write both). Add them; the P2 columns
-- (dimensions_ok, new_count, ...) stay for later lifecycle work.
-- Review-only file: apply by hand via the management API.
ALTER TABLE qa.runs ADD COLUMN IF NOT EXISTS host   text;
ALTER TABLE qa.runs ADD COLUMN IF NOT EXISTS counts jsonb;
