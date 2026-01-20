import os
import sys
import sqlite3
import psycopg2
from psycopg2 import IntegrityError
import random
import json
import argparse
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# --- 設定 (デフォルト値) ---
DB_PATH = "coma_link.db"
TARGET_DB_URL = os.environ.get("DATABASE_URL")
RANDOM_SEED = 42  # 再現性のため固定
DEFAULT_NUM_USERS = 30
DEFAULT_RANGE_DAYS = 14  # 前後2週間
SYLLABUS_FILE = "syllabus_data.json" # スクレイピングデータのファイル名
# ------------------------

# デフォルトの講義カタログ (シラバスデータがない場合に使用)
# (授業名, 推奨最小学年)
DEFAULT_COURSE_CATALOG = [
    # 1年生向け
    ("英語I", 1), ("第二外国語", 1), ("線形代数", 1), ("微分積分", 1), 
    ("プログラミング基礎", 1), ("体育実技", 1), ("法学入門", 1), ("経済学入門", 1),
    ("心理学概論", 1), ("物理学実験", 1),
    # 2年生向け
    ("データ構造とアルゴリズム", 2), ("Web工学", 2), ("確率統計", 2), 
    ("憲法", 2), ("ミクロ経済学", 2), ("電子回路", 2), ("有機化学", 2),
    # 3年生向け
    ("人工知能", 3), ("データベース論", 3), ("オペレーティングシステム", 3),
    ("ソフトウェア工学", 3), ("ゼミナールI", 3), ("機械学習", 3),
    # 4年生向け
    ("卒業研究", 4), ("ゼミナールII", 4), ("先端技術特論", 4)
]

FACULTIES = ['工学部', '情報理工学部', '文学部', '法学部', '経済学部', '理学部', '農学部', '芸術学部']
CIRCLES = ['テニス', 'サッカー', '軽音', 'プログラミング', '美術', '吹奏楽', 'ダンス', 'ボランティア', '茶道']
CATEGORIES = ['食事', '勉強', 'スポーツ', '雑談', '趣味', 'その他']
LOCATIONS = ['A-101', '図書館', '学食', 'カフェテリア', '体育館', '部室棟', '芝生広場', '駅前']
TITLES_BY_CAT = {
    '食事': ['ランチ行きませんか', '学食でご飯', 'ラーメン食べたい', 'カフェで休憩', 'お腹すいた'],
    '勉強': ['課題手伝って', 'テスト勉強', '図書館で自習', 'プログラミング教えます', '資格の勉強'],
    'スポーツ': ['バスケしよう', 'キャッチボール', 'テニス相手募集', 'ランニング', '卓球しよう'],
    '雑談': ['暇つぶし', '雑談しましょう', 'サークルの話', '就活の情報交換', '悩み相談'],
    '趣味': ['ゲームしよう', 'カラオケ', '映画の話', '推し活', '漫画貸します'],
    'その他': ['落とし物探して', 'ちょっと手伝って', '部室の掃除', 'アンケート協力']
}
DAYS_JP = ['月', '火', '水', '木', '金']

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
    """テーブル初期化"""
    print("テーブルを初期化します...")
    cur = conn.cursor()
    tables = ["participants", "recruitments", "courses", "users", "custom_slots"]
    for t in tables:
        if TARGET_DB_URL:
             cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
        else:
             cur.execute(f"DROP TABLE IF EXISTS {t}")
    
    # User
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
    # Courses
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
    # Custom Slots
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

    # Recruitments & Participants (Postgres/SQLite 分岐)
    if TARGET_DB_URL: 
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
    else:
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
    print("テーブル初期化完了。")

# --- 確率分布設定 ---
def get_weighted_slot_for_course(day_idx):
    """
    授業が入りやすい時間帯を返す
    day_idx: 0(月) - 4(金)
    """
    slots = [1, 2, 3, 4, 5, 6, 7, 8]
    # 基本: 1,2限と4,5限が多い。3限(昼)は授業なし。6限以降は少ない。
    weights = [30, 30, 0, 30, 30, 5, 2, 1] 

    # 月曜(0): 1限(index 0)の確率を下げる
    if day_idx == 0:
        weights[0] = 5 
    
    # 金曜(4): 午後(index 3,4,5...)の確率を下げる
    if day_idx == 4:
        weights[3] = 10
        weights[4] = 5
        weights[5] = 1

    return random.choices(slots, weights=weights, k=1)[0]

