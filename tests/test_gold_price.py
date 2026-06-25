"""Tests for gold price tools."""

from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from pykrx_mcp.tools.gold_price import (
    get_gold_price_by_date,
    get_gold_price_change,
    get_latest_gold_price,
    get_recent_gold_price,
)


class TestGetGoldPriceByDate:
    """Test gold price history retrieval."""

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    def test_valid_request(self, mock_gold):
        """Should return gold price data for valid request."""
        mock_df = pd.DataFrame(
            {
                "날짜": ["2024-01-01", "2024-01-02"],
                "시가": [2650000, 2660000],
                "고가": [2680000, 2690000],
                "저가": [2640000, 2650000],
                "종가": [2670000, 2680000],
                "거래량": [1000, 1200],
                "거래대금": [2670000000, 3216000000],
            }
        )
        mock_instance = mock_gold.return_value
        mock_instance.fetch.return_value = mock_df

        result = get_gold_price_by_date("20240101", "20240102")

        mock_instance.fetch.assert_called_once_with(
            isuCd="KRD040200002",
            strtDd="20240101",
            endDd="20240102",
        )
        assert result["isu_code"] == "KRD040200002"
        assert result["start_date"] == "20240101"
        assert result["end_date"] == "20240102"
        assert result["row_count"] == 2
        assert len(result["data"]) == 2

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    def test_empty_dataframe(self, mock_gold):
        """Should handle empty DataFrame."""
        mock_instance = mock_gold.return_value
        mock_instance.fetch.return_value = pd.DataFrame()

        result = get_gold_price_by_date("20240101", "20240102")

        assert "error" in result
        assert "No data found" in result["error"]

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    def test_invalid_start_date(self, mock_gold):
        """Should reject invalid start date format."""
        result = get_gold_price_by_date("2024-01-01", "20240102")

        mock_gold.return_value.fetch.assert_not_called()
        assert "error" in result
        assert "YYYYMMDD" in result["error"]

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    def test_invalid_end_date(self, mock_gold):
        """Should reject invalid end date format."""
        result = get_gold_price_by_date("20240101", "2024-01-02")

        mock_gold.return_value.fetch.assert_not_called()
        assert "error" in result
        assert "YYYYMMDD" in result["error"]

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    def test_custom_isu_code(self, mock_gold):
        """Should use custom isu_code."""
        mock_instance = mock_gold.return_value
        mock_instance.fetch.return_value = pd.DataFrame(
            {
                "날짜": ["2024-01-01"],
                "시가": [2650000],
                "고가": [2680000],
                "저가": [2640000],
                "종가": [2670000],
                "거래량": [1000],
                "거래대금": [2670000000],
            }
        )

        result = get_gold_price_by_date("20240101", "20240101", "KRD040200003")

        mock_instance.fetch.assert_called_once_with(
            isuCd="KRD040200003",
            strtDd="20240101",
            endDd="20240101",
        )
        assert result["isu_code"] == "KRD040200003"


