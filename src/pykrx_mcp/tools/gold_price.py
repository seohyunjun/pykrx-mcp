"""Gold price related MCP tools."""

import logging

from pykrx.website.krx.items import 개별종목_시세_추이

from ..utils import (
    format_dataframe_response,
    format_error_response,
    mcp_tool_error_handler,
    validate_date_format,
)

logger = logging.getLogger(__name__)


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

    df = 개별종목_시세_추이().fetch(
        isuCd=isu_code,
        strtDd=start_date,
        endDd=end_date,
    )

    if df.empty:
        return format_error_response(
            "No data found for the specified date range",
            isu_code=isu_code,
            start_date=start_date,
            end_date=end_date,
        )

    return format_dataframe_response(
        df,
        isu_code=isu_code,
        start_date=start_date,
        end_date=end_date,
    )
