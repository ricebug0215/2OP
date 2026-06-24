"""
PTCG 卡牌資料 pipeline — 從官網自動抓取卡牌資料並產生模擬器所需的資料檔。

本腳本從 asia.pokemon-card.com 官網爬取卡牌頁面，產生三類資料:

  1. 卡牌效果 DSL      → card_effects.json     (道具/支援者/特性, 經 LLM 轉換)
  2. 進化關係表        → evolution_chains.json ({進化卡: 進化前卡})
  3. 主力能量需求      → energy_profiles.json  ({寶可夢: [需要的能量屬性]})

資料來源:
  - 卡牌效果文字、進化鏈、招式能量需求皆從卡牌的 sourceUrl 頁面 HTML 解析。
  - 效果文字若無法從 HTML 取得, 會退而用 Claude vision 讀卡圖 (imageUrl)。
  - DSL 結構化轉換需呼叫 Claude API (需設定 ANTHROPIC_API_KEY)；
    進化鏈與能量需求為純爬蟲解析, 不需 API。

──────────────────────────────────────────────────────────────────────
用法:

  # ── 卡牌效果 DSL (需 ANTHROPIC_API_KEY) ──
  # 產生單張或多張卡的 DSL, 直接合併進 card_effects.json
  python generate_effects.py "特殊紅牌"
  python generate_effects.py "特殊紅牌" "英雄斗篷" "險惡廢墟"

  # 產生資料庫中所有尚未定義的 Trainer 卡
  python generate_effects.py --missing

  # Dry run: 只抓效果文字, 不呼叫 LLM (用來檢查爬取結果)
  python generate_effects.py --dry "特殊紅牌"

  # 指定輸出檔, 不直接覆寫 card_effects.json
  python generate_effects.py "特殊紅牌" --out preview.json

  # ── 進化關係 (純爬蟲, 不需 API) ──
  # 抓取指定寶可夢的進化鏈, 更新 evolution_chains.json
  python generate_effects.py --evolution "多龍奇" "土龍節節" "可達鴨"

  # ── 主力能量需求 (純爬蟲, 不需 API) ──
  # 推導各進化線主力(最高階 ex)的招式能量需求, 更新 energy_profiles.json
  # 傳入線上任一張卡即可 (基礎/1階/2階皆可), 會自動展開整條進化線
  python generate_effects.py --energy-profile "多龍梅西亞" "土龍弟弟"

換新牌組時的建議流程:
  1. --evolution      補進化關係 (引擎據此判斷合法進化、避免跨線進化)
  2. --energy-profile 補主力能量需求 (填能屬性正確 + 計分依據)
  3. (選用) 對缺少的 Trainer 卡跑 DSL 產生

注意: evolution_chains.json / energy_profiles.json 只含已抓過的寶可夢,
      新增寶可夢請記得重跑對應模式補資料。
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import anthropic
import httpx
from bs4 import BeautifulSoup


EFFECTS_PATH = Path('card_effects.json')
TRAINER_DB_PATH = Path('ptcg_trainer_database.json')
FULL_DB_PATH = Path('ptcg_full_database.json')

DSL_SCHEMA = """
你是 PTCG（寶可夢集換式卡牌遊戲）的 DSL 定義產生器。
你的任務是根據卡牌效果文字，產生符合以下 DSL 格式的 JSON 定義。

## DSL Action 類型

1. **draw** — 從牌庫抽 N 張
   ```json
   {"action": "draw", "count": N}
   ```

2. **search_deck** — 搜尋牌庫，選取符合條件的牌
   ```json
   {
     "action": "search_deck",
     "filter": {"category": "Pokemon", "stage": "基礎", "hp_lte": 70},
     "up_to": 2,
     "destination": "hand" | "bench" | "deck" | "attach"
   }
   ```
   filter 可用欄位:
   - category: "Pokemon" | "Trainer" | "Energy"
   - sub_type: "物品卡" | "支援者卡" | "競技場卡" | "寶可夢道具" | "基本能量卡"
   - stage: "基礎" | "1階進化" | "2階進化"
   - stage_in: ["1階進化", "2階進化"]
   - hp_lte: 數字 (HP 上限)
   - category_in: ["Pokemon", "BasicEnergy"] (多類別)

3. **look_top** — 查看牌庫頂 N 張，選取後剩餘處理
   ```json
   {
     "action": "look_top",
     "count": N,
     "pick_filter": {"category": "Pokemon"},
     "pick_up_to": 1,
     "rest": "shuffle_back" | "discard" | "bottom"
   }
   ```

