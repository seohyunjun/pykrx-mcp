"""pykrx-mcp package.

Loads environment variables from a ``.env`` file as the very first thing on
import. This must happen before pykrx is imported anywhere, because pykrx
(>=1.2.8) reads ``KRX_ID`` / ``KRX_PW`` at import time to build its login
session. Importing any submodule (server, rest_api, tools) triggers this
package ``__init__`` first, so the credentials are in ``os.environ`` before
pykrx loads.
"""

import contextlib
import sys
from pathlib import Path

from dotenv import load_dotenv

from .__about__ import __version__


def _load_env() -> None:
    """Load a ``.env`` file into ``os.environ`` (existing vars take priority).

    Looks for ``.env`` at the repository root (two levels above this package),
    then falls back to walking up from the current working directory so the
    server works regardless of where it is launched from.
    """
    # Repo root: src/pykrx_mcp/__init__.py -> parents[2] == project root.
    repo_env = Path(__file__).resolve().parents[2] / ".env"
    if repo_env.is_file():
        load_dotenv(repo_env, override=False)

    # Also honor a .env found by walking up from the launch directory.
    load_dotenv(override=False)


def _import_pykrx_quietly() -> None:
    """Trigger pykrx's import-time KRX login with stdout sent to stderr.

    pykrx (>=1.2.8) prints login progress (``KRX 로그인 시도...`` etc.) to
    *stdout* when its session module is first imported. For the stdio MCP
    transport, stdout is the JSON-RPC protocol channel, so any stray bytes
    there corrupt the connection. We import the session module here, while
    redirecting stdout to stderr, so the protocol channel stays clean.
    Failures are non-fatal: pykrx itself swallows login errors (returns None).
    """
    with contextlib.redirect_stdout(sys.stderr):
        try:
            import pykrx.website.comm.webio  # noqa: F401  (import for side effect)
        except Exception:
            # Don't let an import/network hiccup break package import; the
            # tools will surface a clear error on first use instead.
            pass


_load_env()
_import_pykrx_quietly()

__all__ = ["__version__"]
