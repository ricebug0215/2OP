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

# ─── T2 展開模擬 ───

DEFAULT_PLAYBOOK = {
    "active_priority": ["含羞苞", "可達鴨", "願增猿", "土龍弟弟", "多龍梅西亞"],
    "setup_bench_priority": ["多龍梅西亞", "土龍弟弟", "願增猿"],
    "no_bench": ["可達鴨"],
    "play_priority": [
        {"card": "bench_basics"},
        {"card": "好友寶芬", "conditions": {"bench_open_gte": 2}},
        {"card": "寶可平板"}, {"card": "高級球"}, {"card": "寶可裝置3.0"},
        {"card": "夜間擔架"},
        {"card": "evolve"}, {"card": "use_ability"},
        {"card": "attach_energy"},
        {"card": "莉莉艾的決意"}, {"card": "赤松"},
        {"card": "小剛的發掘", "conditions": {"hand_size_lte": 3}},
    ],
    "search_priority": [
        "多龍梅西亞", "土龍弟弟", "多龍奇", "多龍巴魯托ex",
        "願增猿", "含羞苞", "土龍節節ex",
    ],
    "discard_priority": ["Energy", "特殊紅牌", "老大的指令", "險惡廢墟"],
    "bench_priority": ["多龍梅西亞", "土龍弟弟", "願增猿"],
    "energy_target": ["多龍梅西亞", "多龍奇", "土龍弟弟"],
    "evolution_lines": {
        "多龍梅西亞": ["多龍奇", "多龍巴魯托ex"],
        "土龍弟弟": ["土龍節節ex", "土龍節節"],
    },
}

TIER_CACHE: dict[str, dict] = {}

def _compute_tiers(runner, n=500):
    scores = []
    for _ in range(n):
        r = runner.run_once(turns=2, going_first=True)
        scores.append(r['score'])
    scores.sort()
    total = len(scores)
    return {
        'p95': scores[int(total * 0.95)],
        'p75': scores[int(total * 0.75)],
        'p40': scores[int(total * 0.40)],
        'p5': scores[int(total * 0.05)],
    }

@app.post("/api/simulate-t2")
async def simulate_t2(request: Request):
    from playbook import SimulationRunner
    body = await request.json()
    deck_list = body.get("deck", [])
    playbook = body.get("playbook", DEFAULT_PLAYBOOK)
    runner = SimulationRunner(deck_list, playbook)

    deck_key = ",".join(sorted(f"{d['name']}:{d['count']}" for d in deck_list))
    if deck_key not in TIER_CACHE:
        TIER_CACHE[deck_key] = _compute_tiers(runner)
        print(f"Debug: computed tiers for deck: {deck_key} -> {TIER_CACHE[deck_key]}")
    tiers = TIER_CACHE[deck_key]

    result = runner.run_once(turns=2, going_first=True)
    result['tiers'] = tiers
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)