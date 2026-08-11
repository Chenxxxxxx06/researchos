"""Public SSH runtime interface.

The implementation lives in :mod:`provider` and is intentionally split from
the authorization/persistence layer in :mod:`service`. All connections require
OpenSSH known_hosts material; credentials are decrypted only for the duration
of a connection.
"""

from .provider import build_tree, read_file, run_command, test_connection, write_file

__all__ = ["build_tree", "read_file", "run_command", "test_connection", "write_file"]