class TestGetLatestGoldPrice:
    """Test latest gold price retrieval."""

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    @patch("pykrx_mcp.tools.gold_price.datetime")
    def test_valid_request(self, mock_datetime, mock_gold):
        """Should return latest gold price for valid request."""
        mock_today = datetime(2024, 1, 15)
        mock_datetime.now.return_value = mock_today
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs) if args else mock_today

        mock_df = pd.DataFrame(
            {
                "날짜": ["2024-01-15"],
                "시가": [2700000],
                "고가": [2720000],
                "저가": [2690000],
                "종가": [2710000],
                "거래량": [1500],
                "거래대금": [4065000000],
            }
        )
        mock_instance = mock_gold.return_value
        mock_instance.fetch.return_value = mock_df

        result = get_latest_gold_price()

        assert "error" not in result
        assert result["isu_code"] == "KRD040200002"
        assert result["close"] == 2710000
        assert result["high"] == 2720000
        assert result["low"] == 2690000
        assert result["open"] == 2700000
        assert result["volume"] == 1500
        assert result["trading_value"] == 4065000000

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    @patch("pykrx_mcp.tools.gold_price.datetime")
    def test_no_data_today_fallback_to_yesterday(self, mock_datetime, mock_gold):
        """Should fallback to yesterday if no data today."""
        mock_today = datetime(2024, 1, 15)
        mock_datetime.now.return_value = mock_today
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs) if args else mock_today

        # First call (today) returns empty, second call (yesterday) returns data
        empty_df = pd.DataFrame()
        data_df = pd.DataFrame(
            {
                "날짜": ["2024-01-14"],
                "시가": [2690000],
                "고가": [2710000],
                "저가": [2680000],
                "종가": [2700000],
                "거래량": [1400],
                "거래대금": [3780000000],
            }
        )

        mock_instance = mock_gold.return_value
        mock_instance.fetch.side_effect = [empty_df, data_df]

        result = get_latest_gold_price()

        assert "error" not in result
        assert result["close"] == 2700000
        assert mock_instance.fetch.call_count == 2

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    @patch("pykrx_mcp.tools.gold_price.datetime")
    def test_empty_data_both_days(self, mock_datetime, mock_gold):
        """Should return error if no data for both today and yesterday."""
        mock_today = datetime(2024, 1, 15)
        mock_datetime.now.return_value = mock_today
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs) if args else mock_today

        mock_instance = mock_gold.return_value
        mock_instance.fetch.side_effect = [pd.DataFrame(), pd.DataFrame()]

        result = get_latest_gold_price()

        assert "error" in result
        assert "No data found" in result["error"]

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    def test_invalid_isu_code(self, mock_gold):
        """Should reject empty isu_code."""
        result = get_latest_gold_price("")

        mock_gold.return_value.fetch.assert_not_called()
        assert "error" in result
        assert "isu_code is required" in result["error"]


class TestGetGoldPriceChange:
    """Test gold price change analysis."""

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    def test_valid_request(self, mock_gold):
        """Should return price change analysis for valid request."""
        mock_df = pd.DataFrame(
            {
                "날짜": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "시가": [2650000, 2660000, 2670000],
                "고가": [2680000, 2690000, 2700000],
                "저가": [2640000, 2650000, 2660000],
                "종가": [2670000, 2680000, 2690000],
                "거래량": [1000, 1200, 1100],
                "거래대금": [2670000000, 3216000000, 2959000000],
            }
        )
        mock_instance = mock_gold.return_value
        mock_instance.fetch.return_value = mock_df

        result = get_gold_price_change("20240101", "20240103")

        mock_instance.fetch.assert_called_once_with(
            isuCd="KRD040200002",
            strtDd="20240101",
            endDd="20240103",
        )
        assert result["start_price"] == 2670000
        assert result["end_price"] == 2690000
        assert result["absolute_change"] == 20000
        assert result["percentage_change"] == pytest.approx(0.75, rel=1e-2)
        assert result["period_high"] == 2700000
        assert result["period_low"] == 2640000
        assert result["trading_days"] == 3

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    def test_empty_dataframe(self, mock_gold):
        """Should handle empty DataFrame."""
        mock_instance = mock_gold.return_value
        mock_instance.fetch.return_value = pd.DataFrame()

        result = get_gold_price_change("20240101", "20240102")

        assert "error" in result
        assert "No data found" in result["error"]

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    def test_invalid_date_format(self, mock_gold):
        """Should reject invalid date format."""
        result = get_gold_price_change("2024-01-01", "20240102")

        mock_gold.return_value.fetch.assert_not_called()
        assert "error" in result
        assert "YYYYMMDD" in result["error"]


