"""Golden-set evaluation for hybrid RAG retrieval (design §7.3).

Standalone script — not part of CI, no pytest. It talks to a *running* API
over real HTTP (CSRF included) and measures whether each golden question
surfaces its expected paper within the Top-3 / Top-5 hits.

Usage (stack running, demo seed loaded):

    uv run python scripts/golden_rag_eval.py

Configuration via environment variables:

    GOLDEN_BASE_URL   default http://localhost:8000
    GOLDEN_EMAIL      default demo@researchos.dev
    GOLDEN_PASSWORD   default demo-password-123
    GOLDEN_SET        path to the question set (default: golden_rag_set.json
                      next to this script)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

BASE_URL = os.environ.get("GOLDEN_BASE_URL", "http://localhost:8000")
EMAIL = os.environ.get("GOLDEN_EMAIL", "demo@researchos.dev")
PASSWORD = os.environ.get("GOLDEN_PASSWORD", "demo-password-123")
SET_PATH = Path(os.environ.get("GOLDEN_SET", Path(__file__).with_name("golden_rag_set.json")))


def _csrf(client: httpx.Client) -> dict[str, str]:
    token = client.cookies.get("ros_csrf")
    return {"X-CSRF-Token": token} if token else {}


def main() -> int:
    golden = json.loads(SET_PATH.read_text(encoding="utf-8"))
    queries = golden["queries"]

    with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
        login = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if login.status_code != 200:
            print(f"LOGIN FAILED: HTTP {login.status_code} {login.text[:200]}")
            return 1

        organizations = client.get("/organizations").json()
        if not organizations:
            print("NO ORGANIZATIONS for this account")
            return 1
        projects = client.get(
            "/projects", params={"organization_id": organizations[0]["id"]}
        ).json()["items"]
        project = next((p for p in projects if p["name"] == golden["project_name"]), None)
        if project is None:
            names = [p["name"] for p in projects]
            print(f"PROJECT {golden['project_name']!r} NOT FOUND; available: {names}")
            return 1
        project_id = project["id"]
        print(f"project: {golden['project_name']} ({project_id})")
        print(f"questions: {len(queries)}\n")

        top3 = top5 = kind_match = found = 0
        for entry in queries:
            resp = client.post(
                f"/projects/{project_id}/rag/search",
                json={"query": entry["question"], "limit": 8},
                headers=_csrf(client),
            )
            if resp.status_code != 200:
                print(f"{entry['id']}  HTTP {resp.status_code}: {resp.text[:160]}")
                continue
            body = resp.json()
            keyword = entry["expected_title_keyword"].lower()
            ranks = [
                index
                for index, hit in enumerate(body["hits"], start=1)
                if keyword in hit["title"].lower()
            ]
            rank = ranks[0] if ranks else None
            hit3 = rank is not None and rank <= 3
            hit5 = rank is not None and rank <= 5
            top3 += hit3
            top5 += hit5
            kind_ok = False
            if rank is not None:
                found += 1
                kind_ok = body["hits"][rank - 1]["kind"] == entry["expected_kind"]
                kind_match += kind_ok
            status = f"rank={rank}" if rank else "MISS"
            kinds = (
                f"kind={body['hits'][rank - 1]['kind']} expected={entry['expected_kind']}"
                if rank
                else f"expected={entry['expected_kind']}"
            )
            print(
                f"{entry['id']} [{entry['style']:<10}] {status:<8} {kinds}  "
                f"{entry['question'][:72]}"
            )

        total = len(queries)
        print(
            f"\nTop-3 hit rate: {top3}/{total} = {top3 / total:.1%}\n"
            f"Top-5 hit rate: {top5}/{total} = {top5 / total:.1%}\n"
            f"Kind accuracy on hits: {kind_match}/{found}"
            + (f" = {kind_match / found:.1%}" if found else "")
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
