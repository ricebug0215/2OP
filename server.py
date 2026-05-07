from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import json
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    conn = sqlite3.connect('pokemon_tcg_full.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/api/cards")
async def get_cards(name: str = "", category: str = "All", type: str = "All"):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM cards WHERE 1=1"
    params = []
    
    if name:
        query += " AND name LIKE ?"
        params.append(f"%{name}%")
        
    if category != "All":
        query += " AND category = ?"
        params.append(category)
    
    if type != "All":
        if category == "Pokemon":
            query += " AND types LIKE ?"
            params.append(f'%"{type}"%')
        elif category == "Trainer":
            query += " AND subCategory = ?"
            params.append(type)
        elif category == "Energy":
            if type == "Basic":
                query += " AND subCategory = 'Basic'"
            elif type == "Special":
                query += " AND subCategory = 'Special'"
            
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    results = []
    for row in rows:
        card = dict(row)
        if card.get('types'): card['types'] = json.loads(card['types'])
        if card.get('abilities'): card['abilities'] = json.loads(card['abilities'])
        if card.get('attacks'): card['attacks'] = json.loads(card['attacks'])
        
        card['is_ace_spec'] = bool(card.get('is_ace_spec', 0))
        card['image'] = card.get('image_url')
        results.append(card)
        
    conn.close()
    return results

@app.post("/api/simulate")
async def run_simulation(request: Request):
    raw_deck = await request.json()
    
    # 1. 攤平牌組 (將 count 展開為獨立的卡片字典)
    deck = []
    for item in raw_deck:
        count = item.get('count', 1)
        for i in range(count):
            # 保留需要的關鍵資訊
            deck.append({
                "id": f"{item['id']}-{i}",
                "name": item['name'],
                "category": item['category'],
                "stage": item.get('stage', ''),
                "image": item.get('image', '')
            })
            
    # 2. 洗牌與 Mulligan 邏輯
    random.shuffle(deck)
    mulligan_count = 0
    
    while True:
        hand = deck[:7]
        remaining = deck[7:]
        
        # 檢查手牌是否有基礎寶可夢
        has_basic = any(c['category'] == 'Pokemon' and c['stage'] == 'Basic' for c in hand)
        
        if has_basic:
            deck = remaining
            break
            
        # 重新洗牌
        mulligan_count += 1
        deck = remaining + hand
        random.shuffle(deck)
        
        # 防呆機制
        if mulligan_count > 15:
            deck = remaining
            break
            
    # 3. 抽出 6 張獎勵卡
    prizes = deck[:6]
    remaining_deck = deck[6:]
    
    return {
        "hand": hand,
        "prizes": prizes,
        "remainingDeckCount": len(remaining_deck),
        "mulliganCount": mulligan_count
    }

@app.post("/api/import-deck")
async def import_deck(request: Request):
    """接收前端傳來的卡片名稱與數量，從資料庫轉換成完整卡片物件"""
    items = await request.json()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    full_deck = []
    not_found_list = [] # 記錄哪些牌真的找不到
    
    for item in items:
        # 👇 關鍵修改：使用 LIKE 和 % 進行模糊搜尋，容忍空白或大小寫差異
        search_name = f"%{item['name']}%"
        cursor.execute("SELECT * FROM cards WHERE name LIKE ? LIMIT 1", (search_name,))
        row = cursor.fetchone()
        
        if row:
            card = dict(row)
            if card.get('types'): card['types'] = json.loads(card['types'])
            if card.get('abilities'): card['abilities'] = json.loads(card['abilities'])
            if card.get('attacks'): card['attacks'] = json.loads(card['attacks'])
            
            card['is_ace_spec'] = bool(card.get('is_ace_spec', 0))
            card['image'] = card.get('image_url')
            card['count'] = item.get('count', 1) 
            
            full_deck.append(card)
        else:
            not_found_list.append(item['name'])
            print(f"⚠️ 警告：資料庫完全找不到包含『{item['name']}』的卡片")
            
    conn.close()
    
    # 順便把找不到的清單也傳回前端，方便除錯
    return {"deck": full_deck, "notFound": not_found_list}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)