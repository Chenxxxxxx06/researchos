"""SSH profile persistence and secret-boundary tests."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.runtime.ssh.models import SSHExecution, SSHProfile

from .helpers import csrf_headers, register


async def test_ssh_profile_credentials_are_encrypted_and_never_returned(
    client, db_session: AsyncSession
) -> None:
    await register(client, email="ssh-profile@example.com")
    org_id = (await client.get("/organizations")).json()[0]["id"]
    project = await client.post(
        "/projects",
        json={"organization_id": org_id, "name": "Remote project"},
        headers=csrf_headers(client),
    )
    project_id = project.json()["id"]
    password = "temporary-test-password"
    saved = await client.put(
        f"/projects/{project_id}/workspace/ssh/profiles",
        json={
            "name": "lab-gpu",
            "host": "gpu.example.edu",
            "port": 22,
            "username": "researcher",
            "auth_type": "password",
            "secret": password,
            "known_hosts": ("gpu.example.edu ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestOnly"),
            "default_workdir": "/srv/research/project",
        },
        headers=csrf_headers(client),
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["credential_masked"] == "••••••••"
    assert password not in saved.text

    row = await db_session.get(SSHProfile, uuid.UUID(body["id"]))
    assert row is not None
    assert row.encrypted_credentials.startswith("enc:v1:")
    assert password not in row.encrypted_credentials

    listed = await client.get(f"/projects/{project_id}/workspace/ssh/profiles")
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "lab-gpu"
    assert password not in listed.text

    deleted = await client.delete(
        f"/projects/{project_id}/workspace/ssh/profiles/{body['id']}",
        headers=csrf_headers(client),
    )
    assert deleted.status_code == 204


async def test_ssh_profile_with_execution_history_cannot_be_deleted(
    client, db_session: AsyncSession
) -> None:
    user = await register(client, email="ssh-audit@example.com")
    org_id = (await client.get("/organizations")).json()[0]["id"]
    project = await client.post(
        "/projects",
        json={"organization_id": org_id, "name": "Audited remote"},
        headers=csrf_headers(client),
    )
    project_id = project.json()["id"]
    saved = await client.put(
        f"/projects/{project_id}/workspace/ssh/profiles",
        json={
            "name": "audit-host",
            "host": "gpu.example.edu",
            "port": 22,
            "username": "researcher",
            "auth_type": "password",
            "secret": "temporary-test-password",
            "known_hosts": "gpu.example.edu ssh-ed25519 AAAATestOnly",
            "default_workdir": "/srv/research/project",
        },
        headers=csrf_headers(client),
    )
    profile_id = uuid.UUID(saved.json()["id"])
    db_session.add(
        SSHExecution(
            project_id=uuid.UUID(project_id),
            profile_id=profile_id,
            user_id=uuid.UUID(user["user"]["id"]),
            argv_json=["python", "train.py"],
            workdir="/srv/research/project",
            status="completed",
            duration_ms=12,
            exit_code=0,
        )
    )
    await db_session.commit()

    deleted = await client.delete(
        f"/projects/{project_id}/workspace/ssh/profiles/{profile_id}",
        headers=csrf_headers(client),
    )
    assert deleted.status_code == 409
    assert deleted.json()["error"]["code"] == "ssh_profile_has_executions"
    assert deleted.json()["error"]["details"]["execution_count"] == 1
