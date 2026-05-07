import sqlite3
import json

def patch_missing_cards():
    # 連線至你的 SQLite 資料庫
    conn = sqlite3.connect('pokemon_tcg_full.db')
    cursor = conn.cursor()

    # 你辛苦找齊的高清官方圖片資料
    missing_cards = [
        {
            "id": "patch-ultra-ball",
            "name": "高級球",
            "category": "Trainer",
            "subCategory": "Item",
            "image_url": "https://asia.pokemon-card.com/tw/card-img/tw00017122.png", 
            "is_ace_spec": 0
        },
        {
            "id": "patch-boss-orders",
            "name": "老大的指令",
            "category": "Trainer",
            "subCategory": "Supporter",
            "image_url": "https://asia.pokemon-card.com/tw/card-img/tw00008471.png",
            "is_ace_spec": 0
        },
        {
            "id": "patch-poke-pad",
            "name": "寶可平板",
            "category": "Trainer",
            "subCategory": "Item",
            "image_url": "https://asia.pokemon-card.com/tw/card-img/tw00018047.png",
            "is_ace_spec": 0
        },
        {
            "id": "patch-pokegear-3",
            "name": "寶可裝置3.0",
            "category": "Trainer",
            "subCategory": "Item",
            "image_url": "https://asia.pokemon-card.com/tw/card-img/tw00017131.png",
            "is_ace_spec": 0
        },
        {
            "id": "patch-special-red-card",
            "name": "特殊紅牌",
            "category": "Trainer",
            "subCategory": "Item",
            "image_url": "https://asia.pokemon-card.com/tw/card-img/tw00018492.png",
            "is_ace_spec": 0
        },
        {
            "id": "patch-lillies-resolve",
            "name": "莉莉艾的決意",
            "category": "Trainer",
            "subCategory": "Supporter",
            "image_url": "https://asia.pokemon-card.com/tw/card-img/tw00014835.png",
            "is_ace_spec": 0
        },
        {
            "id": "patch-acerolas-premonition",
            "name": "阿賽蘿拉的惡作劇",
            "category": "Trainer",
            "subCategory": "Supporter",
            "image_url": "https://asia.pokemon-card.com/tw/card-img/tw00014829.png",
            "is_ace_spec": 0
        },
        {
            "id": "patch-dangerous-wastes",
            "name": "險惡廢墟",
            "category": "Trainer",
            "subCategory": "Stadium",
            "image_url": "https://asia.pokemon-card.com/tw/card-img/tw00014020.png",
            "is_ace_spec": 0
        }
    ]

    print("🛠️ 開始執行資料庫補丁，準備強制覆蓋缺漏卡片...")

    success_count = 0
    for card in missing_cards:
        try:
            # 👇 關鍵修改：使用 INSERT OR REPLACE
            # 如果資料庫沒有這張牌，它會直接新增；如果有同 id 的牌，它會用新資料「完全覆蓋」舊資料！
            cursor.execute("""
                INSERT OR REPLACE INTO cards (id, name, category, subCategory, image_url, types, abilities, attacks, is_ace_spec)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                card['id'], 
                card['name'], 
                card['category'], 
                card['subCategory'], 
                card['image_url'],
                json.dumps([]), # types
                json.dumps([]), # abilities
                json.dumps([]), # attacks
                card['is_ace_spec']
            ))
            success_count += 1
            print(f"✅ 成功更新: {card['name']}")
        except Exception as e:
            print(f"❌ 寫入 {card['name']} 時發生錯誤: {e}")

    conn.commit()
    conn.close()
    print(f"🎉 補丁執行完畢！共強制更新了 {success_count} 張關鍵卡片。")

if __name__ == "__main__":
    patch_missing_cards()