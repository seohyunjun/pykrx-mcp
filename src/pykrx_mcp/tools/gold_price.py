"""Gold price related MCP tools."""

import logging
from datetime import datetime, timedelta

import pandas as pd
from pykrx.website.krx.items import 개별종목_시세_추이

from ..utils import (
    fetch_with_relogin,
    format_dataframe_response,
    format_error_response,
    mcp_tool_error_handler,
    validate_date_format,
)

logger = logging.getLogger(__name__)

# The KRX gold endpoint (MDCSTAT15001) returns raw column codes with
# comma-formatted string values. Map them to friendly Korean names so all
# downstream tools (incl. 거래량/거래대금) work against live data. Frames that
# already use Korean names (e.g. test fixtures) pass through unchanged.
_GOLD_COLUMN_MAP = {
    "TRD_DD": "날짜",
    "TDD_OPNPRC": "시가",
    "TDD_HGPRC": "고가",
    "TDD_LWPRC": "저가",
    "TDD_CLSPRC": "종가",
    "CMPPREVDD_PRC": "대비",
    "FLUC_RT": "등락률",
    "ACC_TRDVOL": "거래량",
    "ACC_TRDVAL": "거래대금",
}

# Columns that should be coerced from comma-formatted strings to numbers.
_GOLD_NUMERIC_COLS = ["시가", "고가", "저가", "종가", "대비", "등락률", "거래량", "거래대금"]