4. **discard_hand** — 丟棄全部手牌
   ```json
   {"action": "discard_hand"}
   ```

5. **shuffle_hand_draw** — 手牌全部洗回牌庫後抽 N 張
   ```json
   {"action": "shuffle_hand_draw", "count": N}
   ```
   count 可以是數字或 "prizes_remaining"

6. **switch_active** — 替換戰鬥區與備戰區寶可夢
   ```json
   {"action": "switch_active"}
   ```

7. **evolve** — 進化場上寶可夢
   ```json
   {"action": "evolve", "skip_stage": true}
   ```
   skip_stage=true 表示可以跳階進化（如神奇糖果）

8. **recover** — 從棄牌區回收
   ```json
   {
     "action": "recover",
     "filter": {"category": "Pokemon"},
     "count": 1,
     "destination": "hand" | "deck"
   }
   ```

## 卡牌結構

### 道具/支援者/競技場
```json
{
  "sub_type": "物品卡" | "支援者卡" | "競技場卡" | "寶可夢道具",
  "is_ace_spec": true,  // 僅 ACE SPEC 卡需要
  "cost": {"action": "discard_from_hand", "count": N},  // 如高級球需丟2張
  "effects": [ ... action 列表 ... ],
  "constraints": {"min_turn_in_play": 1}  // 如需場上回合限制
}
```

### 多選模式 (choose_one)
```json
{
  "sub_type": "物品卡",
  "mode": "choose_one",
  "options": [
    {"id": "option_a", "effects": [...]},
    {"id": "option_b", "effects": [...]}
  ]
}
```

### 寶可夢特性 (abilities)
回傳格式不同:
```json
{
  "name": "特性名稱",
  "once_per_turn_per_pokemon": true,
  "effects": [ ... ]
}
```

## 重要注意事項

1. 這是一個 T1/T2 展開模擬器，只關心「自己的回合」能做的事。不需要處理對手回合的效果。
2. 涉及對手操作的效果（如讓對手洗手牌、對手展示手牌等），在我們的模擬中不影響遊戲狀態，可以忽略或標記為 "opponent_effect": true。
3. 攻擊招式不需要定義，只需要特性和道具/支援者效果。
4. 目前引擎不支援的效果類型，用 "not_implemented": true 標記，並在 "description" 中說明。
5. filter 中的值必須精確匹配 DSL 定義，不要自創。
6. 注意分辨「最多N張」(up_to) 和「剛好N張」(count) 的區別。

## 現有範例

