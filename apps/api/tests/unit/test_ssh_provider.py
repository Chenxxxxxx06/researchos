import pytest

from researchos.common.errors import ValidationError
from researchos.runtime.ssh.provider import _validate_argv, remote_join


def test_remote_join_stays_below_configured_root() -> None:
    assert remote_join("/srv/research/project", ".") == "/srv/research/project"
    assert remote_join("/srv/research/project", "src/main.py") == (
        "/srv/research/project/src/main.py"
    )
    with pytest.raises(ValidationError):
        remote_join("/srv/research/project", "../other/secret.txt")
    with pytest.raises(ValidationError):
        remote_join("relative/root", "src/main.py")


def test_remote_terminal_keeps_local_allowlist() -> None:
    _validate_argv(["python", "train.py", "--epochs", "2"])
    _validate_argv(["git", "status", "--short"])
    with pytest.raises(ValidationError):
        _validate_argv(["bash", "-lc", "rm -rf /tmp/example"])
    with pytest.raises(ValidationError):
        _validate_argv(["git", "push"])
