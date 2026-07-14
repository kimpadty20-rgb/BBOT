import sqlite3
import random
import string
import os
from datetime import datetime
from flask import Flask, jsonify, request, render_template

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "codes.db")

# 봇과 웹앱 사이의 간단한 인증용 시크릿 (환경변수로 바꿔서 쓰세요)
API_SECRET = os.environ.get("API_SECRET", "change-this-secret")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS codes (
            code TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            redeemed_at TEXT,
            redeemed_by TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def generate_code(length=12):
    # 영문 대문자만 사용 (헷갈리는 O, I 는 제외)
    chars = "".join(c for c in string.ascii_uppercase if c not in "OI")
    return "".join(random.choice(chars) for _ in range(length))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def api_generate():
    conn = get_db()
    while True:
        code = generate_code()
        exists = conn.execute("SELECT 1 FROM codes WHERE code = ?", (code,)).fetchone()
        if not exists:
            break
    conn.execute(
        "INSERT INTO codes (code, created_at) VALUES (?, ?)",
        (code, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    return jsonify({"code": code})


@app.route("/api/redeem", methods=["POST"])
def api_redeem():
    # 디스코드 봇이 호출하는 엔드포인트
    data = request.get_json(force=True) or {}
    if data.get("secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401

    code = (data.get("code") or "").strip().upper()
    user = data.get("user", "unknown")

    if not code:
        return jsonify({"valid": False, "reason": "no_code"}), 400

    conn = get_db()
    row = conn.execute("SELECT * FROM codes WHERE code = ?", (code,)).fetchone()

    if not row:
        conn.close()
        return jsonify({"valid": False, "reason": "not_found"})

    if row["redeemed_at"]:
        conn.close()
        return jsonify({"valid": False, "reason": "already_used"})

    conn.execute(
        "UPDATE codes SET redeemed_at = ?, redeemed_by = ? WHERE code = ?",
        (datetime.utcnow().isoformat(), user, code),
    )
    conn.commit()
    conn.close()
    return jsonify({"valid": True})


@app.route("/api/status/<code>")
def api_status(code):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM codes WHERE code = ?", (code.strip().upper(),)
    ).fetchone()
    conn.close()
    if not row:
        return jsonify({"exists": False})
    return jsonify(
        {
            "exists": True,
            "redeemed": bool(row["redeemed_at"]),
            "redeemed_by": row["redeemed_by"],
        }
    )


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
