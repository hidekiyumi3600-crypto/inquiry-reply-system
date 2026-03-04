"""ダッシュボード画面のルート"""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from database import db
from services import inquiry_service

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    """問い合わせ一覧ダッシュボード"""
    status_filter = request.args.get("status", "all")
    inquiries = inquiry_service.get_inquiry_list()

    # 件数カウント（フィルタ前）
    counts = {"all": len(inquiries), "open": 0, "replied": 0, "completed": 0}
    for inq in inquiries:
        s = inq["status"]
        if s in counts:
            counts[s] += 1

    # フィルタ適用
    if status_filter != "all":
        inquiries = [inq for inq in inquiries if inq["status"] == status_filter]

    last_sync = db.get_last_sync()
    return render_template(
        "dashboard.html",
        inquiries=inquiries,
        last_sync=last_sync,
        status_filter=status_filter,
        counts=counts,
    )


@bp.route("/sync", methods=["POST"])
def sync():
    """楽天APIから問い合わせを同期"""
    try:
        days_back = request.form.get("days_back", 365, type=int)
        days_back = max(1, min(days_back, 365))
        count = inquiry_service.sync_inquiries(days_back=days_back)
        flash(f"過去{days_back}日間から{count}件の問い合わせを同期しました。", "success")
    except Exception as e:
        flash(f"同期エラー: {e}", "danger")
    return redirect(url_for("dashboard.index"))


@bp.route("/inquiry/<inquiry_number>")
def inquiry_detail(inquiry_number):
    """問い合わせ詳細画面"""
    data = inquiry_service.get_inquiry_detail(inquiry_number)
    if not data:
        flash("問い合わせが見つかりません。", "warning")
        return redirect(url_for("dashboard.index"))
    return render_template("inquiry_detail.html", **data)