以下是已經定義好的卡牌，供你參考風格和格式:
"""

EXAMPLES = {
    "好友寶芬": {
        "text": "從自己的牌庫選擇最多2張HP為「70」以下的【基礎】寶可夢卡，放置於備戰區。並且重洗牌庫。",
        "dsl": {
            "sub_type": "物品卡",
            "effects": [{
                "action": "search_deck",
                "filter": {"category": "Pokemon", "stage": "基礎", "hp_lte": 70},
                "up_to": 2,
                "destination": "bench"
            }]
        }
    },
    "高級球": {
        "text": "從手牌選擇2張丟棄後，從牌庫選擇1張寶可夢卡加入手牌，重洗牌庫。",
        "dsl": {
            "sub_type": "物品卡",
            "cost": {"action": "discard_from_hand", "count": 2},
            "effects": [{
                "action": "search_deck",
                "filter": {"category": "Pokemon"},
                "up_to": 1,
                "destination": "hand"
            }]
        }
    },
    "夜間擔架": {
        "text": "選擇1：(1)從棄牌區選擇1張寶可夢卡加入手牌 或 (2)從棄牌區選擇最多3張基本能量卡放回牌庫。",
        "dsl": {
            "sub_type": "物品卡",
            "mode": "choose_one",
            "options": [
                {
                    "id": "recover_pokemon",
                    "effects": [{
                        "action": "recover",
                        "filter": {"category": "Pokemon"},
                        "count": 1,
                        "destination": "hand"
                    }]
                },
                {
                    "id": "recover_energy",
                    "effects": [{
                        "action": "recover",
                        "filter": {"category": "Energy", "sub_type": "基本能量卡"},
                        "count": 3,
                        "destination": "deck"
                    }]
                }
            ]
        }
    },
    "莉莉艾的決意": {
        "text": "將手牌全部洗入牌庫，抽8張。",
        "dsl": {
            "sub_type": "支援者卡",
            "effects": [{"action": "shuffle_hand_draw", "count": 8}]
        }
    },
    "赤松": {
        "text": "從牌庫搜尋1張基本能量卡加入手牌，再搜尋1張基本能量卡貼在場上寶可夢身上。重洗牌庫。",
        "dsl": {
            "sub_type": "支援者卡",
            "effects": [
                {
                    "action": "search_deck",
                    "filter": {"category": "Energy", "sub_type": "基本能量卡"},
                    "up_to": 1,
                    "destination": "hand"
                },
                {
                    "action": "search_deck",
                    "filter": {"category": "Energy", "sub_type": "基本能量卡"},
                    "up_to": 1,
                    "destination": "attach"
                }
            ]
        }
    }
}


def load_databases() -> dict[str, dict]:
    """載入所有卡牌資料庫，以 name 為 key。"""
    db = {}
    for path in [TRAINER_DB_PATH, FULL_DB_PATH]:
        if path.exists():
            with open(path) as f:
                for card in json.load(f):
                    db[card['name']] = card
    return db


def load_existing_effects() -> dict:
    with open(EFFECTS_PATH) as f:
        return json.load(f)


def fetch_card_text(source_url: str) -> str | None:
    """從官網頁面抓取卡牌效果文字。"""
    try:
        resp = httpx.get(source_url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f'[!] HTTP error fetching {source_url}: {e}', file=sys.stderr)
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')

    texts = []
    # 寶可夢特性
    ability_section = soup.find('h4', string=re.compile(r'特性'))
    if ability_section:
        ability_name_el = ability_section.find_next_sibling()
        if ability_name_el:
            texts.append(f'[特性] {ability_name_el.get_text(strip=True)}')

    # 效果文字 — 通常在 class 含 "text" 的區塊
    for el in soup.select('.pokemon-card-text, .card-text, .pokemon-info__text'):
        txt = el.get_text(strip=True)
        if txt and len(txt) > 5:
            texts.append(txt)

    # fallback: 找所有 <p> 或 <div> 中包含遊戲關鍵字的文字
    if not texts:
        keywords = ['牌庫', '手牌', '棄牌', '備戰區', '戰鬥區', '能量', '進化',
                     '寶可夢', '回合', '選擇', '抽', '丟棄', '洗', '搜尋']
        for p in soup.find_all(['p', 'div', 'span']):
            txt = p.get_text(strip=True)
            if any(kw in txt for kw in keywords) and 10 < len(txt) < 500:
                texts.append(txt)

    # 去重
    seen = set()
    unique = []
    for t in texts:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    return '\n'.join(unique) if unique else None


def fetch_evolution_stages(source_url: str) -> list[list[str]] | None:
    """從官網頁面抓取進化鏈，回傳分階段的名稱列表。

    例: 多龍奇頁面 -> [['多龍梅西亞'], ['多龍奇'], ['多龍巴魯托', '多龍巴魯托ex']]
    每個階段可能有多個變體（如 2階的一般版與 ex 版）。
    """
    try:
        resp = httpx.get(source_url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f'[!] HTTP error fetching {source_url}: {e}', file=sys.stderr)
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')
    evo_div = soup.find('div', class_='evolution')
    if not evo_div:
        return None

    stages = []
    for ul in evo_div.find_all('ul', class_='evolutionStep'):
        names = []
        for li in ul.find_all('li', recursive=False):
            a = li.find('a', recursive=False)
            if a:
                names.append(a.get_text(strip=True))
        if names:
            stages.append(names)
    return stages or None


def build_evolves_from(stages: list[list[str]]) -> dict[str, str]:
    """從分階段名稱列表推導 evolves_from 對應關係。

    每一階的每張卡都進化自「前一階的第一張」（前一階通常只有一個基礎/中間型）。
    回傳 {進化卡名: 進化前卡名}。
    """
    mapping = {}
    for depth in range(1, len(stages)):
        prev_names = stages[depth - 1]
        # 前一階若有多個變體，取第一個作為主要進化來源
        pre = prev_names[0]
        for name in stages[depth]:
            mapping[name] = pre
    return mapping


def generate_evolution_chains(pokemon_names: list[str], db: dict,
                              out_path: Path = Path('evolution_chains.json')) -> dict:
    """為指定寶可夢抓取進化鏈，產生 {卡名: 進化前卡名} 對應檔。"""
    existing = {}
    if out_path.exists():
        with open(out_path) as f:
            existing = json.load(f)

    seen_urls = set()
    for name in pokemon_names:
        meta = db.get(name)
        if not meta:
            print(f'  [skip] "{name}" 不在資料庫中', file=sys.stderr)
            continue
        if meta.get('stage') == '基礎':
            # 基礎寶可夢不進化自任何卡，仍抓取以補齊其後續進化
            pass
        url = meta.get('sourceUrl', '')
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        print(f'  → {name}: {url}')
        stages = fetch_evolution_stages(url)
        if not stages:
            print(f'    無進化鏈（可能是非進化寶可夢）')
            continue
        chain_str = ' → '.join('/'.join(s) for s in stages)
        print(f'    進化鏈: {chain_str}')
        existing.update(build_evolves_from(stages))
        time.sleep(0.3)

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write('\n')
    print(f'\n✓ 已更新 {out_path}，共 {len(existing)} 筆進化關係')
    return existing


# ── 招式能量需求 → 主力能量 profile ──

# 官網能量圖示檔名(英) → 中文屬性
ENERGY_TYPE_MAP = {
    'Grass': '草', 'Fire': '火', 'Water': '水', 'Lightning': '雷',
    'Psychic': '超', 'Fighting': '鬥', 'Darkness': '惡', 'Metal': '鋼',
    'Dragon': '龍', 'Colorless': '無', 'Fairy': '妖',
}


def fetch_attack_costs(source_url: str) -> list[tuple[str, list[str]]]:
    """從官網頁面抓取招式與其能量需求。

    回傳 [(招式名, [中文屬性...]), ...]。無色以 '無' 表示。
    """
    try:
        resp = httpx.get(source_url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f'[!] HTTP error fetching {source_url}: {e}', file=sys.stderr)
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    attacks = []
    for sd in soup.find_all('div', class_='skill'):
        name_el = sd.select_one('.skillName')
        cost_el = sd.select_one('.skillCost')
        name = name_el.get_text(strip=True) if name_el else ''
        types = []
        if cost_el:
            for img in cost_el.find_all('img'):
                m = re.search(r'/energy/([A-Za-z]+)\.png', img.get('src', ''))
                if m:
                    types.append(ENERGY_TYPE_MAP.get(m.group(1), m.group(1)))
        if types:  # 只有真正的招式有能量需求（特性沒有）
            attacks.append((name, types))
    return attacks


def derive_required_types(attacks: list[tuple[str, list[str]]]) -> list[str]:
    """從招式列表推導「主力能量需求」。

    選擇非無色符號最多的招式作為主招，回傳其去重後的有色屬性。
    若所有招式皆為無色（如純無色攻擊手），回傳 []（表示任意能量皆可）。
    """
    best = []
    best_specific = -1
    for _, types in attacks:
        colored = [t for t in types if t != '無']
        if len(colored) > best_specific:
            best_specific = len(colored)
            best = colored
    # 去重保序
    seen = set()
    result = []
    for t in best:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def generate_energy_profiles(pokemon_names: list[str], db: dict,
                             evo_path: Path = Path('evolution_chains.json'),
                             out_path: Path = Path('energy_profiles.json')) -> dict:
    """為各進化線推導主力能量需求，產生 {寶可夢名: [需要的屬性]}。

    主力 = 進化線中最高階的卡（自動推導）。同一條線上的所有卡
    （基礎/1階/2階）都對應到主力的能量需求，這樣不論場上是哪一階都能查到。
    """
    evolves_from = {}
    if evo_path.exists():
        with open(evo_path) as f:
            evolves_from = json.load(f)

    existing = {}
    if out_path.exists():
        with open(out_path) as f:
            existing = json.load(f)

    # 建立進化線: 每個基礎 → 其所有後續進化
    children = {}
    for evo, pre in evolves_from.items():
        children.setdefault(pre, []).append(evo)

    def line_members(name: str) -> list[str]:
        """回傳該卡所屬進化線的所有成員（往上找根，再往下展開）。"""
        # 往上找基礎
        root = name
        while root in evolves_from:
            root = evolves_from[root]
        # BFS 往下
        members = [root]
        queue = [root]
        while queue:
            cur = queue.pop()
            for ch in children.get(cur, []):
                if ch not in members:
                    members.append(ch)
                    queue.append(ch)
        return members

    def stage_rank(name: str) -> int:
        s = db.get(name, {}).get('stage', '')
        return {'基礎': 0, '1階進化': 1, '2階進化': 2}.get(s, 0)

    processed_lines = set()
    for name in pokemon_names:
        members = line_members(name)
        line_key = tuple(sorted(members))
        if line_key in processed_lines:
            continue
        processed_lines.add(line_key)

        # 主力 = 最高階成員（同階取 ex 優先）
        attacker = max(members, key=lambda n: (stage_rank(n), 'ex' in n))
        meta = db.get(attacker)
        if not meta or not meta.get('sourceUrl'):
            print(f'  [skip] 主力 "{attacker}" 無資料', file=sys.stderr)
            continue
        print(f'  → 進化線 {members}，主力={attacker}')
        attacks = fetch_attack_costs(meta['sourceUrl'])
        required = derive_required_types(attacks)
        label = required if required else '任意（無色攻擊手）'
        print(f'    招式: {attacks}')
        print(f'    主力能量需求: {label}')
        # 整條線的每張卡都對應到主力需求
        for m in members:
            existing[m] = required
        time.sleep(0.3)

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write('\n')
    print(f'\n✓ 已更新 {out_path}，共 {len(existing)} 筆')
    return existing


def generate_dsl(card_name: str, card_text: str, card_meta: dict,
                 is_pokemon: bool = False) -> dict:
    """呼叫 Claude API 產生 DSL 定義。"""
    client = anthropic.Anthropic()

    examples_str = json.dumps(EXAMPLES, ensure_ascii=False, indent=2)

    if is_pokemon:
        output_hint = (
            "請產生 abilities 格式的 JSON（帶 name, once_per_turn_per_pokemon, effects）。"
            "如果這隻寶可夢沒有可模擬的特性，回傳 {\"skip\": true, \"reason\": \"...\"}"
        )
    else:
        output_hint = (
            "請產生 cards 格式的 JSON（帶 sub_type, effects 等）。"
        )

    user_msg = f"""請為以下卡牌產生 DSL JSON 定義。

