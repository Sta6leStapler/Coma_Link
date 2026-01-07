import os
import sys
import sqlite3
import psycopg2
import random
import json
import argparse
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# --- 設定 ---
TARGET_DB_URL = os.environ.get("DATABASE_URL") 
DB_PATH = "coma_link.db"
RANDOM_SEED = 12345
NUM_USERS = 50
NUM_RECRUITMENTS = 300
# ------------

# 既存のデータセット定義 (変更なし)
FACULTIES = ['工学部', '情報理工学部', '文学部', '法学部', '経済学部', '理学部', '農学部', '芸術学部']
CIRCLES = ['テニス', 'サッカー', '軽音', 'プログラミング', '美術', '吹奏楽', 'ダンス', 'ボランティア', '茶道']
CATEGORIES = ['食事', '勉強', 'スポーツ', '雑談', '趣味', 'その他']
LOCATIONS = ['A-101', '図書館', '学食', 'カフェテリア', '体育館', '部室棟', '芝生広場', '駅前']
TITLES_BY_CAT = {
    '食事': ['ランチ行きませんか', '学食でご飯', 'ラーメン食べたい', 'カフェで休憩'],
    '勉強': ['課題手伝って', 'テスト勉強', '図書館で自習', 'プログラミング教えます'],
    'スポーツ': ['バスケしよう', 'キャッチボール', 'テニス相手募集', 'ランニング'],
    '雑談': ['暇つぶし', '雑談しましょう', 'サークルの話', '就活の情報交換'],
    '趣味': ['ゲームしよう', 'カラオケ', '映画の話', '推し活'],
    'その他': ['落とし物探して', 'ちょっと手伝って', '部室の掃除']
}
DAYS = ['月', '火', '水', '木', '金']
COURSE_CONTENTS = ['Web工学', 'データベース', '人工知能', '線形代数', '心理学', '英語', '経済学入門', '物理学', '憲法', 'プログラミング基礎']

def get_connection():
    if TARGET_DB_URL and TARGET_DB_URL.startswith("postgres"):
        print(f"Connecting to PostgreSQL...")
        return psycopg2.connect(TARGET_DB_URL)
    else:
        print(f"Connecting to SQLite: {DB_PATH}")
        return sqlite3.connect(DB_PATH)

def execute_query(cur, query, params=()):
    if TARGET_DB_URL and TARGET_DB_URL.startswith("postgres"):
        query = query.replace('?', '%s')
    cur.execute(query, params)

