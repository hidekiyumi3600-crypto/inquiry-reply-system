"""楽天RMS 問い合わせ管理API クライアント (ESA認証)

API仕様:
- ベースURL: https://api.rms.rakuten.co.jp/es/1.0/inquirymng-api
- 認証: ESA方式 (Authorization: ESA base64(serviceSecret:licenseKey))
- 日時形式: YYYY-MM-DDTHH:MM:SS
- licenseKeyは90日ごとに更新が必要
"""

import base64
import logging

import requests

from config import Config

logger = logging.getLogger(__name__)


def _auth_header():
    """ESA認証ヘッダーを生成"""
    raw = f"{Config.RAKUTEN_SERVICE_SECRET}:{Config.RAKUTEN_LICENSE_KEY}"
    token = base64.b64encode(raw.encode()).decode()
    return {"Authorization": f"ESA {token}"}


def _base_headers():
    headers = _auth_header()
    headers["Content-Type"] = "application/json; charset=utf-8"
    return headers


def _url(path):
    return f"{Config.RAKUTEN_API_BASE}/{path.lstrip('/')}"


def _handle_response(resp, context=""):
    """レスポンスを処理し、エラーがあればログに出力"""
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        # APIエラーレスポンスをパースして詳細をログに出す
        try:
            error_body = resp.json()
            error_info = error_body.get("error", {})
            logger.error(
                "楽天API エラー [%s]: code=%s, message=%s",
                context,
                error_info.get("code", resp.status_code),
                error_info.get("message", resp.text),
            )
        except ValueError:
            logger.error("楽天API エラー [%s]: %s %s", context, resp.status_code, resp.text)
        raise
    return resp.json()


# ── 問い合わせ件数取得 ────────────────────────────────────


def get_inquiry_count(from_date, to_date, no_merchant_reply=False):
    """
    問い合わせ件数を取得する。

    Args:
        from_date: 開始日時 (YYYY-MM-DDTHH:MM:SS)
        to_date: 終了日時 (YYYY-MM-DDTHH:MM:SS)
        no_merchant_reply: True=未返信のみ
    Returns:
        int: 件数
    """
    params = {"fromDate": from_date, "toDate": to_date}
    if no_merchant_reply:
        params["noMerchantReply"] = "true"

    try:
        resp = requests.get(
            _url("inquiries/count"), headers=_base_headers(), params=params, timeout=30
        )
        data = _handle_response(resp, "件数取得")
        return data.get("result", {}).get("count", 0)
    except requests.RequestException as e:
        logger.error("楽天API 件数取得エラー: %s", e)
        raise


# ── 問い合わせ一覧取得 ────────────────────────────────────


def get_inquiries(from_date, to_date, page=1, limit=30, no_merchant_reply=False):
    """
    問い合わせ一覧を取得する。

    Args:
        from_date: 開始日時 (YYYY-MM-DDTHH:MM:SS)
        to_date: 終了日時 (YYYY-MM-DDTHH:MM:SS)
        page: ページ番号 (1始まり)
        limit: 1ページの件数
        no_merchant_reply: True=未返信のみ
    Returns:
        dict: {totalCount, totalPageCount, page, list: [...]}
    """
    params = {
        "fromDate": from_date,
        "toDate": to_date,
        "page": page,
        "limit": limit,
    }
    if no_merchant_reply:
        params["noMerchantReply"] = "true"

    try:
        resp = requests.get(
            _url("inquiries"), headers=_base_headers(), params=params, timeout=30
        )
        return _handle_response(resp, "一覧取得")
    except requests.RequestException as e:
        logger.error("楽天API 一覧取得エラー: %s", e)
        raise


# ── 個別問い合わせ詳細取得 ─────────────────────────────────


def get_inquiry_detail(inquiry_number):
    """
    問い合わせ詳細を取得する。

    Returns:
        dict: {result: {inquiryNumber, userName, message, replies, ...}}
    """
    try:
        resp = requests.get(
            _url(f"inquiry/{inquiry_number}"),
            headers=_base_headers(),
            timeout=30,
        )
        return _handle_response(resp, f"詳細取得 {inquiry_number}")
    except requests.RequestException as e:
        logger.error("楽天API 詳細取得エラー (No.%s): %s", inquiry_number, e)
        raise


# ── 返信送信 ──────────────────────────────────────────────


def send_reply(inquiry_number, message):
    """
    問い合わせに返信を送信する。

    Args:
        inquiry_number: 問い合わせ番号
        message: 返信本文
    Returns:
        dict: {result: {inquiryNumber, message, regDate, ...}}
    """
    payload = {
        "inquiryNumber": inquiry_number,
        "shopId": Config.RAKUTEN_SHOP_ID,
        "message": message,
    }
    try:
        resp = requests.post(
            _url("inquiry/reply"),
            headers=_base_headers(),
            json=payload,
            timeout=30,
        )
        return _handle_response(resp, f"返信送信 {inquiry_number}")
    except requests.RequestException as e:
        logger.error("楽天API 返信送信エラー (No.%s): %s", inquiry_number, e)
        raise


# ── 対応完了マーク ────────────────────────────────────────


def mark_complete(inquiry_numbers):
    """
    問い合わせを対応完了にする。

    Args:
        inquiry_numbers: str or list[str]
    Returns:
        dict: {result: {ok: [...], error: [...]}}
    """
    if isinstance(inquiry_numbers, str):
        inquiry_numbers = [inquiry_numbers]
    payload = {"inquiryNumbers": inquiry_numbers}
    try:
        resp = requests.patch(
            _url("inquiries/complete"),
            headers=_base_headers(),
            json=payload,
            timeout=30,
        )
        return _handle_response(resp, "対応完了")
    except requests.RequestException as e:
        logger.error("楽天API 完了マークエラー: %s", e)
        raise


# ── 既読マーク ────────────────────────────────────────────


def mark_read(inquiry_numbers):
    """
    問い合わせを既読にする。

    Args:
        inquiry_numbers: str or list[str]
    Returns:
        dict: {result: {ok: [...], error: [...]}}
    """
    if isinstance(inquiry_numbers, str):
        inquiry_numbers = [inquiry_numbers]
    payload = {"inquiryNumbers": inquiry_numbers}
    try:
        resp = requests.patch(
            _url("inquiries/read"),
            headers=_base_headers(),
            json=payload,
            timeout=30,
        )
        return _handle_response(resp, "既読マーク")
    except requests.RequestException as e:
        logger.error("楽天API 既読マークエラー: %s", e)
        raise
