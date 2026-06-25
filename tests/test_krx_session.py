"""Tests for KRX session relogin/retry helpers."""

import json
from unittest.mock import patch

import pytest

import pandas as pd

from pykrx_mcp.utils.krx_session import (
    _is_session_error,
    fetch_with_relogin,
    fetch_with_relogin_on_empty,
    force_relogin,
)


class TestIsSessionError:
    """Classification of recoverable session errors vs. genuine errors."""

    @pytest.mark.parametrize(
        "exc",
        [
            RuntimeError("LOGOUT"),
            json.JSONDecodeError("Expecting value", "", 0),
            Exception("400 Client Error: Bad Request for url: ..."),
            Exception("Bad Request"),
        ],
    )
    def test_recoverable(self, exc):
        assert _is_session_error(exc) is True

    @pytest.mark.parametrize(
        "exc",
        [
            ValueError("invalid date format"),
            KeyError("종가"),
            Exception("500 Server Error"),
        ],
    )
    def test_not_recoverable(self, exc):
        assert _is_session_error(exc) is False


class TestFetchWithRelogin:
    """Retry-once-after-relogin behavior."""

    def test_success_no_relogin(self):
        """A successful fetch returns immediately without re-login."""
        with patch("pykrx_mcp.utils.krx_session.force_relogin") as mock_relogin:
            result = fetch_with_relogin(lambda **kw: kw["v"], v=42)
        assert result == 42
        mock_relogin.assert_not_called()

    def test_session_error_triggers_relogin_and_retry(self):
        """A session error forces a re-login and retries once (success)."""
        calls = {"n": 0}

        def fetch(**_kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise json.JSONDecodeError("Expecting value", "", 0)
            return "recovered"

        with patch("pykrx_mcp.utils.krx_session.force_relogin") as mock_relogin:
            result = fetch_with_relogin(fetch)

        assert result == "recovered"
        assert calls["n"] == 2
        mock_relogin.assert_called_once()

    def test_non_session_error_propagates_without_relogin(self):
        """A genuine error is re-raised and does not trigger a re-login."""

        def fetch(**_kwargs):
            raise ValueError("invalid date format")

        with patch("pykrx_mcp.utils.krx_session.force_relogin") as mock_relogin:
            with pytest.raises(ValueError, match="invalid date format"):
                fetch_with_relogin(fetch)
        mock_relogin.assert_not_called()

    def test_persistent_session_error_raises_after_one_retry(self):
        """If it still fails after re-login, the error propagates."""

        def fetch(**_kwargs):
            raise RuntimeError("LOGOUT")

        with patch("pykrx_mcp.utils.krx_session.force_relogin") as mock_relogin:
            with pytest.raises(RuntimeError, match="LOGOUT"):
                fetch_with_relogin(fetch)
        mock_relogin.assert_called_once()


class TestFetchWithReloginOnEmpty:
    """Empty-result-after-relogin behavior for high-level pykrx calls."""

    def test_non_empty_result_returns_without_relogin(self):
        df = pd.DataFrame({"거래량": [1, 2]})
        with patch("pykrx_mcp.utils.krx_session.force_relogin") as mock_relogin:
            with patch(
                "pykrx_mcp.utils.krx_session._session_is_authenticated",
                return_value=True,
            ):
                result = fetch_with_relogin_on_empty(lambda: df)
        assert result is df
        mock_relogin.assert_not_called()

    def test_empty_with_auth_session_relogins_and_retries(self):
        calls = {"n": 0}

        def fetch():
            calls["n"] += 1
            return pd.DataFrame() if calls["n"] == 1 else pd.DataFrame({"x": [1]})

        with patch(
            "pykrx_mcp.utils.krx_session.force_relogin", return_value=True
        ) as mock_relogin:
            with patch(
                "pykrx_mcp.utils.krx_session._session_is_authenticated",
                return_value=True,
            ):
                result = fetch_with_relogin_on_empty(fetch)

        assert not result.empty
        assert calls["n"] == 2
        mock_relogin.assert_called_once()

    def test_empty_without_auth_session_does_not_retry(self):
        """Missing credentials/no-data must not trigger a re-login storm."""
        calls = {"n": 0}

        def fetch():
            calls["n"] += 1
            return pd.DataFrame()

        with patch("pykrx_mcp.utils.krx_session.force_relogin") as mock_relogin:
            with patch(
                "pykrx_mcp.utils.krx_session._session_is_authenticated",
                return_value=False,
            ):
                result = fetch_with_relogin_on_empty(fetch)

        assert result.empty
        assert calls["n"] == 1
        mock_relogin.assert_not_called()

    def test_empty_after_relogin_returns_empty(self):
        """A genuinely empty dataset stays empty after one retry."""
        with patch("pykrx_mcp.utils.krx_session.force_relogin", return_value=True):
            with patch(
                "pykrx_mcp.utils.krx_session._session_is_authenticated",
                return_value=True,
            ):
                result = fetch_with_relogin_on_empty(lambda: pd.DataFrame())
        assert result.empty


class TestForceRelogin:
    """force_relogin invalidates the cached session and re-authenticates."""

    def test_invalidates_and_refreshes(self):
        class FakeSession:
            is_authenticated = True
            expiry_time = 9_999_999_999.0

        fake = FakeSession()

        def fake_get_auth_session():
            # Mimic pykrx: re-login produces an authenticated session.
            fake.is_authenticated = True
            return fake

        with patch("pykrx_mcp.utils.krx_session.auth") as mock_auth:
            mock_auth._auth_session = fake
            mock_auth.get_auth_session.side_effect = fake_get_auth_session
            ok = force_relogin()

        # expiry was zeroed to force is_valid() False before refresh
        assert fake.expiry_time == 0.0
        assert ok is True
        mock_auth.get_auth_session.assert_called_once()

    def test_returns_false_when_login_unavailable(self):
        with patch("pykrx_mcp.utils.krx_session.auth") as mock_auth:
            mock_auth._auth_session = None
            mock_auth.get_auth_session.return_value = None
            assert force_relogin() is False