def init_tables(conn):
    """テーブルを全削除して再作成する"""
    print("テーブルを初期化します...")
    cur = conn.cursor()
    tables = ["participants", "recruitments", "courses", "users", "custom_slots"]
    for t in tables:
        if TARGET_DB_URL:
             cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
        else:
             cur.execute(f"DROP TABLE IF EXISTS {t}")
    
    # テーブル作成
    execute_query(cur, '''
        CREATE TABLE users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            grade INTEGER,
            faculty TEXT,
            department TEXT,
            circles TEXT
        )
    ''')
    execute_query(cur, '''
        CREATE TABLE courses(
            username TEXT NOT NULL,
            day      TEXT NOT NULL,
            slot     INTEGER NOT NULL,
            start_time TEXT,
            end_time   TEXT,
            content  TEXT,
            PRIMARY KEY(username, day, slot)
        )
    ''')
    execute_query(cur, '''
        CREATE TABLE custom_slots(
            username   TEXT NOT NULL,
            day        TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time   TEXT NOT NULL,
            content    TEXT,
            PRIMARY KEY(username, day, start_time)
        )
    ''')

    if TARGET_DB_URL: # Postgres
        cur.execute('''
            CREATE TABLE recruitments (
                id SERIAL PRIMARY KEY,
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
        cur.execute('''
            CREATE TABLE participants (
                id SERIAL PRIMARY KEY,
                recruitment_id INTEGER NOT NULL,
                applicant_username TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (recruitment_id) REFERENCES recruitments(id)
            )
        ''')
    else: # SQLite
        cur.execute('''
            CREATE TABLE recruitments (
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
        cur.execute('''
            CREATE TABLE participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recruitment_id INTEGER NOT NULL,
                applicant_username TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (recruitment_id) REFERENCES recruitments(id)
            )
        ''')
    conn.commit()
    print("テーブル初期化完了。データは空です。")

def insert_demo_data(conn):
    """ダミーデータを投入する"""
    print(f"--- ダミーデータを投入します (Seed: {RANDOM_SEED}) ---")
    random.seed(RANDOM_SEED)
    cur = conn.cursor()
    
    # ユーザー
    print(f"ユーザー生成 ({NUM_USERS}人)...")
    usernames = []
    common_hash = generate_password_hash("password")
    for i in range(NUM_USERS):
        u = f"demo_user_{i+1}"
        usernames.append(u)
        grade = random.randint(1, 4)
        faculty = random.choice(FACULTIES)
        my_circles = random.sample(CIRCLES, random.randint(0, 3))
        execute_query(cur, 
            "INSERT INTO users (username, password, grade, faculty, department, circles) VALUES (?,?,?,?,?,?)",
            (u, common_hash, grade, faculty, "デモ学科", json.dumps(my_circles))
        )

    # 時間割
    print("時間割生成...")
    for u in usernames:
        num_courses = random.randint(8, 15)
        slots = set()
        while len(slots) < num_courses:
            d = random.choice(DAYS)
            s = random.randint(1, 8) 
            slots.add((d, s))
        for d, s in slots:
            content = random.choice(COURSE_CONTENTS)
            execute_query(cur,
                "INSERT INTO courses (username, day, slot, start_time, end_time, content) VALUES (?,?,?,?,?,?)",
                (u, d, s, "00:00", "00:00", content)
            )

    # 募集
    print(f"募集生成 ({NUM_RECRUITMENTS}件)...")
    recruitment_ids = []
    today = datetime.now()
    insert_sql = """
        INSERT INTO recruitments 
        (creator_username, title, category, max_participants, location, date, day, start_slot, end_slot) 
        VALUES (?,?,?,?,?,?,?,?,?)
    """
    for _ in range(NUM_RECRUITMENTS):
        creator = random.choice(usernames)
        category = random.choice(CATEGORIES)
        title = random.choice(TITLES_BY_CAT.get(category, ['募集中']))
        location = random.choice(LOCATIONS)
        max_participants = random.randint(2, 6)
        
        # 今日から前後1週間
        date_offset = random.randint(-7, 7)
        target_date = today + timedelta(days=date_offset)
        date_str = target_date.strftime("%Y-%m-%d")
        day_jp_map = ['月', '火', '水', '木', '金', '土', '日']
        day = day_jp_map[target_date.weekday()]
        
        start_slot = random.randint(1, 8)
        duration = random.choices([1, 2, 3], weights=[70, 20, 10])[0]
        end_slot = min(start_slot + duration - 1, 8)
        
        if TARGET_DB_URL: # Postgres
            cur.execute(insert_sql.replace('?', '%s') + " RETURNING id", (
                creator, title, category, max_participants, location, date_str, day, start_slot, end_slot
            ))
            recruitment_ids.append(cur.fetchone()[0])
        else: # SQLite
            cur.execute(insert_sql, (
                creator, title, category, max_participants, location, date_str, day, start_slot, end_slot
            ))
            recruitment_ids.append(cur.lastrowid)

    # 参加
    print("参加データ生成...")
    for rec_id in recruitment_ids:
        num_applicants = random.randint(0, 4)
        if num_applicants == 0: continue
        applicants = random.sample(usernames, num_applicants)
        for app_user in applicants:
            status = random.choice(['pending', 'approved', 'rejected'])
            execute_query(cur,
                "INSERT INTO participants (recruitment_id, applicant_username, status) VALUES (?,?,?)",
                (rec_id, app_user, status)
            )

    conn.commit()
    print("完了しました。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coma-Link Database Manager")
    parser.add_argument("--init", action="store_true", help="テーブルを初期化して空にする（データ全削除）")
    parser.add_argument("--demo", action="store_true", help="ダミーデータを投入する（--initと併用推奨）")
    args = parser.parse_args()

    if not args.init and not args.demo:
        print("オプションを指定してください: --init (初期化), --demo (データ投入)")
        print("例: python manage_db.py --init --demo (リセットしてダミー投入)")
        sys.exit(1)

    conn = get_connection()
    try:
        if args.init:
            init_tables(conn)
        if args.demo:
            insert_demo_data(conn)
    finally:
        conn.close()