"""問い合わせ返信システム — Streamlit版"""

import streamlit as st

from config import Config
from database import db
from services import inquiry_service

# ── DB初期化 ──────────────────────────────────────────────
db.init_db(Config.DATABASE_PATH)

# ── ページ設定 ────────────────────────────────────────────
st.set_page_config(page_title="問い合わせ返信", page_icon="📩", layout="wide")

# ── セッション初期化 ──────────────────────────────────────
if "selected_inquiry" not in st.session_state:
    st.session_state.selected_inquiry = None


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
            options=["all", "open", "replied", "completed"],
            format_func=lambda s: {
                "all": "すべて",
                "open": "🔴 未返信",
                "replied": "🔵 返信済",
                "completed": "🟢 完了",
            }[s],
            label_visibility="collapsed",
        )

        st.divider()

        # 一覧に戻るボタン
        if st.session_state.selected_inquiry:
            if st.button("← 一覧に戻る", use_container_width=True):
                st.session_state.selected_inquiry = None
                st.rerun()

    return status_filter


# ── ダッシュボード（一覧） ────────────────────────────────
def render_dashboard(status_filter):
    inquiries = inquiry_service.get_inquiry_list()

    # 件数カウント
    counts = {"all": len(inquiries), "open": 0, "replied": 0, "completed": 0}
    for inq in inquiries:
        s = inq["status"]
        if s in counts:
            counts[s] += 1

    # フィルタ適用
    if status_filter != "all":
        inquiries = [inq for inq in inquiries if inq["status"] == status_filter]

    # ヘッダー
    st.header("問い合わせ一覧")
    cols = st.columns(4)
    cols[0].metric("すべて", counts["all"])
    cols[1].metric("🔴 未返信", counts["open"])
    cols[2].metric("🔵 返信済", counts["replied"])
    cols[3].metric("🟢 完了", counts["completed"])

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
        elif inq.get("has_draft"):
            badge = "🟡 下書き"
        else:
            badge = "🔴 未返信"

        inquiry_num = inq["inquiry_number"]
        customer = inq.get("customer_name") or "-"
        category = inq.get("category") or "-"
        item = inq.get("item_name") or "-"
        body_preview = (inq.get("body") or "-")[:50]
        date = inq.get("inquiry_date") or "-"

        col1, col2, col3, col4, col5, col6, col7 = st.columns(
            [1, 1.5, 1, 1, 1.5, 2, 0.8]
        )
        col1.write(badge)
        col2.write(f"`{inquiry_num}`")
        col3.write(customer)
        col4.write(category)
        col5.write(item)
        col6.write(body_preview)
        if col7.button("詳細", key=f"btn_{inquiry_num}"):
            st.session_state.selected_inquiry = inquiry_num
            st.rerun()


# ── 詳細画面 ──────────────────────────────────────────────
def render_detail(inquiry_number):
    data = inquiry_service.get_inquiry_detail(inquiry_number)
    if not data:
        st.error("問い合わせが見つかりません。")
        st.session_state.selected_inquiry = None
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
        st.text_area(
            "本文",
            value=inquiry.get("body") or "(内容なし)",
            height=200,
            disabled=True,
            label_visibility="collapsed",
        )

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

        # AI下書き生成
        if st.button("✨ AI下書き生成"):
            with st.spinner("AIが返信を考えています..."):
                try:
                    draft_text = inquiry_service.generate_draft(inquiry_number)
                    st.session_state[f"draft_{inquiry_number}"] = draft_text
                    st.rerun()
                except Exception as e:
                    st.error(f"生成エラー: {e}")

        # テキストエリア（下書きがあれば表示）
        default_text = ""
        if f"draft_{inquiry_number}" in st.session_state:
            default_text = st.session_state[f"draft_{inquiry_number}"]
        elif drafts:
            default_text = drafts[0]["body"]

        reply_body = st.text_area(
            "返信内容",
            value=default_text,
            height=300,
            placeholder="ここに返信内容が表示されます。AI下書き生成を押すか、直接入力してください。",
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

if st.session_state.selected_inquiry:
    render_detail(st.session_state.selected_inquiry)
else:
    render_dashboard(status_filter)
