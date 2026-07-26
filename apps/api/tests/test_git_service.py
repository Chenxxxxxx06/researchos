"""Git service tests: init, apply-commit trailers, log, diff, revert, disabled mode.

Repo-touching tests skip when the git binary is absent; the porcelain parser is
additionally unit-tested from literal strings so it is covered either way.
"""

from __future__ import annotations

import shutil
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.config import get_settings
from researchos.common.errors import NotFoundError, ValidationError
from researchos.common.paths import workspace_root_for
from researchos.git.provider import get_git_provider, parse_porcelain_status
from researchos.git.runner import GitDisabled, git_available, run_git
from researchos.git.service import GitService
from researchos.identity.service import AuthService
from researchos.projects.service import ProjectService
from researchos.workspace import fs

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git binary not installed")


@pytest.fixture(autouse=True)
def _fresh_git_cache():
    git_available.cache_clear()
    yield
    git_available.cache_clear()


async def _setup(db: AsyncSession, email: str):
    user, org = await AuthService(db).register(
        email=email, password="password123", display_name="Git User"
    )
    project = await ProjectService(db).create_project(
        user, organization_id=org.id, name="P", description=None, field=None
    )
    return user, project


# --- pure porcelain parsing (no git binary required) --------------------------
def test_parse_porcelain_states_and_branch() -> None:
    out = (
        "## main...origin/main [ahead 2, behind 1]\n"
        " M src/app.py\n"
        "A  src/new.py\n"
        " D old.txt\n"
        "R100 a.txt -> b.txt\n"
        "?? notes.md\n"
    )
    branch, ahead, behind, files = parse_porcelain_status(out)
    assert (branch, ahead, behind) == ("main", 2, 1)
    states = {f.path: f.state for f in files}
    assert states == {
        "src/app.py": "modified",
        "src/new.py": "added",
        "old.txt": "deleted",
        "b.txt": "renamed",
        "notes.md": "untracked",
    }


def test_parse_porcelain_no_commits_and_detached() -> None:
    branch, _, _, files = parse_porcelain_status("## No commits yet on main\n")
    assert branch == "main" and files == []
    branch, _, _, _ = parse_porcelain_status("## HEAD (no branch)\n")
    assert branch == "HEAD"


# --- real-git tests -----------------------------------------------------------
@needs_git
async def test_lazy_init_is_idempotent(db_session: AsyncSession) -> None:
    _user, project = await _setup(db_session, "git-init@example.com")
    svc = GitService(db_session)
    assert await svc.ensure_repo(project.id) is True
    assert await svc.ensure_repo(project.id) is True  # second call is a no-op

    root = workspace_root_for(project.id)
    head = run_git(root, "symbolic-ref", "--short", "HEAD").stdout.strip()
    assert head == "main"
    log = run_git(root, "log", "--format=%an <%ae> %s").stdout
    assert "ResearchOS <bot@researchos.local> researchos: initialize workspace" in log


@needs_git
async def test_commit_applied_patch_records_author_and_trailers(
    db_session: AsyncSession,
) -> None:
    user, project = await _setup(db_session, "git-commit@example.com")
    svc = GitService(db_session)
    fs.write_file(project.id, "src/app.py", "print('v1')\n")
    patch_id = uuid.uuid4()
    run_id = uuid.uuid4()

    sha = await svc.commit_applied_patch(
        project.id,
        summary="Add app entrypoint\n\nlong body",
        patch_id=patch_id,
        agent_run_id=run_id,
        author_name=user.display_name,
        author_email=user.email,
        paths=["src/app.py"],
    )
    assert sha is not None

    entries = await svc.log(user, project.id)
    assert entries[0].sha == sha
    assert entries[0].summary == "Add app entrypoint"
    assert entries[0].author_name == user.display_name
    assert entries[0].author_email == user.email
    assert entries[0].patch_id == patch_id
    assert entries[0].agent_run_id == run_id
    assert entries[0].reverts_sha is None

    raw = run_git(workspace_root_for(project.id), "log", "-1", "--format=%B").stdout
    assert f"Patch: {patch_id}" in raw
    assert f"Agent-Run: {run_id}" in raw
    assert "Co-Authored-By: codex <noreply@anthropic.com>" in raw


@needs_git
async def test_log_per_file_filter_and_skip(db_session: AsyncSession) -> None:
    user, project = await _setup(db_session, "git-log@example.com")
    svc = GitService(db_session)
    for name in ("a.txt", "b.txt"):
        fs.write_file(project.id, name, f"{name}\n")
        await svc.commit_applied_patch(
            project.id,
            summary=f"add {name}",
            patch_id=uuid.uuid4(),
            agent_run_id=None,
            author_name="Dev",
            author_email="dev@example.com",
            paths=[name],
        )

    all_entries = await svc.log(user, project.id)
    assert [e.summary for e in all_entries[:2]] == ["add b.txt", "add a.txt"]
    assert all_entries[0].agent_run_id is None  # "-" trailer parses to None

    only_a = await svc.log(user, project.id, path="a.txt")
    assert [e.summary for e in only_a] == ["add a.txt"]

    skipped = await svc.log(user, project.id, limit=1, skip=1)
    assert [e.summary for e in skipped] == ["add a.txt"]


