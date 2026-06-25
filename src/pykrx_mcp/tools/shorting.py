"""공매도(Short Selling) 데이터 조회 도구."""

# Configure logging to stderr
import logging
from typing import Any

from pykrx import stock

from ..utils.decorators import handle_pykrx_errors
from ..utils.formatters import dict_to_table
from ..utils.krx_session import fetch_with_relogin_on_empty
from ..utils.validators import validate_date, validate_ticker

# Shared hint appended to "no data" errors: an empty KRX response is most often
# an auth/session problem (shorting endpoints require KRX_ID/KRX_PW login),
# not a genuinely empty dataset.
_NO_DATA_HINT = (
    "공매도 엔드포인트는 KRX 로그인이 필요합니다. 빈 결과는 보통 "
    "비거래일이거나 KRX_ID/KRX_PW 미설정·세션 만료가 원인입니다. "
    ".env 의 KRX_ID/KRX_PW 설정과 조회일이 영업일인지 확인하세요."
)

logger = logging.getLogger(__name__)


@handle_pykrx_errors
def get_shorting_status_by_date(
    ticker: str, start_date: str, end_date: str
) -> dict[str, Any]:
    """
    특정 종목의 공매도 현황을 조회합니다.

    Args:
        ticker: 6자리 종목코드 (예: '005930')
        start_date: 조회 시작일 (YYYYMMDD 형식, 예: '20240101')
        end_date: 조회 종료일 (YYYYMMDD 형식, 예: '20240131')

    Returns:
        Dict containing:
        - data: 공매도/잔고/공매도금액/잔고금액 정보
        - error: 오류 발생 시 오류 메시지
    """
    logger.info(
        f"Fetching shorting status for {ticker} from {start_date} to {end_date}"
    )

    # Validate inputs
    if not validate_ticker(ticker):
        return {"error": "Invalid ticker format. Must be 6 digits.", "ticker": ticker}

    if not validate_date(start_date) or not validate_date(end_date):
        return {
            "error": "Invalid date format. Use YYYYMMDD (e.g., '20240101').",
            "start_date": start_date,
            "end_date": end_date,
        }

    df = fetch_with_relogin_on_empty(
        stock.get_shorting_status_by_date, start_date, end_date, ticker
    )

    if df.empty:
        return {
            "error": f"No data found for the given period. {_NO_DATA_HINT}",
            "ticker": ticker,
            "start_date": start_date,
            "end_date": end_date,
        }

    # Convert to dict with date as string
    result_dict = df.to_dict(orient="index")
    formatted_dict = {str(k): v for k, v in result_dict.items()}

    return {
        "ticker": ticker,
        "start_date": start_date,
        "end_date": end_date,
        "data": formatted_dict,
        "table": dict_to_table(formatted_dict),
    }


@handle_pykrx_errors
def get_shorting_volume_by_ticker(date: str, market: str = "KOSPI") -> dict[str, Any]:
    """
    특정 일자의 전종목 공매도 거래량을 조회합니다.

    Args:
        date: 조회 일자 (YYYYMMDD 형식, 예: '20240101')
        market: 시장 구분 (KOSPI/KOSDAQ/KONEX, 기본값: KOSPI)

    Returns:
        Dict containing:
        - data: 종목별 공매도/매수/비중 정보
        - error: 오류 발생 시 오류 메시지
    """
    logger.info(f"Fetching shorting volume for {market} on {date}")

    if not validate_date(date):
        return {
            "error": "Invalid date format. Use YYYYMMDD (e.g., '20240101').",
            "date": date,
        }

    market_upper = market.upper()
    if market_upper not in ["KOSPI", "KOSDAQ", "KONEX"]:
        return {
            "error": "Invalid market. Must be one of: KOSPI, KOSDAQ, KONEX",
            "market": market,
        }

    df = fetch_with_relogin_on_empty(
        stock.get_shorting_volume_by_ticker, date, market_upper
    )

    if df.empty:
        return {
            "error": f"No data found for the given date. {_NO_DATA_HINT}",
            "date": date,
            "market": market,
        }

    # Convert to dict with ticker as key
    result_dict = df.to_dict(orient="index")
    formatted_dict = {str(k): v for k, v in result_dict.items()}

    return {
        "date": date,
        "market": market_upper,
        "data": formatted_dict,
        "table": dict_to_table(formatted_dict),
    }


