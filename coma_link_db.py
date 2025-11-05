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

app = Flask(__name__)
CORS(app)               
DB_PATH = os.path.join(app.root_path, "coma_link.db")

## ---------- 共通 ----------
# 大学のコマ時間割を定義 (ここで区切り時間を編集)
# (例: 1限 09:00-10:30, 2限 10:40-12:10 ...)
PERIOD_TIMES = {
    1: ('09:00', '10:30'),
    2: ('10:40', '12:10'),
    3: ('13:00', '14:30'), # 昼休み
    4: ('14:40', '16:10'),
    5: ('16:15', '17:45'),
    6: ('17:50', '19:20'),
    7: ('19:30', '21:00'),
}
JP2ENG = {'月':'Mon','火':'Tue','水':'Wed','木':'Thu','金':'Fri'}
ENG2JP = {v:k for k,v in JP2ENG.items()}

# def get_db():
#     db = getattr(g, "_db", None)
#     if db is None:
#         db = sqlite3.connect(DB_PATH)
#         db.row_factory = sqlite3.Row
#         g._db = db
#     return db
# ---------- 共通 ----------
def get_db():
    db = getattr(g, "_db", None)
    if db is None:
        # timeout=10秒 / check_same_thread=False でスレッド間共有を許可
        db = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        db.row_factory = sqlite3.Row
        # 同時読み書きに強い WAL モードへ
        db.execute("PRAGMA journal_mode=WAL;")
        db.execute("PRAGMA foreign_keys = ON;")
        g._db = db
    return db

@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, "_db", None)
    if db is not None:
        db.close()

## ---------- 初期化 ----------
# def init_db():
#     db = get_db(); cur = db.cursor()
#     # 授業(何限)
#     cur.execute('''CREATE TABLE IF NOT EXISTS courses(
#         username TEXT NOT NULL,
#         day      TEXT NOT NULL,      -- '月'〜'金'
#         slot     INTEGER NOT NULL,   -- 1〜5
#         content  TEXT,
#         PRIMARY KEY(username,day,slot)
#     )''')
#     # カスタムコマ(時刻レンジ)
#     cur.execute('''CREATE TABLE IF NOT EXISTS custom_slots(
#         username   TEXT NOT NULL,
#         day        TEXT NOT NULL,    -- '月'〜'金'
#         start_time TEXT NOT NULL,    -- 'HH:MM'
#         end_time   TEXT NOT NULL,
#         content    TEXT,
#         PRIMARY KEY(username,day,start_time)
#     )''')
#     db.commit()
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
            content  TEXT
        )
    ''')
    cur.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_usr_day_slot
        ON courses(username, day, slot)
    ''')

    # --- custom_slots はそのまま ---
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

    # ユーザー情報とプロフィールを保存するテーブル
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            grade INTEGER,      -- 学年
            faculty TEXT,       -- 学部
            department TEXT,    -- 学科
            circles TEXT        -- サークル (JSON配列の文字列)
        )
    ''')

    # 募集情報を保存するテーブル
    # 既存テーブルを削除 (募集情報を自動生成する際はコメントアウト)
    #cur.execute('DROP TABLE IF EXISTS recruitments')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS recruitments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_username TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT,
            max_participants INTEGER DEFAULT 2,
            location TEXT,
            date TEXT NOT NULL,      -- (YYYY-MM-DD)
            day TEXT NOT NULL,      -- '月', '火' など
            slot INTEGER NOT NULL,  -- 1, 2, 3 など
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 参加申請を管理するテーブル
    cur.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recruitment_id INTEGER NOT NULL,
            applicant_username TEXT NOT NULL,
            status TEXT DEFAULT 'pending', -- pending, approved, rejected
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (recruitment_id) REFERENCES recruitments(id)
        )
    ''')

    db.commit(); db.close()


## ---------- 既定コマ API ----------
# @app.route("/courses", methods=["GET","POST","DELETE"])
# def courses():
#     db = get_db(); cur = db.cursor()
#     if request.method == "GET":
#         u = request.args.get("username","").strip()
#         cur.execute("SELECT day,slot,content FROM courses WHERE username=?", (u,))
#         return jsonify([dict(r) for r in cur.fetchall()])

#     data = request.get_json(); u = data.get("username","").strip()
#     if request.method == "POST":
#         cur.execute('''INSERT INTO courses(username,day,slot,content)
#                        VALUES(?,?,?,?)
#                        ON CONFLICT(username,day,slot)
#                        DO UPDATE SET content=excluded.content''',
#                     (u,data['day'],data['slot'],data.get('content','')))
#         db.commit(); return jsonify(success=True)

