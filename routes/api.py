"""AJAX APIエンドポイント"""

from flask import Blueprint, jsonify, request

from services import inquiry_service

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/generate-draft/<inquiry_number>", methods=["POST"])
def generate_draft(inquiry_number):
    """AI下書きを生成"""
    try:
        draft = inquiry_service.generate_draft(inquiry_number)
        return jsonify({"success": True, "draft": draft})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/send-reply/<inquiry_number>", methods=["POST"])
def send_reply(inquiry_number):
    """返信を送信"""
    data = request.get_json()
    body = data.get("body", "").strip() if data else ""

    if not body:
        return jsonify({"success": False, "error": "返信内容が空です。"}), 400

    try:
        inquiry_service.send_reply(inquiry_number, body)
        return jsonify({"success": True, "message": "返信を送信しました。"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/mark-complete/<inquiry_number>", methods=["POST"])
def mark_complete(inquiry_number):
    """対応完了にする"""
    try:
        inquiry_service.mark_complete(inquiry_number)
        return jsonify({"success": True, "message": "対応完了にしました。"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
