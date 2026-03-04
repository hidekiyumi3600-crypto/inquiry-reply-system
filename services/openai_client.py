"""OpenAI APIを使った返信下書き生成"""

import logging

from openai import OpenAI

from config import Config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
あなたは楽天市場ショップのカスタマーサポートスタッフです。
お客様からのお問い合わせに対して、丁寧で誠実な返信文を作成してください。

ルール:
- 敬語を正しく使い、温かみのある文体で書いてください
- 挨拶（「お問い合わせいただきありがとうございます」等）から始めてください
- 具体的な対応内容や回答を含めてください
- 署名やフッターは含めないでください（返信本文のみ出力）
- 200〜400文字程度を目安にしてください
- 不明な情報については確認する旨を伝えてください
"""


def generate_reply(inquiry_data):
    """
    問い合わせ情報からAI返信下書きを生成する。

    Args:
        inquiry_data: dict with keys like customer_name, category, item_name,
                      item_number, order_number, body
    Returns:
        str: 生成された返信文
    """
    if not Config.OPENAI_API_KEY:
        raise ValueError("OpenAI APIキーが設定されていません。.envファイルを確認してください。")

    client = OpenAI(api_key=Config.OPENAI_API_KEY)

    user_prompt = _build_user_prompt(inquiry_data)

    try:
        response = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=1024,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("OpenAI API エラー: %s", e)
        raise


def _build_user_prompt(data):
    """問い合わせ情報を構造化したプロンプトを作成"""
    parts = ["以下のお問い合わせに対する返信文を作成してください。\n"]

    if data.get("customer_name"):
        parts.append(f"お客様名: {data['customer_name']}")
    if data.get("category"):
        parts.append(f"カテゴリ: {data['category']}")
    if data.get("item_name"):
        parts.append(f"商品名: {data['item_name']}")
    if data.get("item_number"):
        parts.append(f"商品番号: {data['item_number']}")
    if data.get("order_number"):
        parts.append(f"注文番号: {data['order_number']}")

    parts.append(f"\nお問い合わせ内容:\n{data.get('body', '(内容なし)')}")

    return "\n".join(parts)
