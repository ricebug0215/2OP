import sqlite3
import requests

def fix_trainer_types():
    conn = sqlite3.connect('pokemon_tcg_full.db')
    cursor = conn.cursor()
    
    # 1. 幫資料庫新增一個 subCategory 欄位 (如果已經有會自動跳過)
    try:
        cursor.execute("ALTER TABLE cards ADD COLUMN subCategory TEXT")
        print("成功新增 subCategory 欄位！")
    except sqlite3.OperationalError:
        print("subCategory 欄位已存在，直接開始更新資料...")
        
    # 2. 找出所有訓練家卡
    cursor.execute("SELECT id, name FROM cards WHERE category = 'Trainer'")
    trainers = cursor.fetchall()
    
    print(f"總共找到 {len(trainers)} 張訓練家卡，準備補齊分類...")
    
    # 3. 呼叫 API 取得具體的 trainerType (Item, Supporter, Stadium, Tool)
    for i, (card_id, card_name) in enumerate(trainers):
        res = requests.get(f"https://api.tcgdex.net/v2/zh-tw/cards/{card_id}")
        if res.status_code == 200:
            data = res.json()
            # TCGdex 裡訓練家的分類放在 'trainerType'
            sub_cat = data.get('trainerType', 'Unknown')
            
            # 更新回資料庫
            cursor.execute("UPDATE cards SET subCategory = ? WHERE id = ?", (sub_cat, card_id))
            
        if (i + 1) % 10 == 0:
            print(f"進度：已更新 {i + 1}/{len(trainers)} 張...")
            
    conn.commit()
    conn.close()
    print("✨ 訓練家分類修補完成！")

if __name__ == "__main__":
    fix_trainer_types()