"""Flask アプリケーション エントリーポイント"""

from flask import Flask

from config import Config
from database import db
from routes import api, dashboard


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # DB初期化
    db.init_db(app.config["DATABASE_PATH"])

    # Blueprint登録
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(api.bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="127.0.0.1", port=5001)