#     # DELETE
#     cur.execute("DELETE FROM courses WHERE username=? AND day=? AND slot=?",
#                 (u,data['day'],data['slot']))
#     db.commit(); return jsonify(success=True)
# ── 既定コマ API ──────────────────────────
@app.route("/courses", methods=["GET","POST","DELETE"])
def courses():
    db = get_db(); cur = db.cursor()

    if request.method == "GET":
        u = request.args.get("username","").strip()
        cur.execute("SELECT day,slot,content FROM courses WHERE username=?", (u,))
        return jsonify([dict(r) for r in cur.fetchall()])

    data = request.get_json();  u = data.get("username","").strip()

    if request.method == "POST":
        day  = data["day"]
        slot = int(data["slot"])
        content = data.get("content","")

        st, et = PERIOD_TIMES[slot]         
        cur.execute('''
            INSERT INTO courses(username, day, slot, start_time, end_time, content)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(username, day, slot)
            DO UPDATE SET content=excluded.content
        ''', (u, day, slot, st, et, content))
        db.commit()
        return jsonify(success=True)

    # DELETE はそのまま
    cur.execute("DELETE FROM courses WHERE username=? AND day=? AND slot=?",
                (u, data["day"], data["slot"]))
    db.commit()
    return jsonify(success=True)

## ---------- カスタムコマ API ----------
@app.route("/custom_slots", methods=["GET","POST","DELETE"])
def custom_slots():
    db = get_db(); cur = db.cursor()
    if request.method == "GET":
        u = request.args.get("username","").strip()
        cur.execute("SELECT day,start_time,end_time,content FROM custom_slots WHERE username=?", (u,))
        return jsonify([dict(r) for r in cur.fetchall()])

    data = request.get_json(); u = data.get("username","").strip()
    if request.method == "POST":
        cur.execute('''INSERT OR REPLACE INTO custom_slots(username,day,start_time,end_time,content)
                       VALUES(?,?,?,?,?)''',
                    (u,data['day'],data['start_time'],data['end_time'],data.get('content','')))
        db.commit(); return jsonify(success=True)

    # DELETE
    cur.execute("DELETE FROM custom_slots WHERE username=? AND day=? AND start_time=?",
                (u,data['day'],data['start_time']))
    db.commit(); return jsonify(success=True)

## ---------- マッチ API ----------
@app.route("/match", methods=["POST"])
def match():
    """
    body = {
      "username": "me",
      "fixed_slots": ["Mon 2","Wed 4", ...]
    }
    → [{username:"他人", slots:[{day,start,end,content}, ...]}, ...]
    """
    data = request.get_json()
    me   = data.get("username","")
    req  = data.get("fixed_slots",[])          # Mon 3 形式
    if not req:
        return jsonify([])

    # ① 固定コマを day/slot タプルに
    fixed = [tuple(s.split()) for s in req]     # ('Mon','3')
    fixed_jp = [(ENG2JP[d],int(slot)) for d,slot in fixed]

    db = get_db(); cur = db.cursor()
    # ② 他ユーザーの courses から一致を検索
    matches = {}
    for day_jp, slot in fixed_jp:
        cur.execute("""SELECT username, content
                       FROM courses
                       WHERE day=? AND slot=? AND username<>?""",
                    (day_jp, slot, me))
        for r in cur.fetchall():
            st,et = PERIOD_TIMES[slot]
            matches.setdefault(r['username'], []).append(
                {"day": day_jp, "start": st, "end": et, "content": r['content'] or ''}
            )

    # ③ custom_slots の時間レンジとも突合
    for day_jp, slot in fixed_jp:
        st_fixed, et_fixed = PERIOD_TIMES[slot]
        st_f = dt.datetime.strptime(st_fixed, "%H:%M").time()
        et_f = dt.datetime.strptime(et_fixed, "%H:%M").time()

        cur.execute("""SELECT username,start_time,end_time,content
                         FROM custom_slots
                         WHERE day=? AND username<>?""",
                    (day_jp, me))
        for r in cur.fetchall():
            st_c = dt.datetime.strptime(r['start_time'],"%H:%M").time()
            et_c = dt.datetime.strptime(r['end_time'],"%H:%M").time()
            # 重なればヒット
            if not (et_c <= st_f or st_c >= et_f):
                matches.setdefault(r['username'], []).append(
                    {"day": day_jp,
                     "start": r['start_time'],
                     "end"  : r['end_time'],
                     "content": r['content'] or ''}
                )

    # ④ 整形して返す
    result = [{"username":u, "slots":s} for u,s in matches.items()]
    return jsonify(result)

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
                json.dumps(data.get('circles', [])), # サークルはJSON文字列として保存
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
    
    try:
        # ユーザーを追加 (プロフィール項目は後で編集可能)
        db.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, password)
        )
        db.commit()
        return jsonify(success=True)
    except sqlite3.IntegrityError:
        # ユーザー名が既に存在
        return jsonify(success=False, message="そのユーザー名は既に使用されています"), 400

# パスワードをチェックしてログイン
@app.route("/login", methods=["POST"])
def login():
    db = get_db()
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    cur = db.execute("SELECT password FROM users WHERE username = ?", (username,))
    user_row = cur.fetchone()
    
    if user_row and user_row['password'] == password: # 本来はハッシュを比較
        return jsonify(success=True)
    else:
        return jsonify(success=False, message="ユーザー名またはパスワードが違います")

    return jsonify(success=True)

