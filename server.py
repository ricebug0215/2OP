from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 資料載入區 ───
def load_all_data():
    all_cards = []
    files = {
        "Pokemon": "ptcg_full_database.json",
        "Trainer": "ptcg_trainer_database.json",
        "Energy": "ptcg_energy_database.json"
    }
    
    for category, filename in files.items():
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for card in data:
                    card['category'] = category
                    # 統一圖片欄位名稱
                    if 'imageUrl' in card:
                        card['image'] = card['imageUrl']
                    elif 'image_url' in card:
                        card['image'] = card['image_url']
                all_cards.extend(data)
        else:
            print(f"⚠️ 找不到檔案：{filename}")
            
    return all_cards

MASTER_DATA = load_all_data()

# ─── API 路由 ───

@app.get("/api/cards")
async def get_cards(name: str = "", category: str = "All", type: str = "All", page: int = 1, limit: int = 48):
    results = MASTER_DATA
    
    if name:
        results = [c for c in results if name.lower() in str(c.get('name', '')).lower()]
        
    if category != "All":
        results = [c for c in results if str(c.get('category')) == category]
        
    if type != "All" and type != "":
        filtered_results = []
        for c in results:
            if category == "Pokemon":
                # 寶可夢比對屬性
                types_data = str(c.get('types', '')) + str(c.get('type', '')) + str(c.get('attribute', ''))
                if type in types_data:
                    filtered_results.append(c)
            else:
                # 👇 訓練家卡與能量卡，現在完美共用這個邏輯！
                # 直接去抓你爬蟲寫好的 subType 欄位
                sub_data = str(c.get('subCategory', '')) + str(c.get('subType', '')) + str(c.get('class', ''))
                
                # 前端傳來 "特殊能量卡"，你的 subType 也是 "特殊能量卡"，完美配對！
                if sub_data and (type in sub_data or sub_data in type):
                    filtered_results.append(c)
                    
        results = filtered_results
        
    # 分頁邏輯
    total_count = len(results)
    skip = (page - 1) * limit
    
    return {
        "items": results[skip : skip + limit],
        "total": total_count
    }

@app.post("/api/import-deck")
async def import_deck(request: Request):
    items = await request.json()
    full_deck = []
    not_found = []
    
    for item in items:
        match = next((c for c in MASTER_DATA if item['name'].lower() in str(c.get('name', '')).lower()), None)
        if match:
            card_copy = match.copy()
            card_copy['count'] = item.get('count', 1)
            full_deck.append(card_copy)
        else:
            not_found.append(item['name'])
            
    return {"deck": full_deck, "notFound": not_found}

@app.post("/api/simulate")
async def run_simulation(request: Request):
    raw_deck = await request.json()
    deck = []
    for item in raw_deck:
        for i in range(item.get('count', 1)):
            deck.append(item)
            
    random.shuffle(deck)
    mulligan_count = 0
    
    while True:
        hand = deck[:7]
        remaining = deck[7:]
        has_basic = any(c.get('category') == 'Pokemon' and c.get('stage') == '基礎' for c in hand)
        if has_basic:
            break
        mulligan_count += 1
        random.shuffle(deck)
        if mulligan_count > 15: break
            
    prizes = deck[7:13]
    return {
        "hand": hand,
        "prizes": prizes,
        "mulliganCount": mulligan_count
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)