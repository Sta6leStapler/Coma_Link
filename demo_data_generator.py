import sqlite3
import random
import json
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# --- 設定 ---
DB_PATH = "coma_link.db"
SYLLABUS_FILE = "syllabus_data.json" # スクレイピングしたファイル
RANDOM_SEED = 12345
NUM_USERS = 50           
NUM_RECRUITMENTS = 300   
# ------------

random.seed(RANDOM_SEED)

# 固定データセット
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

def load_syllabus_data():
    """シラバスJSONを読み込む。ファイルがない場合はダミーを返す"""
    if not os.path.exists(SYLLABUS_FILE):
        print(f"警告: {SYLLABUS_FILE} が見つかりません。スクレイピングを行ってください。")
        print("簡易ダミーデータを使用します。")
        dummy_courses = []
        contents = ['Web工学', 'データベース', '人工知能', '線形代数', '心理学', '英語']
        for c in contents:
            for d in DAYS:
                for s in range(1, 6):
                    dummy_courses.append({"name": c, "day": d, "slot": s})
        return dummy_courses

    with open(SYLLABUS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def init_db_structure(db):
    """DB構造を初期化する"""
    cur = db.cursor()
    
    # ユーザーテーブル
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

    # 授業テーブル
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

    # 募集テーブル
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

    # 参加者テーブル
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
    db.commit()

def create_demo_data():
    print(f"--- デモデータ生成開始 (Seed: {RANDOM_SEED}) ---")
    
    # 1. 講義データのロード
    all_syllabus_courses = load_syllabus_data()
    print(f"使用する講義データプール: {len(all_syllabus_courses)} 件")

    try:
        db = sqlite3.connect(DB_PATH)
        cur = db.cursor()
        
        # 2. クリーンアップ
        db.execute("DROP TABLE IF EXISTS participants")
        db.execute("DROP TABLE IF EXISTS recruitments")
        db.execute("DROP TABLE IF EXISTS courses")
        db.execute("DROP TABLE IF EXISTS users")
        db.execute("DROP TABLE IF EXISTS custom_slots")
        
        init_db_structure(db)
        print("テーブル初期化完了")

        # 3. ユーザー生成
        # 3. ユーザー生成
        print(f"ユーザー生成中 ({NUM_USERS}人)...")
        usernames = []
        users_data = []
        
        # 全員共通のハッシュ済みパスワードを計算しておく（高速化のため）
        # デモユーザーのパスワードは全員 "password" とします
        common_password_hash = generate_password_hash("password") # ← 追加

        for i in range(NUM_USERS):
            u = f"demo_user_{i+1}"
            usernames.append(u)
            grade = random.randint(1, 4)
            faculty = random.choice(FACULTIES)
            my_circles = random.sample(CIRCLES, random.randint(0, 3))
            
            users_data.append((
                u, 
                common_password_hash, # ← "password" から変更
                grade, faculty, "デモ学科", json.dumps(my_circles)
            ))
        
        cur.executemany(
            "INSERT INTO users (username, password, grade, faculty, department, circles) VALUES (?,?,?,?,?,?)",
            users_data
        )

        # 4. 授業(時間割)生成 - 被りなしロジック適用
        print("時間割生成中(リアルデータ使用)...")
        courses_to_insert = []
        
        for u in usernames:
            # 1人あたり 8〜14コマ履修させる
            target_course_count = random.randint(8, 14)
            
            # このユーザーが既に埋まっているコマ (day, slot) を記録するセット
            occupied_slots = set()
            user_courses = []
            
            # ランダムに講義を選びながら、空いているコマなら登録する
            # 無限ループ防止のため、試行回数制限を設ける
            attempts = 0
            while len(user_courses) < target_course_count and attempts < 100:
                candidate = random.choice(all_syllabus_courses)
                day = candidate['day']
                slot = candidate['slot']
                
                # 既にそのコマに授業があればスキップ
                if (day, slot) in occupied_slots:
                    attempts += 1
                    continue
                
                # 登録
                occupied_slots.add((day, slot))
                user_courses.append((
                    u, day, slot, "00:00", "00:00", candidate['name']
                ))
            
            courses_to_insert.extend(user_courses)
        
        cur.executemany(
            "INSERT INTO courses (username, day, slot, start_time, end_time, content) VALUES (?,?,?,?,?,?)",
            courses_to_insert
        )

        # 5. 募集生成 (前回と同じ)
        print(f"募集生成中 ({NUM_RECRUITMENTS}件)...")
        recruitment_ids = []
        today = datetime.now()
        
        insert_rec_sql = """
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
            
            date_offset = random.randint(-14, 14)
            target_date = today + timedelta(days=date_offset)
            date_str = target_date.strftime("%Y-%m-%d")
            
            day_jp_map = ['月', '火', '水', '木', '金', '土', '日']
            day = day_jp_map[target_date.weekday()]
            
            start_slot = random.randint(1, 8)
            duration = random.choices([1, 2, 3], weights=[70, 20, 10])[0]
            end_slot = min(start_slot + duration - 1, 8)
            
            cur.execute(insert_rec_sql, (
                creator, title, category, max_participants, location, date_str, day, start_slot, end_slot
            ))
            recruitment_ids.append(cur.lastrowid)

        # 6. 参加申請生成 (前回と同じ)
        print("参加データ生成中...")
        participants_data = []
        for rec_id in recruitment_ids:
            num_applicants = random.randint(0, 4)
            if num_applicants == 0: continue
            
            applicants = random.sample(usernames, num_applicants)
            for app_user in applicants:
                status = random.choice(['pending', 'approved', 'rejected'])
                participants_data.append((rec_id, app_user, status))
        
        cur.executemany(
            "INSERT INTO participants (recruitment_id, applicant_username, status) VALUES (?,?,?)",
            participants_data
        )

        db.commit()
        print("完了: coma_link.db にデータを生成しました。")

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    create_demo_data()