@app.route("/")
def home(): return "Coma‑Link backend running"

@app.route("/recruitments", methods=["POST"])
def create_recruitment():
    db = get_db()
    data = request.get_json()
    if not all(k in data for k in ['creator_username', 'title', 'date', 'day', 'slot']):
        return jsonify(success=False, message="必須項目が不足しています"), 400

    cur = db.execute('''
        INSERT INTO recruitments (creator_username, title, category, max_participants, location, date, day, slot)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['creator_username'],
        data['title'],
        data.get('category'),
        data.get('max_participants', 2),
        data.get('location'),
        data['date'],     # ▼▼▼ 追記 ▼▼▼
        data['day'],      
        data['slot']      
    ))
    db.commit()
    return jsonify(success=True, recruitment_id=cur.lastrowid)

@app.route("/recruitments", methods=["GET"])
def get_recruitments():
    db = get_db()
    # クエリパラメータでフィルタリング条件を受け取る
    # (例: /recruitments?category=スポーツ&start_after=2025-10-06T10:00:00)
    query = "SELECT * FROM recruitments WHERE 1=1"
    params = []
    
    multi_slots_query = []
    
    # 複数コマ検索 ('multi_slots') の処理
    if 'multi_slots' in request.args and request.args['multi_slots']:
        # "月-1,火-3,水-5" のような文字列をパース
        slot_pairs = request.args['multi_slots'].split(',')
        for pair in slot_pairs:
            parts = pair.split('-')
            if len(parts) == 2:
                day, slot = parts[0].strip(), parts[1].strip()
                if day and slot.isdigit():
                    multi_slots_query.append("(day = ? AND slot = ?)")
                    params.extend([day, int(slot)])
        
        if multi_slots_query:
            query += " AND (" + " OR ".join(multi_slots_query) + ")"

    # (カテゴリ、場所、単一の曜日/コマの絞り込み)
    # multi_slotsが指定されていない場合のみ、他の条件を適用
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

        if 'slot' in request.args:
            query += " AND slot = ?"
            params.append(request.args['slot'])

    cur = db.execute(query, params)
    recruitments = [dict(row) for row in cur.fetchall()]
    return jsonify(recruitments)

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
    # ここに本来は募集者への通知処理などを追加する
    return jsonify(success=True)

@app.route("/my_recruitments/applications", methods=["GET"])
def get_my_applications():
    db = get_db()
    username = request.args.get("username")
    if not username:
        return jsonify([]), 400

    # 自分が作成した募集(r)に参加申請(p)してきたユーザーの一覧を取得
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
    new_status = data.get("status") # 'approved' or 'rejected'
    if new_status not in ['approved', 'rejected']:
        return jsonify(success=False, message="無効なステータスです"), 400

    db.execute("UPDATE participants SET status = ? WHERE id = ?", (new_status, app_id))
    db.commit()
    return jsonify(success=True)

# ヒートマップ表示用API
@app.route("/heatmap", methods=["GET"])
def get_heatmap():
    db = get_db()
    
    # 基本クエリ: コマごとに募集数をカウント
    query = """
        SELECT r.day, r.slot, COUNT(r.id) as count
        FROM recruitments r
    """
    params = []
    
    # --- フィルタリング ---
    # フィルタ条件を格納するリスト
    filters = []
    
    # フィルタ用のJOIN (フィルタが指定された場合のみ users と JOIN)
    join_clause = ""
    
    if request.args.get('grade') or request.args.get('faculty') or request.args.get('circles'):
        join_clause = " JOIN users u ON r.creator_username = u.username "
    
    if request.args.get('grade'):
        filters.append(" u.grade = ? ")
        params.append(request.args.get('grade'))
        
    if request.args.get('faculty'):
        filters.append(" u.faculty = ? ")
        params.append(request.args.get('faculty'))

    # サークル (部分一致検索)
    if request.args.get('circles'):
        filters.append(" u.circles LIKE ? ")
        params.append(f"%{request.args.get('circles')}%") # '["スポーツ"]' などの検索

    # クエリの組み立て
    if filters:
        query += join_clause + " WHERE " + " AND ".join(filters)
        
    query += " GROUP BY r.day, r.slot "
    
    cur = db.execute(query, params)
    
    # { "月-1": 5, "火-3": 10 } のような形式で返す
    heatmap_data = {}
    for row in cur.fetchall():
        key = f"{row['day']}-{row['slot']}"
        heatmap_data[key] = row['count']
        
    return jsonify(heatmap_data)

# ---------- Run ----------
if __name__ == "__main__":
    with app.app_context():
        init_db()
        print("✔ DB ready :", DB_PATH)
    app.run(host="0.0.0.0", port=5000, debug=True)
