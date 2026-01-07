#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coma‑Link backend
・/courses         既定コマ（何限）CRUD
・/custom_slots    カスタムコマ（時刻レンジ）CRUD
・/match           フリーコマと重なる他ユーザーのコマを返す
"""
import os, sqlite3, json, datetime as dt
from flask import Flask, g, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
CORS(app)               
DB_PATH = os.path.join(app.root_path, "coma_link.db")

## ---------- 共通 ----------
# 大学のコマ時間割 (8限まで)
PERIOD_TIMES = {
    1: ('09:00', '10:30'),
    2: ('10:40', '12:10'),
    3: ('12:10', '13:00'), # 昼休み
    4: ('13:00', '14:30'),
    5: ('14:40', '16:10'),
    6: ('16:15', '17:45'),
    7: ('17:50', '19:20'),
    8: ('19:30', '21:00'),
}

# カテゴリ設定
CATEGORY_SETTINGS = {
    "食事": {"icon": "🍱", "preset": True, "default_title": "ランチに行きませんか？"},
    "勉強": {"icon": "📖", "preset": True, "default_title": "課題一緒にやりましょう"},
    "スポーツ": {"icon": "⚽", "preset": True, "default_title": "スポーツしましょう"},
    "雑談": {"icon": "💬", "preset": True, "default_title": "空きコマ雑談"},
    "趣味": {"icon": "🎮", "preset": False, "default_title": ""},
    "その他": {"icon": "✨", "preset": False, "default_title": ""}
}

JP2ENG = {'月':'Mon','火':'Tue','水':'Wed','木':'Thu','金':'Fri'}
ENG2JP = {v:k for k,v in JP2ENG.items()}

# --- データベース接続ラッパー (SQLite/Postgres互換用) ---
class DBWrapper:
    """SQLiteとPostgreSQLの差異を吸収するラッパークラス"""
    def __init__(self, conn, is_postgres=False):
        self.conn = conn
        self.is_postgres = is_postgres

    def execute(self, query, params=()):
        # PostgreSQLの場合、SQLiteのプレースホルダ '?' を '%s' に変換
        if self.is_postgres:
            query = query.replace('?', '%s')
            cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        else:
            cursor = self.conn.cursor()
        
        cursor.execute(query, params)
        return cursor

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()
        
    def cursor(self):
        if self.is_postgres:
            return self.conn.cursor(cursor_factory=RealDictCursor)
        return self.conn.cursor()

def get_db():
    db = getattr(g, "_db", None)
    if db is None:
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url:
            # クラウド環境 (PostgreSQL)
            conn = psycopg2.connect(database_url)
            db = DBWrapper(conn, is_postgres=True)
        else:
            # ローカル環境 (SQLite)
            conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            db = DBWrapper(conn, is_postgres=False)
            
        g._db = db
    return db

@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, "_db", None)
    if db is not None:
        db.close()

## ---------- 初期化 ----------
def init_db():
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS courses(
            username TEXT NOT NULL,
            day      TEXT NOT NULL,
            slot     INTEGER NOT NULL,
            start_time TEXT,
            end_time   TEXT,
            content  TEXT,
            PRIMARY KEY(username, day, slot)
        )
    ''')

    # custom_slots
    cur.execute('''
        CREATE TABLE IF NOT EXISTS custom_slots(
            username   TEXT NOT NULL,
            day        TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time   TEXT NOT NULL,
            content    TEXT,
            PRIMARY KEY(username, day, start_time)
        )
    ''')

    # users
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            grade INTEGER,
            faculty TEXT,
            department TEXT,
            circles TEXT
        )
    ''')

    # recruitments (start_slot, end_slot 対応版)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS recruitments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_username TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT,
            max_participants INTEGER DEFAULT 2,
            location TEXT,
            date TEXT NOT NULL,
            day TEXT NOT NULL,
            start_slot INTEGER NOT NULL,
            end_slot INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # participants
    cur.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recruitment_id INTEGER NOT NULL,
            applicant_username TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (recruitment_id) REFERENCES recruitments(id)
        )
    ''')

    db.commit(); db.close()


## ---------- 既定コマ API (修正済み) ----------
@app.route("/courses", methods=["GET","POST","DELETE"])
def courses():
    db = get_db()
    # cur = db.cursor() ← 削除: これを使うと変換が効かないため

    if request.method == "GET":
        u = request.args.get("username","").strip()
        # 修正: db.execute を使用
        cur = db.execute("SELECT day,slot,content FROM courses WHERE username=?", (u,))
        return jsonify([dict(r) for r in cur.fetchall()])

    data = request.get_json();  u = data.get("username","").strip()

    if request.method == "POST":
        day  = data["day"]
        slot = int(data["slot"])
        content = data.get("content","")

        st, et = PERIOD_TIMES.get(slot, ("00:00", "00:00"))         
        # 修正: db.execute を使用
        db.execute('''
            INSERT INTO courses(username, day, slot, start_time, end_time, content)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(username, day, slot)
            DO UPDATE SET content=excluded.content
        ''', (u, day, slot, st, et, content))
        db.commit()
        return jsonify(success=True)

    # DELETE
    # 修正: db.execute を使用
    db.execute("DELETE FROM courses WHERE username=? AND day=? AND slot=?",
                (u, data["day"], data["slot"]))
    db.commit()
    return jsonify(success=True)

## ---------- カスタムコマ API (修正済み) ----------
@app.route("/custom_slots", methods=["GET","POST","DELETE"])
def custom_slots():
    db = get_db()
    
    if request.method == "GET":
        u = request.args.get("username","").strip()
        # 修正: db.execute を使用
        cur = db.execute("SELECT day,start_time,end_time,content FROM custom_slots WHERE username=?", (u,))
        return jsonify([dict(r) for r in cur.fetchall()])

    data = request.get_json(); u = data.get("username","").strip()
    if request.method == "POST":
        # 修正: INSERT OR REPLACE (SQLite専用) -> INSERT ... ON CONFLICT (両対応)
        # 修正: db.execute を使用
        db.execute('''
            INSERT INTO custom_slots(username, day, start_time, end_time, content)
            VALUES (?,?,?,?,?)
            ON CONFLICT(username, day, start_time)
            DO UPDATE SET end_time=excluded.end_time, content=excluded.content
        ''', (u,data['day'],data['start_time'],data['end_time'],data.get('content','')))
        db.commit(); return jsonify(success=True)

    # DELETE
    # 修正: db.execute を使用
    db.execute("DELETE FROM custom_slots WHERE username=? AND day=? AND start_time=?",
                (u,data['day'],data['start_time']))
    db.commit(); return jsonify(success=True)

## ---------- マッチ API (今回は省略可能だが残しておく) ----------
@app.route("/match", methods=["POST"])
def match():
    return jsonify([]) # 簡易実装のため省略

## ---------- ユーザー管理 API ----------
@app.route("/profile", methods=["GET", "PUT"])
def profile():
    db = get_db()
    username = request.args.get("username")
    
    if request.method == "GET":
        cur = db.execute("SELECT grade, faculty, department, circles FROM users WHERE username = ?", (username,))
        profile_data = cur.fetchone()
        return jsonify(dict(profile_data) if profile_data else {})

    if request.method == "PUT":
        data = request.get_json()
        db.execute(
            """UPDATE users SET grade=?, faculty=?, department=?, circles=?
               WHERE username = ?""",
            (
                data.get('grade'),
                data.get('faculty'),
                data.get('department'),
                json.dumps(data.get('circles', [])),
                username
            )
        )
        db.commit()
        return jsonify(success=True)

@app.route("/register", methods=["POST"])
def register():
    db = get_db()
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        return jsonify(success=False, message="ユーザー名とパスワードは必須です"), 400
    
    hashed_password = generate_password_hash(password)
    
    try:
        db.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hashed_password)
        )
        db.commit()
        return jsonify(success=True)
    
    except sqlite3.IntegrityError:
        return jsonify(success=False, message="そのユーザー名は既に使用されています"), 400

@app.route("/login", methods=["POST"])
def login():
    db = get_db()
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    cur = db.execute("SELECT password FROM users WHERE username = ?", (username,))
    user_row = cur.fetchone()
    
    if user_row and check_password_hash(user_row['password'], password):
        return jsonify(success=True)
    else:
        return jsonify(success=False, message="ユーザー名またはパスワードが違います")

@app.route("/")
def home(): return "Coma‑Link backend running"

## ---------- 募集関連 API (Phase 2 改修) ----------

@app.route("/recruitments", methods=["POST"])
def create_recruitment():
    db = get_db()
    data = request.get_json()
    if not all(k in data for k in ['creator_username', 'title', 'date', 'day', 'start_slot', 'end_slot']):
        return jsonify(success=False, message="必須項目が不足しています"), 400

    cur = db.execute('''
        INSERT INTO recruitments (creator_username, title, category, max_participants, location, date, day, start_slot, end_slot)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['creator_username'],
        data['title'],
        data.get('category'),
        data.get('max_participants', 2),
        data.get('location'),
        data['date'],
        data['day'],
        data['start_slot'],
        data['end_slot']
    ))
    db.commit()
    return jsonify(success=True, recruitment_id=cur.lastrowid)

# ▼▼▼ Phase 2: 複数コマ検索に対応した募集一覧取得 ▼▼▼
@app.route("/recruitments", methods=["GET"])
def get_recruitments():
    db = get_db()
    query = "SELECT * FROM recruitments WHERE 1=1"
    params = []
    
    # 過去のイベントを除外 (デフォルト動作) 
    # クエリパラメータ include_past=true があれば過去も表示
    if request.args.get('include_past') != 'true':
        today_str = dt.datetime.now().strftime("%Y-%m-%d")
        query += " AND date >= ?"
        params.append(today_str)

    multi_slots_query = []
    
    # 複数コマ検索 (例: '月-1,火-3')
    if 'multi_slots' in request.args and request.args['multi_slots']:
        slot_pairs = request.args['multi_slots'].split(',')
        for pair in slot_pairs:
            parts = pair.split('-')
            if len(parts) == 2:
                day, slot = parts[0].strip(), int(parts[1].strip())
                if day:
                    # そのコマが start_slot と end_slot の間に含まれる募集を検索
                    multi_slots_query.append("(day = ? AND ? BETWEEN start_slot AND end_slot)")
                    params.extend([day, slot])
        
        if multi_slots_query:
            query += " AND (" + " OR ".join(multi_slots_query) + ")"

    # 通常のフィルタリング
    else:
        if 'category' in request.args:
            query += " AND category = ?"
            params.append(request.args['category'])

        if 'location' in request.args:
            query += " AND location = ?"
            params.append(request.args['location'])
            
        if 'date' in request.args:
            query += " AND date = ?"
            params.append(request.args['date'])

        if 'day' in request.args:
            query += " AND day = ?"
            params.append(request.args['day'])

        # ▼ 修正: slot検索を範囲検索に変更
        if 'slot' in request.args:
            query += " AND ? BETWEEN start_slot AND end_slot"
            params.append(request.args['slot'])

    cur = db.execute(query, params)
    recruitments = [dict(row) for row in cur.fetchall()]
    return jsonify(recruitments)
# ▲▲▲ 改修完了 ▲▲▲

@app.route("/recruitments/<int:rec_id>/apply", methods=["POST"])
def apply_for_recruitment(rec_id):
    db = get_db()
    data = request.get_json()
    applicant = data.get("applicant_username")
    if not applicant:
        return jsonify(success=False, message="申請者名が必要です"), 400

    db.execute('''
        INSERT INTO participants (recruitment_id, applicant_username)
        VALUES (?, ?)
    ''', (rec_id, applicant))
    db.commit()
    return jsonify(success=True)

@app.route("/my_recruitments/applications", methods=["GET"])
def get_my_applications():
    db = get_db()
    username = request.args.get("username")
    if not username:
        return jsonify([]), 400

    cur = db.execute('''
        SELECT p.id, p.recruitment_id, r.title, p.applicant_username, p.status
        FROM participants p
        JOIN recruitments r ON p.recruitment_id = r.id
        WHERE r.creator_username = ? AND p.status = 'pending'
    ''', (username,))
    
    applications = [dict(row) for row in cur.fetchall()]
    return jsonify(applications)

@app.route("/applications/<int:app_id>", methods=["PUT"])
def update_application_status(app_id):
    db = get_db()
    data = request.get_json()
    new_status = data.get("status")
    if new_status not in ['approved', 'rejected']:
        return jsonify(success=False, message="無効なステータスです"), 400

    db.execute("UPDATE participants SET status = ? WHERE id = ?", (new_status, app_id))
    db.commit()
    return jsonify(success=True)

@app.route("/heatmap", methods=["GET"])
def get_heatmap():
    db = get_db()
    
    query = "SELECT r.day, r.start_slot, r.end_slot, r.category FROM recruitments r"
    params = []
    join_clause = ""
    filters = []

    # 日付範囲フィルタ
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    if start_date and end_date:
        filters.append(" r.date BETWEEN ? AND ? ")
        params.extend([start_date, end_date])
    
    if request.args.get('grade') or request.args.get('faculty') or request.args.get('circles'):
        join_clause = " JOIN users u ON r.creator_username = u.username "
    
    if request.args.get('grade'):
        filters.append(" u.grade = ? ")
        params.append(request.args.get('grade'))
    if request.args.get('faculty'):
        filters.append(" u.faculty = ? ")
        params.append(request.args.get('faculty'))
    if request.args.get('circles'):
        filters.append(" u.circles LIKE ? ")
        params.append(f"%{request.args.get('circles')}%")

    if filters:
        query += join_clause + " WHERE " + " AND ".join(filters)

    cur = db.execute(query, params)
    rows = cur.fetchall()

    heatmap_data = {}

    for row in rows:
        day = row['day']
        start = row['start_slot']
        end = row['end_slot']
        category = row['category']
        
        # 複数コマを1コマずつ展開して集計
        for slot in range(start, end + 1):
            key = f"{day}-{slot}"
            if key not in heatmap_data:
                heatmap_data[key] = {"count": 0, "categories": []}
            
            heatmap_data[key]["count"] += 1
            if category not in heatmap_data[key]["categories"]:
                heatmap_data[key]["categories"].append(category)

    return jsonify(heatmap_data)

# ▼▼▼ Phase 2: 空きユーザー数API (範囲対応) ▼▼▼
@app.route("/free_users", methods=["GET"])
def get_free_users():
    db = get_db()
    day = request.args.get('day')
    
    # start_slot / end_slot を取得 (指定がない場合は1コマ分とする)
    try:
        start_slot = int(request.args.get('start_slot', 0))
        end_slot = int(request.args.get('end_slot', start_slot))
    except ValueError:
        return jsonify({"count": 0})
    
    if not day or start_slot == 0:
        return jsonify({"count": 0})

    # 1. 全ユーザー数を取得
    cur = db.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]

    # 2. 指定された期間(start_slot 〜 end_slot)のいずれかに
    #    授業(courses)が入っているユーザーの数を取得
    #    (重複排除のため DISTINCT username)
    cur = db.execute("""
        SELECT COUNT(DISTINCT username) 
        FROM courses 
        WHERE day = ? AND slot BETWEEN ? AND ?
    """, (day, start_slot, end_slot))
    
    busy_users = cur.fetchone()[0]

    # 3. 差分が「この期間ずっと空いているユーザー数」
    free_count = max(0, total_users - busy_users)
    
    return jsonify({"count": free_count})

# 新規追加: マイページ用データ取得
@app.route("/my_page_data", methods=["GET"])
def get_my_page_data():
    db = get_db()
    username = request.args.get("username")
    if not username: return jsonify({}), 400

    # 1. 自分が作成した募集 (新しい順)
    cur = db.execute('''
        SELECT * FROM recruitments 
        WHERE creator_username = ? 
        ORDER BY date DESC, start_slot ASC
    ''', (username,))
    created = [dict(r) for r in cur.fetchall()]

    # 2. 自分が参加申請した募集 (新しい順)
    cur = db.execute('''
        SELECT r.title, r.date, r.day, r.start_slot, r.end_slot, r.location, p.status, p.id as app_id
        FROM participants p
        JOIN recruitments r ON p.recruitment_id = r.id
        WHERE p.applicant_username = ?
        ORDER BY r.date DESC
    ''', (username,))
    joined = [dict(r) for r in cur.fetchall()]

    return jsonify({"created": created, "joined": joined})

if __name__ == "__main__":
    with app.app_context():
        init_db()
        print("✔ DB ready :", DB_PATH)
    app.run(host="0.0.0.0", port=5000, debug=True)