"""問い合わせ返信システム — Streamlit版"""

import hashlib
import re

import streamlit as st
import streamlit.components.v1 as components
from streamlit_cookies_controller import CookieController

from config import Config

cookie_controller = CookieController()


# ── キャンセル検出 ────────────────────────────────────────
CANCEL_KEYWORDS = [
    "キャンセル", "取り消し", "取消", "注文を取り消", "注文取消",
    "キャンセルしたい", "キャンセル希望", "キャンセルお願い",
    "キャンセルをお願い", "取りやめ", "注文をやめ",
]
_cancel_pattern = re.compile("|".join(CANCEL_KEYWORDS))


def is_cancel_request(text):
    """テキストにキャンセル関連キーワードが含まれるか判定"""
    if not text:
        return False
    return bool(_cancel_pattern.search(text))
from database import db
from services import inquiry_service

# ── DB初期化 ──────────────────────────────────────────────
db.init_db(Config.DATABASE_PATH)

# ── ページ設定 ────────────────────────────────────────────
st.set_page_config(page_title="問い合わせ返信", page_icon="📩", layout="wide")

# Safari等の古いブラウザでStreamlit内部のLaTeX検出regexがエラーになる問題を抑制
components.html(
    """<script>
    window.addEventListener('error', function(e) {
        if (e.message && e.message.includes('Invalid regular expression')) {
            e.preventDefault();
            return true;
        }
    });
    </script>""",
    height=0,
)

# ── 認証 ──────────────────────────────────────────────────
def _auth_token():
    return hashlib.sha256(f"inquiry-auth-{Config.APP_PASSWORD}".encode()).hexdigest()[:32]


def check_password():
    """パスワード認証。クッキーで7日間ログイン維持。"""
    # セッション内で認証済み
    if st.session_state.get("authenticated"):
        return True

    # クッキーをチェック（初回レンダリングではNoneが返るので1回待つ）
    token = cookie_controller.get("auth_token")
    if token is None and "cookie_loaded" not in st.session_state:
        st.session_state.cookie_loaded = True
        st.rerun()
        return False

    if token == _auth_token():
        st.session_state.authenticated = True
        return True

    st.title("📩 問い合わせ返信システム")
    password = st.text_input("パスワードを入力してください", type="password")
    if st.button("ログイン", use_container_width=True):
        if password == Config.APP_PASSWORD:
            cookie_controller.set("auth_token", _auth_token(), max_age=7 * 24 * 60 * 60)
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("パスワードが正しくありません。")
    return False


if not check_password():
    st.stop()

# ── URLベースのナビゲーション ─────────────────────────────
def get_selected_inquiry():
    return st.query_params.get("inquiry", None)


def navigate_to_detail(inquiry_number):
    st.query_params.inquiry = inquiry_number
    st.rerun()


def navigate_to_list():
    if "inquiry" in st.query_params:
        del st.query_params["inquiry"]
    st.rerun()


# ── サイドバー ────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.title("📩 問い合わせ返信")

        # 同期セクション
        st.subheader("楽天API同期")
        days_back = st.selectbox(
            "取得期間",
            options=[7, 14, 30, 90, 180, 365],
            index=5,
            format_func=lambda d: f"過去{d}日",
        )
        if st.button("🔄 同期実行", use_container_width=True):
            with st.spinner("楽天APIから同期中..."):
                try:
                    count = inquiry_service.sync_inquiries(days_back=days_back)
                    st.success(f"{count}件を同期しました")
                except Exception as e:
                    st.error(f"同期エラー: {e}")

        last_sync = db.get_last_sync()
        if last_sync:
            st.caption(f"最終同期: {last_sync['synced_at']}")

        st.divider()

        # ステータスフィルタ
        st.subheader("フィルタ")
        status_filter = st.radio(
            "ステータス",
            options=["all", "open", "replied", "completed", "cancel"],
            format_func=lambda s: {
                "all": "すべて",
                "open": "🔴 未返信",
                "replied": "🔵 返信済",
                "completed": "🟢 完了",
                "cancel": "⚠️ キャンセル希望",
            }[s],
            label_visibility="collapsed",
        )

        st.divider()

        # 一覧に戻るボタン
        if get_selected_inquiry():
            if st.button("← 一覧に戻る", use_container_width=True):
                navigate_to_list()

    return status_filter