def get_weighted_slot_for_recruitment(day_idx):
    """
    募集がかかりやすい時間帯を返す
    """
    slots = [1, 2, 3, 4, 5, 6, 7, 8]
    # 基本: 昼休み(3)と放課後(6,7,8)が多い。授業中(1,2,4,5)は少なめ。
    weights = [5, 5, 50, 5, 5, 30, 30, 20]

    # 金曜(4): 午後〜夜にかけて募集激増
    if day_idx == 4:
        weights = [5, 5, 60, 10, 10, 50, 60, 50]

    return random.choices(slots, weights=weights, k=1)[0]

def load_course_catalog():
    """
    シラバスデータ(JSON)があれば読み込んでカタログを作成する。
    なければデフォルトのカタログを返す。
    """
    if os.path.exists(SYLLABUS_FILE):
        try:
            with open(SYLLABUS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # JSONからユニークな講義名を抽出
            # データ形式: [{"name": "...", "day": "...", "slot": ...}, ...]
            unique_names = sorted(list(set([item["name"] for item in data])))
            
            if unique_names:
                print(f"シラバスデータ({SYLLABUS_FILE})から {len(unique_names)} 件の講義を読み込みました。")
                
                # カタログ形式に変換: (講義名, 推奨学年)
                # シラバスには学年がないため、ランダムに割り振る
                dynamic_catalog = []
                for name in unique_names:
                    # 1〜4年をランダムに割り当て (低学年向けを少し多めに重み付け)
                    grade = random.choices([1, 2, 3, 4], weights=[40, 30, 20, 10])[0]
                    dynamic_catalog.append((name, grade))
                return dynamic_catalog
        except Exception as e:
            print(f"シラバスデータの読み込みに失敗しました: {e}")
            print("デフォルトのカタログを使用します。")
    else:
        print(f"シラバスデータ({SYLLABUS_FILE})が見つかりません。")
        print("デフォルトのカタログを使用します。")
        
    return DEFAULT_COURSE_CATALOG

def insert_demo_data(conn, num_users, days_range, num_guests):
    print(f"--- データ投入開始 (Users: {num_users}, Guests: {num_guests}, Range: ±{days_range} days) ---")
    random.seed(RANDOM_SEED)
    cur = conn.cursor()
    
    # 講義カタログの準備
    course_catalog = load_course_catalog()
    
    # 1. ユーザー生成
    all_users = []
    
    # (A) 一般デモユーザー
    common_hash = generate_password_hash("password")
    for i in range(num_users):
        u = f"demo_user_{i+1}"
        grade = random.randint(1, 4)
        all_users.append({"u": u, "g": grade, "pass": "password"})
        
        execute_query(cur, 
            "INSERT INTO users (username, password, grade, faculty, department, circles) VALUES (?,?,?,?,?,?)",
            (u, common_hash, grade, random.choice(FACULTIES), "デモ学科", json.dumps(random.sample(CIRCLES, random.randint(0, 3))))
        )

    # (B) ゲスト（聴衆）用ユーザー
    if num_guests > 0:
        print(f"ゲストアカウントを {num_guests} 件生成します...")
        guest_credentials = []
        guest_hash = generate_password_hash("guest1234") # 共通パスワード
        for i in range(num_guests):
            u = f"guest_{i+1}"
            grade = random.randint(1, 4)
            pass_clear = "guest1234"
            all_users.append({"u": u, "g": grade, "pass": pass_clear})
            guest_credentials.append((u, pass_clear))
            
            try:
                execute_query(cur,
                    "INSERT INTO users (username, password, grade, faculty, department, circles) VALUES (?,?,?,?,?,?)",
                    (u, guest_hash, grade, "ゲスト学部", "体験学科", json.dumps([]))
                )
            except (sqlite3.IntegrityError, IntegrityError):
                pass # 既にいたらスキップ

    # 2. 時間割生成 (学年と曜日の傾向を考慮)
    print("時間割を生成中...")
    for user_obj in all_users:
        username = user_obj["u"]
        grade = user_obj["g"]
        
        # 自分の学年以下の授業のみ候補にする
        available_courses = [c[0] for c in course_catalog if c[1] <= grade]
        if not available_courses: available_courses = ["一般教養"]

        # 週に8〜14コマ程度
        num_courses = random.randint(8, 14)
        slots_taken = set()
        
        for _ in range(num_courses * 2): # 試行回数多めにして衝突回避
            if len(slots_taken) >= num_courses: break
            
            day_idx = random.randint(0, 4) # 0:月 - 4:金
            day_str = DAYS_JP[day_idx]
            slot = get_weighted_slot_for_course(day_idx)
            
            if slot == 3: continue # 昼休みは授業なし
            
            if (day_str, slot) not in slots_taken:
                content = random.choice(available_courses)
                slots_taken.add((day_str, slot))
                execute_query(cur,
                    "INSERT INTO courses (username, day, slot, start_time, end_time, content) VALUES (?,?,?,?,?,?)",
                    (username, day_str, slot, "00:00", "00:00", content)
                )

    # 3. 募集生成 (日時・傾向を考慮)
    print("募集を生成中...")
    recruitment_ids = []
    today = datetime.now()
    
    # 募集の数をユーザー数に応じて調整 (ユーザーあたり平均 0.5〜1件/日 程度)
    total_recruitments = int(num_users * days_range * 0.8) 
    
    insert_sql = """
        INSERT INTO recruitments 
        (creator_username, title, category, max_participants, location, date, day, start_slot, end_slot) 
        VALUES (?,?,?,?,?,?,?,?,?)
    """
    
    if TARGET_DB_URL: insert_sql += " RETURNING id"

    for _ in range(total_recruitments):
        creator = random.choice(all_users)["u"]
        
        # 日付決定 (今日を中心に前後 days_range)
        offset = random.randint(-days_range, days_range)
        target_date = today + timedelta(days=offset)
        
        # 土日(5,6)はスキップして平日に寄せる（大学アプリなので）
        if target_date.weekday() >= 5: continue
        
        date_str = target_date.strftime("%Y-%m-%d")
        day_idx = target_date.weekday()
        day_jp = DAYS_JP[day_idx]
        
        # カテゴリ決定
        category = random.choice(CATEGORIES)
        title = random.choice(TITLES_BY_CAT.get(category, ['募集中']))
        location = random.choice(LOCATIONS)
        max_part = random.randint(2, 6)
        
        # 時間帯決定 (重みづけ使用)
        start_slot = get_weighted_slot_for_recruitment(day_idx)
        
        # 期間 (1〜2コマ)
        duration = 1 if start_slot == 3 else random.choice([1, 1, 2]) # 昼休みは1コマ
        end_slot = min(start_slot + duration - 1, 8)
        if start_slot == 2 and end_slot == 3: end_slot = 2 # 2限から昼休み跨ぎはしない

        params = (creator, title, category, max_part, location, date_str, day_jp, start_slot, end_slot)
        
        # ▼▼▼ 修正箇所: Postgresなら ? を %s に置換 ▼▼▼
        if TARGET_DB_URL:
            cur.execute(insert_sql.replace('?', '%s'), params)
            recruitment_ids.append(cur.fetchone()[0])
        else:
            cur.execute(insert_sql, params)
            recruitment_ids.append(cur.lastrowid)

    # 4. 参加データ生成
    print("参加申請を生成中...")
    for rec_id in recruitment_ids:
        # 閑散を作るため、参加者が0人の募集も作る
        if random.random() < 0.3: continue # 30%は参加者なし

        num_applicants = random.randint(1, 3)
        # 自分以外から選ぶ
        potential_applicants = [u["u"] for u in all_users] # 簡易実装
        applicants = random.sample(potential_applicants, min(len(potential_applicants), num_applicants))
        
        for app_user in applicants:
            status = random.choice(['pending', 'approved', 'approved', 'rejected']) # 承認済み多め
            execute_query(cur,
                "INSERT INTO participants (recruitment_id, applicant_username, status) VALUES (?,?,?)",
                (rec_id, app_user, status)
            )

    conn.commit()
    print("\n=== データ生成完了 ===")
    print(f"デモユーザー数: {num_users} (Pass: password)")
    if 'guest_credentials' in locals() and guest_credentials:
        print("\n【ゲスト用アカウント（配布用）】")
        print("------------------------------------------------")
        for u, p in guest_credentials:
            print(f"ID: {u:<12} / Pass: {p}")
        print("------------------------------------------------")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coma-Link Database Manager (v2)")
    parser.add_argument("--init", action="store_true", help="テーブル初期化（全データ削除）")
    parser.add_argument("--demo", action="store_true", help="データ生成実行")
    parser.add_argument("--users", type=int, default=DEFAULT_NUM_USERS, help=f"生成するデモユーザー数 (Default: {DEFAULT_NUM_USERS})")
    parser.add_argument("--guests", type=int, default=0, help="生成するゲスト(聴衆)用アカウント数")
    parser.add_argument("--range", type=int, default=DEFAULT_RANGE_DAYS, help=f"募集を生成する期間の日数± (Default: {DEFAULT_RANGE_DAYS})")
    
    args = parser.parse_args()

    if not args.init and not args.demo:
        print("オプションを指定してください: --init (初期化), --demo (データ投入)")
        sys.exit(1)

    conn = get_connection()
    try:
        if args.init:
            init_tables(conn)
        if args.demo:
            insert_demo_data(conn, args.users, args.range, args.guests)
    finally:
        conn.close()