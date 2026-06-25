"""KRX authenticated-session helpers.

pykrx (>=1.2.8) keeps a single global login session (``KRX_ID`` / ``KRX_PW``)
and considers it valid for one hour based on a *client-side* timer. KRX,
however, may invalidate the session *server-side* before that hour is up
(e.g. during its early-morning maintenance/batch window). When that happens
the client still believes the session is valid, so it never auto-refreshes,
and the data endpoint replies with the 6-byte body ``LOGOUT`` (HTTP 400) —
which surfaces as an ``HTTPError`` or a ``JSONDecodeError`` ("Expecting
value...") depending on the code path.

This module detects that condition at request time, forces a fresh re-login,
and retries the call once. Endpoints that need authentication (e.g. the gold
market, ``MDCSTAT15001``) should route their ``fetch`` through
:func:`fetch_with_relogin`.
"""

import logging
from collections.abc import Callable
from typing import TypeVar

from pykrx.website.comm import auth

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Markers that identify a rejected/expired KRX session rather than a genuine
# domain error. The ``LOGOUT`` body yields either an HTTPError ("400 Client
# Error: Bad Request") or a JSONDecodeError ("Expecting value: line 1 ...")
# when the empty/non-JSON body is parsed.
_SESSION_ERROR_MARKERS = (
    "logout",
    "expecting value",
    "400 client error",
    "bad request",
)


def _is_session_error(exc: Exception) -> bool:
    """Return True if ``exc`` looks like an expired/rejected KRX session."""
    msg = str(exc).lower()
    return any(marker in msg for marker in _SESSION_ERROR_MARKERS)


def force_relogin() -> bool:
    """Invalidate the cached KRX session and trigger a fresh login.

    Marks the global ``KRXSession`` as expired so that the next
    ``get_auth_session()`` call re-authenticates with the configured
    ``KRX_ID`` / ``KRX_PW`` credentials.

    Returns:
        True if a valid authenticated session is available afterwards.
    """
    session = getattr(auth, "_auth_session", None)
    if session is not None:
        # Make is_valid() return False so get_auth_session() re-logs in.
        session.is_authenticated = False
        session.expiry_time = 0.0

    refreshed = auth.get_auth_session()
    ok = refreshed is not None and getattr(refreshed, "is_authenticated", False)
    if ok:
        logger.info("KRX session re-login succeeded")
    else:
        logger.warning(
            "KRX session re-login failed (check KRX_ID/KRX_PW or KRX availability)"
        )
    return ok


def _session_is_authenticated() -> bool:
    """Return True if pykrx currently believes it holds a valid KRX session.

    pykrx's high-level ``stock.get_*`` helpers auto-login on the first call,
    so after a successful fetch the global session is authenticated. A
    server-side expiry (the case this module guards against) leaves the
    *client* still marked authenticated while data calls come back empty.
    """
    session = getattr(auth, "_auth_session", None)
    return session is not None and getattr(session, "is_authenticated", False)


def _is_empty_result(result: object) -> bool:
    """Return True if ``result`` is an empty DataFrame/list/None."""
    if result is None:
        return True
    empty = getattr(result, "empty", None)
    if empty is not None:  # pandas DataFrame / Series
        return bool(empty)
    try:
        return len(result) == 0  # type: ignore[arg-type]
    except TypeError:
        return False


def fetch_with_relogin_on_empty(fetch: Callable[..., T], *args, **kwargs) -> T:
    """Run a *high-level* pykrx call, re-logging in and retrying once on empty.

    pykrx's ``stock.get_*`` helpers swallow the ``JSONDecodeError`` raised by an
    expired/rejected KRX session internally and return an **empty DataFrame**
    instead of raising. :func:`fetch_with_relogin` (which keys off exceptions)
    therefore can't recover those calls. This variant treats an empty result
    from an otherwise-authenticated session as a likely server-side session
    expiry, forces a fresh login, and retries once.

    When the session is *not* authenticated (e.g. missing ``KRX_ID``/``KRX_PW``)
    an empty result is taken at face value — no retry — to avoid a re-login
    storm on a genuine credential/no-data condition.

    Args:
        fetch: A high-level pykrx callable (e.g. ``stock.get_shorting_*``).
        *args, **kwargs: Forwarded to ``fetch``.

    Returns:
        Whatever ``fetch`` returns (after one retry if the first result was
        empty and a re-login was warranted).
    """
    result = fetch(*args, **kwargs)
    if _is_empty_result(result) and _session_is_authenticated():
        logger.warning(
            "Empty KRX result with an authenticated session; "
            "forcing re-login and retrying once"
        )
        if force_relogin():
            result = fetch(*args, **kwargs)
    return result


def fetch_with_relogin(fetch: Callable[..., T], *args, **kwargs) -> T:
    """Run a pykrx fetch, re-logging in and retrying once on a session timeout.

    Args:
        fetch: A pykrx ``.fetch`` callable (or any callable hitting an
            auth-protected KRX endpoint).
        *args, **kwargs: Forwarded to ``fetch``.

    Returns:
        Whatever ``fetch`` returns.

    Raises:
        The original exception if it is not a session error, or if the call
        still fails after a forced re-login.
    """
    try:
        return fetch(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - re-raised below if not recoverable
        if not _is_session_error(exc):
            raise
        logger.warning(
            "KRX session appears expired (%s: %s); forcing re-login and retrying",
            type(exc).__name__,
            str(exc)[:80],
        )
        force_relogin()
        return fetch(*args, **kwargs)
