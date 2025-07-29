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
CORS(app)                        # フロントを file:// で開いても OK
DB_PATH = os.path.join(app.root_path, "coma_link.db")

## ---------- 共通 ----------
JP2ENG = {'月':'Mon','火':'Tue','水':'Wed','木':'Thu','金':'Fri'}
ENG2JP = {v:k for k,v in JP2ENG.items()}
PERIOD_TIMES = {
    1:('09:00','10:30'),
    2:('10:40','12:10'),
    3:('13:00','14:30'),
    4:('14:40','16:10'),
    5:('16:15','17:45')
}

def get_db():
    db = getattr(g, "_db", None)
    if db is None:
        db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
        g._db = db
    return db

@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, "_db", None)
    if db is not None:
        db.close()

## ---------- 初期化 ----------
def init_db():
    db = get_db(); cur = db.cursor()
    # 授業(何限)
    cur.execute('''CREATE TABLE IF NOT EXISTS courses(
        username TEXT NOT NULL,
        day      TEXT NOT NULL,      -- '月'〜'金'
        slot     INTEGER NOT NULL,   -- 1〜5
        content  TEXT,
        PRIMARY KEY(username,day,slot)
    )''')
    # カスタムコマ(時刻レンジ)
    cur.execute('''CREATE TABLE IF NOT EXISTS custom_slots(
        username   TEXT NOT NULL,
        day        TEXT NOT NULL,    -- '月'〜'金'
        start_time TEXT NOT NULL,    -- 'HH:MM'
        end_time   TEXT NOT NULL,
        content    TEXT,
        PRIMARY KEY(username,day,start_time)
    )''')
    db.commit()

## ---------- 既定コマ API ----------
@app.route("/courses", methods=["GET","POST","DELETE"])
def courses():
    db = get_db(); cur = db.cursor()
    if request.method == "GET":
        u = request.args.get("username","").strip()
        cur.execute("SELECT day,slot,content FROM courses WHERE username=?", (u,))
        return jsonify([dict(r) for r in cur.fetchall()])

    data = request.get_json(); u = data.get("username","").strip()
    if request.method == "POST":
        cur.execute('''INSERT INTO courses(username,day,slot,content)
                       VALUES(?,?,?,?)
                       ON CONFLICT(username,day,slot)
                       DO UPDATE SET content=excluded.content''',
                    (u,data['day'],data['slot'],data.get('content','')))
        db.commit(); return jsonify(success=True)

    # DELETE
    cur.execute("DELETE FROM courses WHERE username=? AND day=? AND slot=?",
                (u,data['day'],data['slot']))
    db.commit(); return jsonify(success=True)

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

## ---------- 簡易ログイン (dummy) ----------
@app.route("/login", methods=["POST"])
def login():
    # 前端は localStorage に username を保持するだけなので
    # バックでは特に認証せず echo
    return jsonify(success=True)

@app.route("/")
def home(): return "Coma‑Link backend running"

# ---------- Run ----------
if __name__ == "__main__":
    with app.app_context():
        init_db()
        print("✔ DB ready :", DB_PATH)
    app.run(host="0.0.0.0", port=5000, debug=True)