def _normalize_gold_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a raw KRX gold DataFrame.

    Renames raw KRX column codes (TDD_CLSPRC, ACC_TRDVOL, ...) to Korean
    names and coerces price/volume/trading-value columns to numeric so that
    거래량(volume) and 거래대금(trading value) are always available downstream.

    Args:
        df: DataFrame returned by 개별종목_시세_추이().fetch.

    Returns:
        Normalized DataFrame (empty frames are returned unchanged).
    """
    if df.empty:
        return df

    df = df.rename(
        columns={k: v for k, v in _GOLD_COLUMN_MAP.items() if k in df.columns}
    )
    for col in _GOLD_NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", ""), errors="coerce"
            )
    return df


@mcp_tool_error_handler
def get_latest_gold_price(
    isu_code: str = "KRD040200002",
) -> dict:
    """
    Retrieve the latest gold price data from KRX gold market.

    This tool fetches the most recent gold price information including
    opening, high, low, closing prices and trading volume.

    Args:
        isu_code: KRX issue code (default: "KRD040200002" for KRX Gold Au 99.99)

    Returns:
        Dictionary containing latest gold price data with OHLCV information.

    Example:
        get_latest_gold_price()
        get_latest_gold_price("KRD040200002")
    """
    if not isu_code:
        return format_error_response("isu_code is required", isu_code=isu_code)

    # Get today's date and yesterday's date for fetching
    today = datetime.now()
    yesterday = today - timedelta(days=1)

    start_date = yesterday.strftime("%Y%m%d")
    end_date = today.strftime("%Y%m%d")

    logger.info(
        "Fetching latest gold price for %s (range %s ~ %s)",
        isu_code,
        start_date,
        end_date,
    )

    df = fetch_with_relogin(
        개별종목_시세_추이().fetch,
        isuCd=isu_code,
        strtDd=start_date,
        endDd=end_date,
    )
    logger.debug(
        "Initial fetch returned %d rows for %s", len(df), isu_code
    )

    # If no data today, try yesterday
    if df.empty:
        yesterday = today - timedelta(days=1)
        start_date = yesterday.strftime("%Y%m%d")
        end_date = yesterday.strftime("%Y%m%d")

        logger.debug(
            "No data today; falling back to yesterday %s for %s",
            start_date,
            isu_code,
        )
        df = 개별종목_시세_추이().fetch(
            isuCd=isu_code,
            strtDd=start_date,
            endDd=end_date,
        )
        logger.debug("Fallback fetch returned %d rows", len(df))

    if df.empty:
        logger.warning(
            "No gold price data found for %s (today or yesterday)", isu_code
        )
        return format_error_response(
            "No data found for the specified gold issue",
            isu_code=isu_code,
        )

    df = _normalize_gold_df(df)

    # Get the latest record
    latest_record = df.iloc[-1]
    logger.debug(
        "Latest gold record for %s: date=%s close=%s",
        isu_code,
        latest_record["날짜"],
        latest_record["종가"],
    )

    return {
        "isu_code": isu_code,
        "date": latest_record["날짜"],
        "open": float(latest_record["시가"]),
        "high": float(latest_record["고가"]),
        "low": float(latest_record["저가"]),
        "close": float(latest_record["종가"]),
        "volume": int(latest_record["거래량"]),
        "trading_value": int(latest_record["거래대금"]),
    }


@mcp_tool_error_handler
def get_gold_price_by_date(
    start_date: str,
    end_date: str,
    isu_code: str = "KRD040200002",
) -> dict:
    """
    Retrieve gold price data from KRX gold market.

    Uses pykrx.website.krx.items.개별종목_시세_추이().fetch to retrieve
    gold price history. Default isu_code corresponds to KRX Gold (Au 99.99).

    Args:
        start_date: Start date in YYYYMMDD format (e.g., "20240101").
        end_date: End date in YYYYMMDD format (e.g., "20240131").
        isu_code: KRX issue code (default: "KRD040200002").

    Returns:
        Dictionary containing gold price data with dates and price/volume fields.

    Example:
        get_gold_price_by_date("20240101", "20240131")
    """
    valid, msg = validate_date_format(start_date)
    if not valid:
        return format_error_response(msg, start_date=start_date)

    valid, msg = validate_date_format(end_date)
    if not valid:
        return format_error_response(msg, end_date=end_date)

    if not isu_code:
        return format_error_response("isu_code is required", isu_code=isu_code)

    logger.info(
        "Fetching gold price for %s (range %s ~ %s)",
        isu_code,
        start_date,
        end_date,
    )
    df = fetch_with_relogin(
        개별종목_시세_추이().fetch,
        isuCd=isu_code,
        strtDd=start_date,
        endDd=end_date,
    )
    logger.debug("Fetch returned %d rows for %s", len(df), isu_code)

    if df.empty:
        logger.warning(
            "No gold price data for %s in range %s ~ %s",
            isu_code,
            start_date,
            end_date,
        )
        return format_error_response(
            "No data found for the specified date range",
            isu_code=isu_code,
            start_date=start_date,
            end_date=end_date,
        )

    df = _normalize_gold_df(df)

    return format_dataframe_response(
        df,
        isu_code=isu_code,
        start_date=start_date,
        end_date=end_date,
    )


@mcp_tool_error_handler
def get_gold_price_change(
    start_date: str,
    end_date: str,
    isu_code: str = "KRD040200002",
) -> dict:
    """
    Retrieve gold price change analysis over a specified period.

    This tool calculates price changes, percentage changes, and volatility
    metrics for gold prices over a given date range.

    Args:
        start_date: Start date in YYYYMMDD format (e.g., "20240101").
        end_date: End date in YYYYMMDD format (e.g., "20240131").
        isu_code: KRX issue code (default: "KRD040200002").

    Returns:
        Dictionary containing price change analysis including:
        - Starting price, ending price
        - Absolute change and percentage change
        - Period high and low
        - Average price and volume

    Example:
        get_gold_price_change("20240101", "20240131")
        Returns gold price change analysis for January 2024
    """
    valid, msg = validate_date_format(start_date)
    if not valid:
        return format_error_response(msg, start_date=start_date)

    valid, msg = validate_date_format(end_date)
    if not valid:
        return format_error_response(msg, end_date=end_date)

    if not isu_code:
        return format_error_response("isu_code is required", isu_code=isu_code)

    logger.info(
        "Computing gold price change for %s (range %s ~ %s)",
        isu_code,
        start_date,
        end_date,
    )
    df = fetch_with_relogin(
        개별종목_시세_추이().fetch,
        isuCd=isu_code,
        strtDd=start_date,
        endDd=end_date,
    )
    logger.debug("Fetch returned %d rows for %s", len(df), isu_code)

    if df.empty:
        logger.warning(
            "No gold price data for %s in range %s ~ %s",
            isu_code,
            start_date,
            end_date,
        )
        return format_error_response(
            "No data found for the specified date range",
            isu_code=isu_code,
            start_date=start_date,
            end_date=end_date,
        )

    df = _normalize_gold_df(df)

    # Get first and last closing prices
    start_price = float(df.iloc[0]["종가"])
    end_price = float(df.iloc[-1]["종가"])
    absolute_change = end_price - start_price
    percentage_change = (absolute_change / start_price) * 100 if start_price else 0.0
    logger.debug(
        "Change for %s: %s -> %s (%+.4f%%) over %d days",
        isu_code,
        start_price,
        end_price,
        percentage_change,
        len(df),
    )

    # Calculate period statistics
    period_high = float(df["고가"].max())
    period_low = float(df["저가"].min())
    avg_price = float(df["종가"].mean())
    total_volume = int(df["거래량"].sum())
    total_trading_value = int(df["거래대금"].sum())
    trading_days = len(df)

    return {
        "isu_code": isu_code,
        "start_date": start_date,
        "end_date": end_date,
        "trading_days": trading_days,
        "start_price": start_price,
        "end_price": end_price,
        "absolute_change": absolute_change,
        "percentage_change": percentage_change,
        "period_high": period_high,
        "period_low": period_low,
        "average_price": avg_price,
        "total_volume": total_volume,
        "total_trading_value": total_trading_value,
    }


@mcp_tool_error_handler
def get_recent_gold_price(
    days: int = 30,
    isu_code: str = "KRD040200002",
) -> dict:
    """
    Retrieve and analyze recent KRX gold price data over the last N days.

    Convenience tool for requests like "analyze the last 30 days of gold
    prices". It automatically computes the date range ending today, fetches
    the daily OHLCV history, and returns both the raw daily records and a
    summary analysis (trend, change, volatility, moving average, volume).

    Args:
        days: Number of calendar days to look back from today (default: 30).
        isu_code: KRX issue code (default: "KRD040200002" for KRX Gold Au 99.99).

    Returns:
        Dictionary containing:
        - period metadata (start_date, end_date, requested_days, trading_days)
        - analysis: start/end price, absolute & percentage change, period
          high/low, average close, volatility (stdev of daily returns),
          max daily gain/loss, average volume
        - data: list of daily OHLCV records for further analysis or charting

    Example:
        get_recent_gold_price()        # last 30 days
        get_recent_gold_price(7)       # last 7 days
    """
    if not isinstance(days, int) or days < 1:
        return format_error_response(
            "days must be a positive integer", days=days
        )

    if not isu_code:
        return format_error_response("isu_code is required", isu_code=isu_code)

    today = datetime.now()
    start = today - timedelta(days=days)
    start_date = start.strftime("%Y%m%d")
    end_date = today.strftime("%Y%m%d")

    logger.info(
        "Fetching recent gold price for %s over last %d days (%s ~ %s)",
        isu_code,
        days,
        start_date,
        end_date,
    )

    df = fetch_with_relogin(
        개별종목_시세_추이().fetch,
        isuCd=isu_code,
        strtDd=start_date,
        endDd=end_date,
    )
    logger.debug(
        "Fetch returned %d rows for %s over last %d days", len(df), isu_code, days
    )

    if df.empty:
        logger.warning(
            "No recent gold price data for %s in range %s ~ %s",
            isu_code,
            start_date,
            end_date,
        )
        return format_error_response(
            "No data found for the recent period",
            isu_code=isu_code,
            start_date=start_date,
            end_date=end_date,
        )

    # Normalize raw KRX columns and coerce numerics (incl. 거래량/거래대금).
    df = _normalize_gold_df(df)

    close = df["종가"]
    start_price = float(close.iloc[0])
    end_price = float(close.iloc[-1])
    absolute_change = end_price - start_price
    percentage_change = (
        (absolute_change / start_price) * 100 if start_price else 0.0
    )

    # Daily returns for volatility and best/worst day
    daily_returns = close.pct_change().dropna() * 100

    analysis = {
        "start_price": start_price,
        "end_price": end_price,
        "absolute_change": absolute_change,
        "percentage_change": round(percentage_change, 4),
        "period_high": float(df["고가"].max()),
        "period_low": float(df["저가"].min()),
        "average_price": round(float(close.mean()), 2),
        "volatility_pct": (
            # stdev needs >= 2 returns; otherwise it is NaN (invalid JSON).
            round(float(daily_returns.std()), 4)
            if len(daily_returns) >= 2
            else 0.0
        ),
        "max_daily_gain_pct": (
            round(float(daily_returns.max()), 4)
            if not daily_returns.empty
            else 0.0
        ),
        "max_daily_loss_pct": (
            round(float(daily_returns.min()), 4)
            if not daily_returns.empty
            else 0.0
        ),
        "average_volume": round(float(df["거래량"].mean()), 2),
        "total_trading_value": float(df["거래대금"].sum()),
    }

    logger.debug(
        "Recent analysis for %s: %d trading days, change %+.4f%%, "
        "volatility %.4f%%, high %s, low %s",
        isu_code,
        len(df),
        analysis["percentage_change"],
        analysis["volatility_pct"],
        analysis["period_high"],
        analysis["period_low"],
    )

    response = format_dataframe_response(
        df,
        isu_code=isu_code,
        requested_days=days,
        start_date=start_date,
        end_date=end_date,
        trading_days=len(df),
        analysis=analysis,
    )
    return response
