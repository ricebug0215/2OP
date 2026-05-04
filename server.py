from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import json

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
async def get_cards(
    name: str = "", 
    category: str = "All", 
    type: str = "All"  # React 前端傳來的 subFilter 都統一放在這裡
):
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
    
    # --- 關鍵修正：區分寶可夢屬性與訓練家類型的篩選方式 ---
    if type != "All":
        if category == "Pokemon":
            # 寶可夢的屬性是 JSON 字串（如 '["Grass"]'）
            query += " AND types LIKE ?"
            params.append(f'%"{type}"%')
        elif category == "Trainer":
            # 訓練家的類型是我們剛才新增的純文字欄位（如 'Item', 'Supporter'）
            query += " AND subCategory = ?"
            params.append(type)
            
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    results = []
    for row in rows:
        card = dict(row)
        # 解析 JSON 字串
        if card['types']: card['types'] = json.loads(card['types'])
        if card['abilities']: card['abilities'] = json.loads(card['abilities'])
        if card['attacks']: card['attacks'] = json.loads(card['attacks'])
        
        card['image'] = card['image_url']
        results.append(card)
        
    conn.close()
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)