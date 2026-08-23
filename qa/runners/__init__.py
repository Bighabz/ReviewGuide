"""QA loop runners (Increment 2+).

Each runner is independently runnable for debugging:
    cd qa && python -m runners.<name> --run-id R --artifacts-dir DIR

Exit codes are the supervised entrypoint's contract:
    0  completed (with or without findings)
    2  crashed (unexpected exception)
    3  CONTAINMENT BREACH (abort remaining prod runners + HIGH alert)
"""