class TestGetRecentGoldPrice:
    """Test recent gold price retrieval and analysis."""

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    def test_valid_request(self, mock_gold):
        """Should return daily data plus analysis for valid request."""
        mock_df = pd.DataFrame(
            {
                "날짜": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "시가": [2650000, 2660000, 2670000],
                "고가": [2680000, 2690000, 2700000],
                "저가": [2640000, 2650000, 2660000],
                "종가": [2670000, 2680000, 2690000],
                "거래량": [1000, 1200, 1100],
                "거래대금": [2670000000, 3216000000, 2959000000],
            }
        )
        mock_instance = mock_gold.return_value
        mock_instance.fetch.return_value = mock_df

        result = get_recent_gold_price(30)

        assert "error" not in result
        assert result["requested_days"] == 30
        assert result["trading_days"] == 3
        assert result["row_count"] == 3
        assert len(result["data"]) == 3

        analysis = result["analysis"]
        assert analysis["start_price"] == 2670000
        assert analysis["end_price"] == 2690000
        assert analysis["absolute_change"] == 20000
        assert analysis["percentage_change"] == pytest.approx(0.7491, rel=1e-2)
        assert analysis["period_high"] == 2700000
        assert analysis["period_low"] == 2640000

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    def test_handles_string_formatted_numbers(self, mock_gold):
        """Should coerce comma-formatted string values from KRX."""
        mock_df = pd.DataFrame(
            {
                "날짜": ["2024-01-01", "2024-01-02"],
                "시가": ["2,650,000", "2,660,000"],
                "고가": ["2,680,000", "2,690,000"],
                "저가": ["2,640,000", "2,650,000"],
                "종가": ["2,670,000", "2,680,000"],
                "거래량": ["1,000", "1,200"],
                "거래대금": ["2,670,000,000", "3,216,000,000"],
            }
        )
        mock_instance = mock_gold.return_value
        mock_instance.fetch.return_value = mock_df

        result = get_recent_gold_price(7)

        assert "error" not in result
        assert result["analysis"]["start_price"] == 2670000
        assert result["analysis"]["end_price"] == 2680000

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    def test_empty_dataframe(self, mock_gold):
        """Should handle empty DataFrame."""
        mock_instance = mock_gold.return_value
        mock_instance.fetch.return_value = pd.DataFrame()

        result = get_recent_gold_price(30)

        assert "error" in result
        assert "No data found" in result["error"]

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    def test_invalid_days(self, mock_gold):
        """Should reject non-positive days."""
        result = get_recent_gold_price(0)

        mock_gold.return_value.fetch.assert_not_called()
        assert "error" in result
        assert "positive integer" in result["error"]

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    def test_invalid_isu_code(self, mock_gold):
        """Should reject empty isu_code."""
        result = get_recent_gold_price(30, "")

        mock_gold.return_value.fetch.assert_not_called()
        assert "error" in result
        assert "isu_code is required" in result["error"]

    @patch("pykrx_mcp.tools.gold_price.개별종목_시세_추이")
    def test_normalizes_raw_krx_columns(self, mock_gold):
        """Should map raw KRX column codes and include 거래량/거래대금."""
        # Mimics the real KRX MDCSTAT15001 payload: raw code columns with
        # comma-formatted string values.
        mock_df = pd.DataFrame(
            {
                "TRD_DD": ["2024/01/01", "2024/01/02"],
                "TDD_CLSPRC": ["2,670,000", "2,680,000"],
                "TDD_OPNPRC": ["2,650,000", "2,660,000"],
                "TDD_HGPRC": ["2,680,000", "2,690,000"],
                "TDD_LWPRC": ["2,640,000", "2,650,000"],
                "ACC_TRDVOL": ["1,000", "1,200"],
                "ACC_TRDVAL": ["2,670,000,000", "3,216,000,000"],
            }
        )
        mock_instance = mock_gold.return_value
        mock_instance.fetch.return_value = mock_df

        result = get_recent_gold_price(30)

        assert "error" not in result
        # Renamed Korean columns are present in the daily records.
        first_row = result["data"][0]
        assert "거래량" in first_row
        assert "거래대금" in first_row
        assert first_row["거래량"] == 1000
        assert first_row["거래대금"] == 2670000000
        # Analysis still computed correctly from normalized numeric values.
        assert result["analysis"]["start_price"] == 2670000
        assert result["analysis"]["average_volume"] == 1100.0
        assert result["analysis"]["total_trading_value"] == 5886000000
