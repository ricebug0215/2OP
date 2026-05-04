from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import json

app = FastAPI()

# 允許前端 React 存取 (CORS 設定)
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
    type: str = "All"
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
    
    # 處理子分類的篩選邏輯
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
        
        # 解析 JSON 字串
        if card.get('types'): card['types'] = json.loads(card['types'])
        if card.get('abilities'): card['abilities'] = json.loads(card['abilities'])
        if card.get('attacks'): card['attacks'] = json.loads(card['attacks'])
        
        # 將 ACE SPEC 標籤轉為前端好用的 Boolean
        card['is_ace_spec'] = bool(card.get('is_ace_spec', 0))
        
        # 統一圖片欄位名稱
        card['image'] = card.get('image_url')
        
        results.append(card)
        
    conn.close()
    return results

if __name__ == "__main__":
    import uvicorn
    # 啟動伺服器，預設運行在 8000 port
    uvicorn.run(app, host="127.0.0.1", port=8000)