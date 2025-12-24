import requests
from bs4 import BeautifulSoup
import json
import re
import time

# ターゲットURL
URLS = [
    "https://kyoumu.office.uec.ac.jp/syllabus/2025/GakkiIchiran_31_0.html",
    "https://kyoumu.office.uec.ac.jp/syllabus/2025/GakkiIchiran_33_0.html"
]

OUTPUT_FILE = "syllabus_data.json"

def parse_day_slot(text):
    """
    '月曜1限' や 'Tue 2' などの文字列から (曜日, コマ番号) のリストを返す
    例: "月1" -> [("月", 1)]
        "火1,2" -> [("火", 1), ("火", 2)]
    """
    result = []
    
    # 曜日の変換マップ
    day_map = {'月': '月', '火': '火', '水': '水', '木': '木', '金': '金', '土': '土', '日': '日',
               'Mon': '月', 'Tue': '火', 'Wed': '水', 'Thu': '木', 'Fri': '金', 'Sat': '土', 'Sun': '日'}
    
    # 正規表現で「曜日」と「数字」を探す
    # パターン: 曜日文字 + 任意の文字 + 数字
    # ※ 実際のHTMLに合わせて調整が必要な場合があります
    text = text.strip()
    
    # 曜日を特定
    found_day = None
    for k, v in day_map.items():
        if k in text:
            found_day = v
            break
            
    if not found_day:
        return []

    # 数字(コマ)を全て抽出
    slots = re.findall(r'\d+', text)
    
    for s in slots:
        slot_num = int(s)
        # Coma-Linkは8限まで対応
        if 1 <= slot_num <= 8:
            result.append((found_day, slot_num))
            
    return result

def scrape_syllabus():
    all_courses = []
    
    print("シラバスデータの取得を開始します...")

    for url in URLS:
        print(f"Fetching: {url}")
        try:
            # サーバー負荷軽減のため少し待機
            time.sleep(1)
            
            res = requests.get(url)
            res.encoding = res.apparent_encoding # 文字化け対策
            soup = BeautifulSoup(res.text, 'html.parser')

            # テーブルを探す (多くの場合、class="list" などのテーブルに入っている)
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                if not rows: continue

                # ヘッダーを確認して列インデックスを特定する
                header_cells = rows[0].find_all(['th', 'td'])
                headers = [c.get_text(strip=True) for c in header_cells]
                
                name_idx = -1
                time_idx = -1
                
                # 列名からインデックスを探す (表記ゆれに対応)
                for i, h in enumerate(headers):
                    if '科目' in h or 'Course' in h:
                        name_idx = i
                    elif '曜' in h or '時限' in h or 'Day' in h or 'Period' in h:
                        time_idx = i
                
                if name_idx == -1 or time_idx == -1:
                    continue # このテーブルは対象外

                # データ行を解析
                for row in rows[1:]:
                    cols = row.find_all('td')
                    if len(cols) <= max(name_idx, time_idx):
                        continue
                        
                    course_name = cols[name_idx].get_text(strip=True)
                    time_text = cols[time_idx].get_text(strip=True)
                    
                    # 曜日・時限をパース
                    day_slots = parse_day_slot(time_text)
                    
                    for day, slot in day_slots:
                        all_courses.append({
                            "name": course_name,
                            "day": day,
                            "slot": slot
                        })
                        
        except Exception as e:
            print(f"エラーが発生しました ({url}): {e}")

    # 重複排除 (同じ授業が複数リストにある場合など)
    unique_courses = []
    seen = set()
    for c in all_courses:
        key = (c['name'], c['day'], c['slot'])
        if key not in seen:
            seen.add(key)
            unique_courses.append(c)

    print(f"合計 {len(unique_courses)} 件の講義データを抽出しました。")
    
    # JSON保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(unique_courses, f, ensure_ascii=False, indent=2)
    print(f"データを {OUTPUT_FILE} に保存しました。")

if __name__ == "__main__":
    scrape_syllabus()