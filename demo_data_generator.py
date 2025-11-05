import sqlite3
import random
import json
from datetime import datetime, timedelta

# ▼▼▼ 修正点 1: 乱数シード値の指定 ▼▼▼
RANDOM_SEED = 12345 # この値を変更すると、生成されるデータが変わります
random.seed(RANDOM_SEED)
print(f"--- 乱数シード値 {RANDOM_SEED} を使用します ---")
# ▲▲▲ 修正点 1 ▲▲▲

DB_PATH = "coma_link.db"

# --- 設定 ---
NUM_USERS = 500       # 生成するダミーユーザー数
NUM_RECRUITMENTS = 300 # 生成するダミー募集数
# --- ---

# ランダムデータ用のサンプル (変更なし)
FACULTIES = ['工学部', '文学部', '法学部', '経済学部', '理学部', '教育学部', '薬学部']
DEPARTMENTS = ['機械工学科', '情報工学科', '日本文学科', '法学科', '経済学科', '物理学科', '化学科']
CIRCLES = ['テニス', 'サッカー', 'バスケ', '軽音楽', 'プログラミング', '美術', 'ボランティア']
CATEGORIES = ['勉強', '食事', 'スポーツ', '趣味', '雑談', '移動']
LOCATIONS = ['A-101', '図書館', '学食', 'カフェテリア', '体育館', '部室棟']
TITLES = [
    '一緒にランチしませんか？', '微積の課題手伝ってください', '空きコマで雑談',
    'キャッチボール相手募集', '今から学食行く人', '〇〇の過去問情報交換'
]
DAYS = ['月', '火', '水', '木', '金']

def create_demo_users(db):
    """ダミーユーザーを生成する"""
    print(f"--- {NUM_USERS}人のユーザーを生成します ---")
    users_to_insert = []
    usernames_list = [] # ▼▼▼ 修正点 2: 返却用のリストを分離 ▼▼▼

    for i in range(NUM_USERS):
        username = f"demo_user_{i+1}"
        usernames_list.append(username) # 生成する全ユーザー名をまずリストに追加
        
        password = "password"
        grade = random.randint(1, 4)
        faculty = random.choice(FACULTIES)
        department = random.choice(DEPARTMENTS)
        num_circles = random.randint(0, 2)
        user_circles = json.dumps(random.sample(CIRCLES, num_circles))
        
        users_to_insert.append((username, password, grade, faculty, department, user_circles))

    try:
        # users テーブルに一括挿入 (既に存在する場合は DO NOTHING)
        db.executemany(
            """
            INSERT INTO users (username, password, grade, faculty, department, circles)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO NOTHING
            """,
            users_to_insert
        )
        db.commit()
        print("ユーザーの生成/確認が完了しました。")
        
        # ▼▼▼ 修正点 2: DBへの挿入成否に関わらず、生成したユーザー名のリストを返す ▼▼▼
        return usernames_list
        
    except sqlite3.Error as e:
        print(f"ユーザー生成中にエラーが発生しました: {e}")
        return [] # エラー時のみ空リストを返す

def create_demo_recruitments(db, usernames):
    """ダミー募集を生成する"""
    if not usernames:
        # ▼▼▼ 修正点 2: このエラーが出なくなります ▼▼▼
        print("募集を作成するユーザーがいません。")
        return
        
    print(f"--- {NUM_RECRUITMENTS}件の募集を生成します ---")
    recruitments = []
    today = datetime.now()

    for _ in range(NUM_RECRUITMENTS):
        creator = random.choice(usernames)
        title = random.choice(TITLES)
        category = random.choice(CATEGORIES)
        location = random.choice(LOCATIONS)
        max_participants = random.randint(2, 10)
        
        # 日付 (今日から前後1週間) ※要件を満たしているため変更なし
        date_offset = random.randint(-7, 7)
        date = (today + timedelta(days=date_offset)).strftime("%Y-%m-%d")
        
        # 曜日とコマ
        day = random.choice(DAYS)
        slot = random.randint(1, 7) # 1〜7限
        
        recruitments.append((
            creator, title, category, max_participants, location, date, day, slot
        ))

    try:
        # recruitments テーブルに一括挿入
        db.executemany(
            """
            INSERT INTO recruitments (creator_username, title, category, max_participants, location, date, day, slot)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            recruitments
        )
        db.commit()
        print("募集の生成が完了しました。")
        
    except sqlite3.Error as e:
        print(f"募集生成中にエラーが発生しました: {e}")


def main():
    try:
        db = sqlite3.connect(DB_PATH)
        print(f"{DB_PATH} に接続しました。")
        
        # 既存の募集と参加者を削除 (デモデータを再生成するため)
        print("既存の募集・参加者データをクリアします...")
        db.execute("DELETE FROM participants")
        db.execute("DELETE FROM recruitments")
        # ユーザーは削除しない (ON CONFLICTで対応)
        db.commit()
        
        # 1. ダミーユーザーを生成 (必ずユーザー名のリストが返ってくる)
        usernames = create_demo_users(db)
        
        # 2. ダミー募集を生成
        create_demo_recruitments(db, usernames)
        
    except sqlite3.Error as e:
        print(f"データベースエラー: {e}")
    finally:
        if db:
            db.close()
            print(f"{DB_PATH} への接続を閉じました。")

if __name__ == "__main__":
    main()