@needs_git
async def test_commit_diff_contents_and_edges(db_session: AsyncSession) -> None:
    user, project = await _setup(db_session, "git-diff@example.com")
    svc = GitService(db_session)

    fs.write_file(project.id, "f.txt", "one\n")
    await svc.commit_applied_patch(
        project.id, summary="create f", patch_id=uuid.uuid4(), agent_run_id=None,
        author_name="Dev", author_email="dev@example.com", paths=["f.txt"],
    )
    fs.write_file(project.id, "f.txt", "two\n")
    await svc.commit_applied_patch(
        project.id, summary="modify f", patch_id=uuid.uuid4(), agent_run_id=None,
        author_name="Dev", author_email="dev@example.com", paths=["f.txt"],
    )
    fs.delete_file(project.id, "f.txt")
    await svc.commit_applied_patch(
        project.id, summary="delete f", patch_id=uuid.uuid4(), agent_run_id=None,
        author_name="Dev", author_email="dev@example.com", paths=["f.txt"],
    )

    entries = await svc.log(user, project.id)
    delete_sha, modify_sha, create_sha = entries[0].sha, entries[1].sha, entries[2].sha

    diff = await svc.commit_diff(user, project.id, create_sha)
    f = diff.files[0]
    assert (f.change_type, f.old_content, f.new_content) == ("added", None, "one\n")

    diff = await svc.commit_diff(user, project.id, modify_sha)
    f = diff.files[0]
    assert (f.change_type, f.old_content, f.new_content) == ("modified", "one\n", "two\n")
    assert f.omitted is False and f.size == 4

    diff = await svc.commit_diff(user, project.id, delete_sha)
    f = diff.files[0]
    assert (f.change_type, f.old_content, f.new_content) == ("deleted", "two\n", None)

    # Root (init) commit has a parent-less diff with no files.
    root_sha = entries[-1].sha
    diff = await svc.commit_diff(user, project.id, root_sha)
    assert diff.files == []

    with pytest.raises(NotFoundError):
        await svc.commit_diff(user, project.id, "deadbeef" * 5)
    with pytest.raises(ValidationError):
        await svc.commit_diff(user, project.id, "NOT-A-SHA")


@needs_git
async def test_revert_happy_path_dirty_tree_and_conflict(db_session: AsyncSession) -> None:
    user, project = await _setup(db_session, "git-revert@example.com")
    svc = GitService(db_session)

    fs.write_file(project.id, "r.txt", "one\n")
    await svc.commit_applied_patch(
        project.id, summary="v1", patch_id=uuid.uuid4(), agent_run_id=None,
        author_name="Dev", author_email="dev@example.com", paths=["r.txt"],
    )
    fs.write_file(project.id, "r.txt", "two\n")
    await svc.commit_applied_patch(
        project.id, summary="v2", patch_id=uuid.uuid4(), agent_run_id=None,
        author_name="Dev", author_email="dev@example.com", paths=["r.txt"],
    )
    entries = await svc.log(user, project.id)
    v2_sha = entries[0].sha

    result = await svc.revert(user, project.id, v2_sha)
    assert result.reverted_sha == v2_sha
    root = workspace_root_for(project.id)
    assert (root / "r.txt").read_text(encoding="utf-8") == "one\n"
    entries = await svc.log(user, project.id)
    assert entries[0].sha == result.commit_sha
    assert entries[0].summary == 'Revert "v2"'
    assert entries[0].reverts_sha == v2_sha
    assert entries[0].author_name == user.display_name

    # Dirty tree is rejected before any git mutation.
    fs.write_file(project.id, "r.txt", "uncommitted\n")
    with pytest.raises(ValidationError):
        await svc.revert(user, project.id, v2_sha)
    fs.write_file(project.id, "r.txt", "one\n")  # restore clean state

    # Conflicting revert aborts cleanly and reports the git error.
    fs.write_file(project.id, "r.txt", "three\n")
    await svc.commit_applied_patch(
        project.id, summary="v3", patch_id=uuid.uuid4(), agent_run_id=None,
        author_name="Dev", author_email="dev@example.com", paths=["r.txt"],
    )
    v1_change_sha = (await svc.log(user, project.id, path="r.txt"))[-1].sha
    with pytest.raises(ValidationError):
        await svc.revert(user, project.id, v1_change_sha)
    status = run_git(root, "status", "--porcelain").stdout.strip()
    assert status == ""  # abort left the tree clean


@needs_git
async def test_real_status_provider(db_session: AsyncSession) -> None:
    user, project = await _setup(db_session, "git-status@example.com")
    svc = GitService(db_session)

    # No repo yet: pristine, side-effect free.
    status = await svc.status(user, project.id)
    assert (status.provider, status.branch, status.clean) == ("git", "main", True)
    assert not (workspace_root_for(project.id) / ".git").exists()

    await svc.ensure_repo(project.id)
    fs.write_file(project.id, "new.txt", "x\n")
    status = await svc.status(user, project.id)
    assert status.provider == "git"
    assert status.clean is False
    assert {f.path: f.state for f in status.files} == {"new.txt": "untracked"}


async def test_disabled_mode_degradation(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, project = await _setup(db_session, "git-off@example.com")
    monkeypatch.setattr(get_settings(), "git_enabled", False)
    git_available.cache_clear()

    svc = GitService(db_session)
    assert get_git_provider().name == "disabled"
    status = await svc.status(user, project.id)
    assert (status.provider, status.branch, status.clean, status.files) == (
        "disabled",
        "",
        True,
        [],
    )
    assert await svc.log(user, project.id) == []
    with pytest.raises(GitDisabled):
        await svc.revert(user, project.id, "a" * 40)
    with pytest.raises(GitDisabled):
        await svc.commit_diff(user, project.id, "a" * 40)
    assert await svc.ensure_repo(project.id) is False
    assert (
        await svc.commit_applied_patch(
            project.id,
            summary="s",
            patch_id=uuid.uuid4(),
            agent_run_id=None,
            author_name="Dev",
            author_email="dev@example.com",
            paths=[],
        )
        is None
    )