# ── ダッシュボード（一覧） ────────────────────────────────
def render_dashboard(status_filter):
    inquiries = inquiry_service.get_inquiry_list()

    # キャンセルフラグ付与
    for inq in inquiries:
        inq["is_cancel"] = is_cancel_request(inq.get("body"))

    # 件数カウント
    counts = {"all": len(inquiries), "open": 0, "replied": 0, "completed": 0, "cancel": 0}
    for inq in inquiries:
        s = inq["status"]
        if s in counts:
            counts[s] += 1
        if inq["is_cancel"]:
            counts["cancel"] += 1

    # フィルタ適用
    if status_filter == "cancel":
        inquiries = [inq for inq in inquiries if inq["is_cancel"]]
    elif status_filter != "all":
        inquiries = [inq for inq in inquiries if inq["status"] == status_filter]

    # ヘッダー
    st.header("問い合わせ一覧")
    cols = st.columns(5)
    cols[0].metric("すべて", counts["all"])
    cols[1].metric("🔴 未返信", counts["open"])
    cols[2].metric("🔵 返信済", counts["replied"])
    cols[3].metric("🟢 完了", counts["completed"])
    cols[4].metric("⚠️ キャンセル", counts["cancel"])

    st.divider()

    if not inquiries:
        st.info("問い合わせがありません。サイドバーの「同期実行」で取得してください。")
        return

    # テーブル表示
    for inq in inquiries:
        status = inq["status"]
        if status == "completed":
            badge = "🟢 完了"
        elif status == "replied":
            badge = "🔵 返信済"
        else:
            badge = "🔴 未返信"

        if inq["is_cancel"]:
            badge = f"⚠️ {badge}"

        inquiry_num = inq["inquiry_number"]
        customer = (inq.get("customer_name") or "-")[:6]
        item = (inq.get("item_name") or "-")[:15]
        body_preview = (inq.get("body") or "-")[:20]

        col1, col2, col3, col4, col5, col6 = st.columns(
            [0.8, 0.8, 1.2, 1.2, 1.5, 0.6]
        )
        col1.write(badge)
        col2.write(customer)
        col3.write(item)
        col4.write(body_preview)
        col5.write(f"`{inquiry_num}`")
        col6.markdown(
            f'<a href="?inquiry={inquiry_num}" target="_blank" '
            f'style="text-decoration:none;">📋 詳細</a>',
            unsafe_allow_html=True,
        )


# ── 詳細画面 ──────────────────────────────────────────────
def render_detail(inquiry_number):
    data = inquiry_service.get_inquiry_detail(inquiry_number)
    if not data:
        st.error("問い合わせが見つかりません。")
        navigate_to_list()
        return

    inquiry = data["inquiry"]
    drafts = data["drafts"]
    sent_replies = data["sent_replies"]
    api_replies = data["api_replies"]

    status = inquiry["status"]
    if status == "completed":
        status_label = "🟢 対応完了"
    elif status == "replied":
        status_label = "🔵 返信済み"
    else:
        status_label = "🔴 未返信"

    st.header(f"問い合わせ #{inquiry_number}")
    st.write(status_label)

    if is_cancel_request(inquiry.get("body")):
        st.warning("⚠️ この問い合わせにはキャンセル希望の内容が含まれています")

    left, right = st.columns([2, 3])

    # ── 左カラム: 問い合わせ情報 ──
    with left:
        st.subheader("問い合わせ情報")
        info_data = {
            "番号": f"`{inquiry['inquiry_number']}`",
            "お客様名": inquiry.get("customer_name") or "-",
            "カテゴリ": inquiry.get("category") or "-",
            "商品名": inquiry.get("item_name") or "-",
            "商品番号": inquiry.get("item_number") or "-",
            "注文番号": inquiry.get("order_number") or "-",
            "問い合わせ日": inquiry.get("inquiry_date") or "-",
        }
        for label, value in info_data.items():
            st.markdown(f"**{label}:** {value}")

        st.divider()
        st.subheader("お問い合わせ内容")
        st.write(inquiry.get("body") or "(内容なし)")

        # 返信履歴
        if api_replies or sent_replies:
            st.divider()
            st.subheader("返信履歴")
            for reply in api_replies:
                with st.container():
                    reply_from = reply.get("replyFrom", "")
                    from_label = "🏪 店舗" if reply_from.lower() == "merchant" else "👤 お客様"
                    st.caption(f"{reply.get('regDate', '')} — {from_label}")
                    st.write(reply.get("message", ""))
                    st.divider()
            for reply in sent_replies:
                with st.container():
                    st.caption(f"{reply['created_at']} — 🏪 店舗 (ローカル記録)")
                    st.write(reply["body"])
                    st.divider()

    # ── 右カラム: 返信エディタ ──
    with right:
        st.subheader("返信エディタ")

        reply_body = st.text_area(
            "返信内容",
            height=300,
            placeholder="返信内容を入力してください。",
            label_visibility="collapsed",
        )

        # アクションボタン
        btn_col1, btn_col2 = st.columns(2)

        with btn_col1:
            if st.button("📤 返信を送信", use_container_width=True, type="primary"):
                if not reply_body.strip():
                    st.warning("返信内容を入力してください。")
                else:
                    with st.spinner("送信中..."):
                        try:
                            inquiry_service.send_reply(inquiry_number, reply_body.strip())
                            st.success("返信を送信しました！")
                            # 下書きセッションをクリア
                            st.session_state.pop(f"draft_{inquiry_number}", None)
                            st.rerun()
                        except Exception as e:
                            st.error(f"送信エラー: {e}")

        with btn_col2:
            if status != "completed":
                if st.button("✅ 対応完了", use_container_width=True):
                    with st.spinner("処理中..."):
                        try:
                            inquiry_service.mark_complete(inquiry_number)
                            st.success("対応完了にしました！")
                            st.rerun()
                        except Exception as e:
                            st.error(f"エラー: {e}")


# ── メイン ────────────────────────────────────────────────
status_filter = render_sidebar()

selected = get_selected_inquiry()
if selected:
    render_detail(selected)
else:
    render_dashboard(status_filter)
