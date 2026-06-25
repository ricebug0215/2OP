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

@app.get("/api/evolution-chains")
async def get_evolution_chains():
    """回傳 {進化卡: 進化前卡} 對應表，供前端計算進化線連動顯示。"""
    from game_engine import EVOLVES_FROM
    return EVOLVES_FROM


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
    "supporter_priority": ["莉莉艾的決意", "小剛的發掘", "赤松", "阿塞蘿拉的惡作劇", "老大的指令"],
    "main_attacker": ["多龍梅西亞"],
    "discard_priority": ["Energy", "特殊紅牌", "老大的指令", "險惡廢墟"],
    "bench_priority": ["多龍梅西亞", "土龍弟弟", "願增猿"],
    "energy_target": ["多龍梅西亞", "多龍奇", "土龍弟弟"],
    "evolution_lines": {
        "多龍梅西亞": ["多龍奇", "多龍巴魯托ex"],
        "土龍弟弟": ["土龍節節ex", "土龍節節"],
    },
}

TIER_CACHE: dict[str, dict] = {}
_TIER_COMPUTING: set[str] = set()

def _deck_key(deck_list: list[dict]) -> str:
    return ",".join(sorted(f"{d['name']}:{d['count']}" for d in deck_list))

def _compute_tiers_bg(deck_list: list[dict], playbook: dict, key: str):
    from playbook import SimulationRunner
    runner = SimulationRunner(deck_list, playbook)
    n = 500
    scores = []
    for _ in range(n):
        r = runner.run_once(turns=2, going_first=True)
        scores.append(r['score'])
    scores.sort()
    total = len(scores)
    TIER_CACHE[key] = {
        'p95': scores[int(total * 0.95)],
        'p75': scores[int(total * 0.75)],
        'p40': scores[int(total * 0.40)],
        'p5': scores[int(total * 0.05)],
    }
    _TIER_COMPUTING.discard(key)

@app.post("/api/simulate-t2")
async def simulate_t2(request: Request):
    from fastapi import BackgroundTasks
    from playbook import SimulationRunner
    body = await request.json()
    deck_list = body.get("deck", [])
    do_not_play = body.get("do_not_play", [])
    main_attacker = body.get("main_attacker", [])
    playbook = dict(body.get("playbook", DEFAULT_PLAYBOOK))
    if do_not_play:
        playbook['do_not_play'] = do_not_play
    if main_attacker:
        # 使用者可能只點了 ex 或基礎，展開成整條進化線
        from game_engine import expand_main_attackers
        playbook['main_attacker'] = expand_main_attackers(main_attacker)
    runner = SimulationRunner(deck_list, playbook)
    key = _deck_key(deck_list)

    result = runner.run_once(turns=2, going_first=True)

    if key in TIER_CACHE:
        result['tiers'] = TIER_CACHE[key]
    else:
        result['tiers'] = None
        if key not in _TIER_COMPUTING:
            _TIER_COMPUTING.add(key)
            import threading
            threading.Thread(
                target=_compute_tiers_bg,
                args=(deck_list, playbook, key),
                daemon=True,
            ).start()

    return result

@app.post("/api/tiers")
async def get_tiers(request: Request):
    body = await request.json()
    deck_list = body.get("deck", [])
    key = _deck_key(deck_list)
    if key in TIER_CACHE:
        return {"tiers": TIER_CACHE[key], "ready": True}
    return {"tiers": None, "ready": False}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)