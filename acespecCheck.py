import requests
import sqlite3

# 終極保險：2026 年標準環境中常見的 ACE SPEC 繁中譯名清單
KNOWN_ACE_SPECS = [
    "不公印章", "覺醒戰鼓", "急進開關", "危險光線", "高級香氛", 
    "頂尖捕捉器", "貴重手推車", "寶可生機劑A", "寶可夢旋風回收機", "重新啟動箱", 
    "璀璨結晶", "奢華炸彈", "英雄斗篷", "極限腰帶", "富裕能量", 
    "古舊能量", "釣竿MAX", "珍寶配件", "中立中心", "奇跡耳麥", "希望護身符", 
    "能量輸送PRO", "百萬噸吹風機", "完全體攪拌器", "壯偉碩木", "倖存鍛鍊器", "新沖天能量", "大師球"
]

def catch_ace_specs():
    conn = sqlite3.connect('pokemon_tcg_full.db')
    cursor = conn.cursor()

    # 確保欄位存在
    try:
        cursor.execute("ALTER TABLE cards ADD COLUMN is_ace_spec INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # 先將所有標記歸零，重新來過
    cursor.execute("UPDATE cards SET is_ace_spec = 0")

    # 取得所有訓練家與特殊能量 (基本能量絕對不可能是 ACE SPEC)
    cursor.execute("SELECT id, name FROM cards WHERE category IN ('Trainer', 'Energy') AND subCategory != 'Basic'")
    candidates = cursor.fetchall()

    print(f"🔍 開始掃描 {len(candidates)} 張卡片的『稀有度』欄位與白名單...")

    ace_count = 0
    for i, (card_id, card_name) in enumerate(candidates):
        try:
            # 策略一：直接比對白名單 (最快、最準)
            is_ace = any(known_name in card_name for known_name in KNOWN_ACE_SPECS)
            
            # 策略二：如果白名單沒抓到，去 API 查他的 Rarity
            if not is_ace:
                res = requests.get(f"https://api.tcgdex.net/v2/zh-tw/cards/{card_id}")
                if res.status_code == 200:
                    data = res.json()
                    rarity = data.get('rarity', '')
                    if rarity == 'ACE SPEC Rare' or 'ACE SPEC' in data.get('name', ''):
                        is_ace = True

            # 如果確認是 ACE SPEC，寫入資料庫
            if is_ace:
                cursor.execute("UPDATE cards SET is_ace_spec = 1 WHERE id = ?", (card_id,))
                ace_count += 1
                print(f"✨ 成功捕捉 ACE SPEC: {card_name}")

            if (i + 1) % 50 == 0:
                print(f"進度：已檢查 {i + 1} 張...")

        except Exception as e:
            print(f"錯誤 ID {card_id}: {e}")

    conn.commit()
    conn.close()
    print(f"🎉 捕捉完成！這次絕對沒漏掉，共標記了 {ace_count} 張 ACE SPEC 卡片。")

if __name__ == "__main__":
    catch_ace_specs()