@handle_pykrx_errors
def get_shorting_balance_top50(date: str, market: str = "KOSPI") -> dict[str, Any]:
    """
    공매도 잔고 비중 상위 50개 종목을 조회합니다.

    Args:
        date: 조회 일자 (YYYYMMDD 형식, 예: '20240101')
        market: 시장 구분 (KOSPI/KOSDAQ, 기본값: KOSPI)

    Returns:
        Dict containing:
        - data: 순위별 공매도잔고/상장주식수/시가총액/비중 정보
        - error: 오류 발생 시 오류 메시지
    """
    logger.info(f"Fetching top 50 shorting balance for {market} on {date}")

    if not validate_date(date):
        return {
            "error": "Invalid date format. Use YYYYMMDD (e.g., '20240101').",
            "date": date,
        }

    market_upper = market.upper()
    if market_upper not in ["KOSPI", "KOSDAQ"]:
        return {
            "error": "Invalid market. Must be one of: KOSPI, KOSDAQ",
            "market": market,
        }

    df = fetch_with_relogin_on_empty(
        stock.get_shorting_balance_top50, date, market=market_upper
    )

    if df.empty:
        return {
            "error": f"No data found for the given date. {_NO_DATA_HINT}",
            "date": date,
            "market": market,
        }

    # Convert to dict with ticker as key
    result_dict = df.to_dict(orient="index")
    formatted_dict = {str(k): v for k, v in result_dict.items()}

    return {
        "date": date,
        "market": market_upper,
        "data": formatted_dict,
        "table": dict_to_table(formatted_dict),
    }


@handle_pykrx_errors
def get_shorting_investor_volume_by_date(
    start_date: str, end_date: str, market: str = "KOSPI"
) -> dict[str, Any]:
    """
    투자자별 공매도 거래량(기관/개인/외국인/기타)을 기간별로 조회합니다.

    Args:
        start_date: 조회 시작일 (YYYYMMDD 형식, 예: '20240101')
        end_date: 조회 종료일 (YYYYMMDD 형식, 예: '20240131')
        market: 시장 구분 (KOSPI/KOSDAQ/KONEX, 기본값: KOSPI)

    Returns:
        Dict containing:
        - data: 일자별 기관/개인/외국인/기타/합계 공매도 거래량
        - error: 오류 발생 시 오류 메시지
    """
    logger.info(
        f"Fetching investor shorting volume for {market} "
        f"from {start_date} to {end_date}"
    )

    if not validate_date(start_date) or not validate_date(end_date):
        return {
            "error": "Invalid date format. Use YYYYMMDD (e.g., '20240101').",
            "start_date": start_date,
            "end_date": end_date,
        }

    market_upper = market.upper()
    if market_upper not in ["KOSPI", "KOSDAQ", "KONEX"]:
        return {
            "error": "Invalid market. Must be one of: KOSPI, KOSDAQ, KONEX",
            "market": market,
        }

    df = fetch_with_relogin_on_empty(
        stock.get_shorting_investor_volume_by_date,
        start_date,
        end_date,
        market_upper,
    )

    if df.empty:
        return {
            "error": f"No data found for the given period. {_NO_DATA_HINT}",
            "start_date": start_date,
            "end_date": end_date,
            "market": market,
        }

    # Convert to dict with date as string
    result_dict = df.to_dict(orient="index")
    formatted_dict = {str(k): v for k, v in result_dict.items()}

    return {
        "start_date": start_date,
        "end_date": end_date,
        "market": market_upper,
        "data": formatted_dict,
        "table": dict_to_table(formatted_dict),
    }


@handle_pykrx_errors
def get_shorting_volume_top50(date: str, market: str = "KOSPI") -> dict[str, Any]:
    """
    공매도 거래 비중 상위 50개 종목을 조회합니다.

    Args:
        date: 조회 일자 (YYYYMMDD 형식, 예: '20240101')
        market: 시장 구분 (KOSPI/KOSDAQ, 기본값: KOSPI)

    Returns:
        Dict containing:
        - data: 순위별 공매도거래대금/총거래대금/공매도비중 정보
        - error: 오류 발생 시 오류 메시지
    """
    logger.info(f"Fetching top 50 shorting volume for {market} on {date}")

    if not validate_date(date):
        return {
            "error": "Invalid date format. Use YYYYMMDD (e.g., '20240101').",
            "date": date,
        }

    market_upper = market.upper()
    if market_upper not in ["KOSPI", "KOSDAQ"]:
        return {
            "error": "Invalid market. Must be one of: KOSPI, KOSDAQ",
            "market": market,
        }

    df = fetch_with_relogin_on_empty(
        stock.get_shorting_volume_top50, date, market_upper
    )

    if df.empty:
        return {
            "error": f"No data found for the given date. {_NO_DATA_HINT}",
            "date": date,
            "market": market,
        }

    # Convert to dict with ticker as key
    result_dict = df.to_dict(orient="index")
    formatted_dict = {str(k): v for k, v in result_dict.items()}

    return {
        "date": date,
        "market": market_upper,
        "data": formatted_dict,
        "table": dict_to_table(formatted_dict),
    }
