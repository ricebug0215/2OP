import requests
import sqlite3
import json

BASE_URL = "https://api.tcgdex.net/v2/zh-tw"

def force_fetch_energy():
    conn = sqlite3.connect('pokemon_tcg_full.db')
    cursor = conn.cursor()

    print("🚀 正在鎖定『能量分類』進行精準抓取...")
    
    try:
        # 直接從分類接口抓取能量清單
        # 這個 API 會回傳所有被標記為 Energy 的卡片
        res = requests.get(f"{BASE_URL}/categories/Energy").json()
        energy_cards = res.get('cards', [])
    except Exception as e:
        print(f"❌ 連線失敗: {e}")
        return

    print(f"找到共 {len(energy_cards)} 張能量卡候補，開始深度處理...")

    count_added = 0
    for i, summary in enumerate(energy_cards):
        card_id = summary.get('id')
        
        # 獲取詳細資訊
        detail_res = requests.get(f"{BASE_URL}/cards/{card_id}")
        if detail_res.status_code != 200: continue
        
        card = detail_res.json()
        card_name = card.get('name', '')
        
        # --- 判斷邏輯 ---
        # 1. 如果名字有「基本」或是它是 sve 系列 (朱紫基本能量)，標記為 Basic
        # 2. 如果它有描述文字 (description)，通常就是特殊能量，標記為 Special
        is_basic = "基本" in card_name or card_id.startswith('sve-')
        sub_cat = 'Basic' if is_basic else 'Special'
        
        # 處理資料格式
        abilities = json.dumps(card.get('abilities', []))
        attacks = json.dumps(card.get('attacks', []))
        types = json.dumps(card.get('types', []))
        weaknesses = json.dumps(card.get('weaknesses', []))
        description = card.get('description', card.get('effect', ""))

        cursor.execute('''
            INSERT OR REPLACE INTO cards 
            (id, name, hp, types, stage, abilities, attacks, weaknesses, description, regulationMark, image_url, category, subCategory)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            card_id,
            card_name,
            card.get('hp'),
            types,
            card.get('stage'),
            abilities,
            attacks,
            weaknesses,
            description,
            card.get('regulationMark'),
            f"{card.get('image')}/high.webp",
            'Energy',
            sub_cat
        ))
        
        count_added += 1
        if count_added % 10 == 0:
            print(f"已處理 {count_added}/{len(energy_cards)} 張能量...")

    conn.commit()
    conn.close()
    print(f"✨ 任務達成！成功補齊 {count_added} 張能量卡（含基本與特殊）。")

if __name__ == "__main__":
    force_fetch_energy()