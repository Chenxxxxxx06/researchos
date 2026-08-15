"""Online tests against the real Aliyun Bailian (DashScope) embedding API.

These tests perform REAL network calls and are skipped unless explicitly
enabled:

    RUN_ONLINE_TESTS=1 uv run pytest tests/online -q

Requirements: ``RUN_ONLINE_TESTS=1`` in the environment and a DashScope key
readable from ``DASHSCOPE_API_KEY`` or ``apps/api/.env``. CI never sets the
flag, so the whole package skips there; the offline suite stays the gate.
"""
