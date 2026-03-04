import os

from dotenv import load_dotenv

load_dotenv()


def _get_secret(key, default=""):
    """環境変数 → st.secrets → default の順でフォールバック"""
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st

        return st.secrets.get(key, default)
    except (ImportError, AttributeError, FileNotFoundError):
        return default


class Config:
    DATABASE_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "inquiry.db"
    )

    # 楽天RMS API
    RAKUTEN_SERVICE_SECRET = _get_secret("RAKUTEN_SERVICE_SECRET")
    RAKUTEN_LICENSE_KEY = _get_secret("RAKUTEN_LICENSE_KEY")
    RAKUTEN_SHOP_ID = _get_secret("RAKUTEN_SHOP_ID")
    RAKUTEN_API_BASE = "https://api.rms.rakuten.co.jp/es/1.0/inquirymng-api"

    # OpenAI
    OPENAI_API_KEY = _get_secret("OPENAI_API_KEY")
    OPENAI_MODEL = "gpt-4o-mini"
