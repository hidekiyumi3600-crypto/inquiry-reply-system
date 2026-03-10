"""問い合わせのビジネスロジック（同期・下書き生成・送信・完了）

楽天API レスポンス構造:
- 一覧: {totalCount, totalPageCount, page, list: [{inquiryNumber, userName, message, ...}]}
- 詳細: {result: {inquiryNumber, userName, message, replies: [{id, message, regDate}], ...}}
"""

import logging
from datetime import datetime, timedelta

from database import db
from services import openai_client, rakuten_api

logger = logging.getLogger(__name__)


# ── 同期 ──────────────────────────────────────────────────


def sync_inquiries(days_back=365):
    """
    楽天APIから問い合わせを取得しDBに同期する。
    楽天APIの日付範囲上限が30日のため、30日ずつ分割してリクエストする。
    Returns: 同期した件数
    """
    MAX_RANGE = 29  # 楽天API日付範囲上限（時刻丸めによる超過を防止）

    try:
        count = 0
        now = datetime.now()
        end = now

        # days_backを30日ごとのチャンクに分割
        remaining = days_back
        while remaining > 0:
            chunk = min(remaining, MAX_RANGE)
            start = end - timedelta(days=chunk)

            from_date = start.strftime("%Y-%m-%dT00:00:00")
            to_date = end.strftime("%Y-%m-%dT23:59:59")

            page = 1
            while True:
                result = rakuten_api.get_inquiries(
                    from_date=from_date, to_date=to_date, page=page
                )
                inquiry_list = result.get("list", [])

                if not inquiry_list:
                    break

                for inq in inquiry_list:
                    data = _map_api_to_db(inq)
                    db.upsert_inquiry(data)
                    count += 1

                total_pages = result.get("totalPageCount", 1)
                if page >= total_pages:
                    break
                page += 1

            end = start
            remaining -= chunk

        db.log_sync(count, "success")
        logger.info("同期完了: %d件", count)
        return count

    except Exception as e:
        db.log_sync(0, "error", str(e))
        logger.error("同期エラー: %s", e)
        raise


def _map_api_to_db(api_data):
    """楽天APIのレスポンス (list内の各要素) をDB形式にマッピング

    楽天APIフィールド → DBフィールド:
      inquiryNumber → inquiry_number
      userName → customer_name
      userMaskEmail → customer_email
      message → body (お客様の問い合わせ本文)
      regDate → inquiry_date
      itemName → item_name
      itemNumber → item_number
      orderNumber → order_number
      category → category
      type → subject (問い合わせタイプ)
      isCompleted → status
      replies → (返信があれば replied)
    """
    # ステータスの判定
    # 「店舗からの問い合わせ」(type末尾m)は店舗が先にメッセージを送っている
    # → 最後のメッセージがuserからなら「未返信(要対応)」と判定
    is_completed = api_data.get("isCompleted", False)
    replies = api_data.get("replies", [])
    inquiry_type = api_data.get("type", "")
    is_merchant_initiated = inquiry_type == "店舗からの問い合わせ"

    if is_completed:
        status = "completed"
    elif not replies:
        if is_merchant_initiated:
            # 店舗発信で返信なし = 顧客がまだ返信していない = 店舗対応不要
            status = "replied"
        else:
            # 顧客発信で返信なし = 未返信
            status = "open"
    else:
        last_reply = replies[-1]
        last_from = last_reply.get("replyFrom", "").lower()
        if last_from == "merchant":
            status = "replied"
        else:
            # 最後がuser = お客様の返信に未対応
            status = "open"

    return {
        "inquiry_number": api_data.get("inquiryNumber", ""),
        "status": status,
        "category": api_data.get("category", ""),
        "subject": api_data.get("type", ""),
        "customer_name": api_data.get("userName", ""),
        "customer_email": api_data.get("userMaskEmail", ""),
        "item_name": api_data.get("itemName", ""),
        "item_number": api_data.get("itemNumber", ""),
        "order_number": api_data.get("orderNumber", ""),
        "body": api_data.get("message", ""),
        "inquiry_date": api_data.get("regDate", ""),
        "raw_json": api_data,
    }


# ── 一覧取得 ──────────────────────────────────────────────


def get_inquiry_list():
    """ステータス情報付きの問い合わせ一覧を返す"""
    inquiries = db.get_all_inquiries()
    for inq in inquiries:
        drafts = db.get_drafts(inq["inquiry_number"])
        inq["has_draft"] = len(drafts) > 0
    return inquiries


def get_inquiry_detail(inquiry_number):
    """問い合わせ詳細を返信履歴付きで返す"""
    inquiry = db.get_inquiry(inquiry_number)
    if not inquiry:
        return None

    drafts = db.get_drafts(inquiry_number)
    sent_replies = db.get_sent_replies(inquiry_number)

    # raw_jsonからAPIの返信履歴も取得
    api_replies = []
    if inquiry.get("raw_json"):
        import json

        try:
            raw = json.loads(inquiry["raw_json"])
            api_replies = raw.get("replies", [])
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "inquiry": inquiry,
        "drafts": drafts,
        "sent_replies": sent_replies,
        "api_replies": api_replies,
    }


# ── AI下書き生成 ──────────────────────────────────────────


def generate_draft(inquiry_number):
    """OpenAI APIで返信下書きを生成しDBに保存"""
    inquiry = db.get_inquiry(inquiry_number)
    if not inquiry:
        raise ValueError(f"問い合わせが見つかりません: {inquiry_number}")

    reply_text = openai_client.generate_reply(inquiry)
    db.save_draft(inquiry_number, reply_text)
    return reply_text


# ── 返信送信 ──────────────────────────────────────────────


def send_reply(inquiry_number, body):
    """楽天APIで返信を送信しDBを更新"""
    rakuten_api.send_reply(inquiry_number, body)
    db.mark_reply_sent(inquiry_number, body)
    db.update_inquiry_status(inquiry_number, "replied")
    return True


# ── 対応完了 ──────────────────────────────────────────────


def mark_complete(inquiry_number):
    """楽天APIで対応完了にしDBを更新"""
    rakuten_api.mark_complete(inquiry_number)
    db.update_inquiry_status(inquiry_number, "completed")
    return True