卡牌名稱: {card_name}
卡牌類型: {card_meta.get('type', '未知')}
子類型: {card_meta.get('subType', card_meta.get('sub_type', '未知'))}
是否 ACE SPEC: {card_meta.get('isAceSpec', False)}

卡牌效果原文:
{card_text}

{output_hint}

只回傳純 JSON，不要包含任何 markdown 標記或解釋文字。"""

    response = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=DSL_SCHEMA + '\n\n' + examples_str,
        messages=[{"role": "user", "content": user_msg}],
    )

    result_text = ''
    for block in response.content:
        if block.type == 'text':
            result_text += block.text

    result_text = result_text.strip()
    result_text = re.sub(r'^```(?:json)?\s*', '', result_text)
    result_text = re.sub(r'\s*```$', '', result_text)

    try:
        return json.loads(result_text)
    except json.JSONDecodeError as e:
        print(f'[!] JSON parse error: {e}', file=sys.stderr)
        print(f'  Raw response:\n{result_text}', file=sys.stderr)
        return {"error": str(e), "raw": result_text}


def process_card(card_name: str, db: dict, existing: dict,
                 dry_run: bool = False) -> dict | None:
    """處理一張卡: 抓文字 → 產生 DSL。"""
    card_meta = db.get(card_name)
    if not card_meta:
        print(f'  ✗ "{card_name}" 不在資料庫中', file=sys.stderr)
        return None

    source_url = card_meta.get('sourceUrl', '')
    if not source_url:
        print(f'  ✗ "{card_name}" 沒有 sourceUrl', file=sys.stderr)
        return None

    print(f'  → 抓取 {source_url}')
    card_text = fetch_card_text(source_url)
    if not card_text:
        print(f'[!] 無法從頁面提取效果文字，嘗試 LLM vision...')
        image_url = card_meta.get('imageUrl', '')
        if image_url:
            card_text = read_card_image(image_url)
        if not card_text:
            print(f'  ✗ 無法取得 "{card_name}" 的效果文字', file=sys.stderr)
            return None

    print(f'  效果文字: {card_text[:100]}...' if len(card_text) > 100 else f'  效果文字: {card_text}')

    if dry_run:
        return {"_dry_run": True, "text": card_text}

    is_pokemon = card_meta.get('type') not in ('Trainer',)
    print(f'  → 呼叫 LLM 產生 DSL...')
    dsl = generate_dsl(card_name, card_text, card_meta, is_pokemon=is_pokemon)
    return dsl


def read_card_image(image_url: str) -> str | None:
    """用 Claude vision 讀取卡牌圖片上的效果文字。"""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "url", "url": image_url},
                },
                {
                    "type": "text",
                    "text": (
                        "請讀取這張寶可夢卡牌圖片上的效果文字。"
                        "只回傳效果/特性的文字部分，不要包含其他描述。"
                        "如果有特性，格式為 [特性] 特性名: 效果文字。"
                        "如果有招式，格式為 [招式] 招式名 (能量需求): 效果文字。"
                    ),
                },
            ],
        }],
    )
    for block in response.content:
        if block.type == 'text':
            return block.text.strip()
    return None


def find_missing_cards(db: dict, existing: dict) -> list[str]:
    """找出資料庫中有但 card_effects.json 中沒有的 Trainer 卡。"""
    existing_cards = set(existing.get('cards', {}).keys())
    missing = []
    for name, meta in db.items():
        if meta.get('type') == 'Trainer' and name not in existing_cards:
            missing.append(name)
    return sorted(missing)


def merge_into_effects(effects_data: dict, card_name: str, dsl: dict,
                       is_ability: bool = False):
    """將產生的 DSL 合併到 card_effects.json 結構中。"""
    if is_ability:
        effects_data.setdefault('abilities', {})[card_name] = dsl
    else:
        effects_data.setdefault('cards', {})[card_name] = dsl


def main():
    parser = argparse.ArgumentParser(description='LLM-based card_effects.json generator')
    parser.add_argument('cards', nargs='*', help='要產生的卡牌名稱')
    parser.add_argument('--missing', action='store_true',
                        help='產生所有缺少定義的 Trainer 卡')
    parser.add_argument('--dry', action='store_true',
                        help='只抓文字，不呼叫 LLM')
    parser.add_argument('--out', default=None,
                        help='輸出檔案路徑 (預設: 直接更新 card_effects.json)')
    parser.add_argument('--evolution', action='store_true',
                        help='抓取指定寶可夢的進化鏈，更新 evolution_chains.json')
    parser.add_argument('--energy-profile', action='store_true',
                        help='推導各進化線主力能量需求，更新 energy_profiles.json')
    args = parser.parse_args()

    db = load_databases()

    if args.evolution:
        names = args.cards
        if not names:
            print('用法: python generate_effects.py --evolution "多龍奇" "土龍節節" ...')
            return
        generate_evolution_chains(names, db)
        return

    if args.energy_profile:
        names = args.cards
        if not names:
            print('用法: python generate_effects.py --energy-profile "多龍巴魯托ex" "土龍節節ex" ...')
            return
        generate_energy_profiles(names, db)
        return

    existing = load_existing_effects()

    if args.missing:
        cards = find_missing_cards(db, existing)
        print(f'找到 {len(cards)} 張缺少定義的 Trainer 卡')
        if not cards:
            return
        for name in cards[:20]:
            print(f'  - {name}')
        if len(cards) > 20:
            print(f'  ... 還有 {len(cards) - 20} 張')
    else:
        cards = args.cards

    if not cards:
        parser.print_help()
        return

    results = {}
    for card_name in cards:
        print(f'\n[{card_name}]')
        dsl = process_card(card_name, db, existing, dry_run=args.dry)
        if dsl and not dsl.get('_dry_run'):
            results[card_name] = dsl
            print(f'  ✓ 產生完成')
            print(f'  {json.dumps(dsl, ensure_ascii=False, indent=2)[:200]}')

    if not results or args.dry:
        return

    # merge results
    for card_name, dsl in results.items():
        if dsl.get('skip'):
            print(f'\n跳過 {card_name}: {dsl.get("reason", "")}')
            continue
        if dsl.get('error'):
            print(f'\n錯誤 {card_name}: {dsl["error"]}')
            continue
        is_ability = 'name' in dsl and 'once_per_turn_per_pokemon' in dsl
        merge_into_effects(existing, card_name, dsl, is_ability=is_ability)

    out_path = Path(args.out) if args.out else EFFECTS_PATH
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(f'\n✓ 已更新 {out_path}，新增 {len(results)} 張卡')


if __name__ == '__main__':
    main()
