import copy
import random

# --- 基礎卡片物件 ---
class Card:
    def __init__(self, id, name, category, **kwargs):
        self.id = id
        self.name = name
        self.category = category
        self.metadata = kwargs

class Pokemon(Card):
    def __init__(self, id, name, stage, hp, types=[], is_ace_spec=False, **kwargs):
        super().__init__(id, name, 'Pokemon', **kwargs)
        self.stage = stage
        self.hp = int(hp) if str(hp).isdigit() else 0
        self.types = types if isinstance(types, list) else []
        self.is_ace_spec = is_ace_spec

        # 狀態記錄
        self.attached_energies = []
        self.evolved_from = None
        self.damage_counters = 0
        self.tool = None # 新增：掛載道具裝備

        self.attacks = kwargs.get('attacks', [])
        self.abilities = kwargs.get('abilities', [])
        self.retreat_cost = kwargs.get('retreatCost', [])

class Trainer(Card):
    def __init__(self, id, name, sub_category, is_ace_spec=False, **kwargs):
        super().__init__(id, name, 'Trainer', **kwargs)
        self.sub_category = sub_category
        self.is_ace_spec = is_ace_spec

class Energy(Card):
    def __init__(self, id, name, sub_category, **kwargs):
        super().__init__(id, name, 'Energy', **kwargs)
        self.sub_category = sub_category
        self.provides = kwargs.get('provides', [name.replace('基本', '').replace('能量', '')])

# --- 遊戲狀態機 ---
class GameState:
    def __init__(self, deck_list):
        self.deck = deck_list
        self.hand = []
        self.active_pokemon = None
        self.bench = []
        self.prizes = []
        self.discard_pile = []

        self.stadium = None # 新增：當前場上的競技場
        self.energy_attached_this_turn = False
        self.supporter_played_this_turn = False

    def clone(self):
        return copy.deepcopy(self)

    def shuffle_deck(self):
        random.shuffle(self.deck)

    def setup_active_pokemon(self):
        basics_in_hand = [c for c in self.hand if isinstance(c, Pokemon) and c.stage == 'Basic']
        if not basics_in_hand: return False

        basics_in_hand.sort(key=lambda x: x.hp, reverse=True)
        # 優先推其他怪，盡量不推可達鴨上戰鬥區
        active_candidates = [p for p in basics_in_hand if "可達鴨" not in p.name]
        if active_candidates:
            self.active_pokemon = active_candidates[0]
        else:
            self.active_pokemon = basics_in_hand[0] # 真的只剩可達鴨只好上

        self.hand.remove(self.active_pokemon)

        for p in list(basics_in_hand):
            if p != self.active_pokemon and len(self.bench) < 5:
                self.bench.append(p)
                self.hand.remove(p)
        return True

    # ==========================================
    # 支援者邏輯
    # ==========================================
    def play_supporter_crispin(self):
        """支援者：赤松 (抓兩張不同基本能量，一張填給寶可夢，一張入手)"""
        if self.supporter_played_this_turn: return False, ["此回合已用過支援者"]
        energies = [c for c in self.deck if isinstance(c, Energy)]
        if not energies: return False, ["牌庫無能量"]

        # 尋找不同屬性的能量
        unique_energies = {}
        for e in energies:
            etype = e.provides[0] if e.provides else "Colorless"
            if etype not in unique_energies: unique_energies[etype] = e

        if len(unique_energies) == 0: return False, ["無合法能量"]
        fetched = list(unique_energies.values())[:2] # 最多抓兩種

        for e in fetched:
            self.deck.remove(e)

        # 智能填能：直接給戰鬥區
        if len(fetched) > 0 and self.active_pokemon:
            self.active_pokemon.attached_energies.append(fetched[0])
        elif len(fetched) > 0:
            self.hand.append(fetched[0])

        if len(fetched) > 1:
            self.hand.append(fetched[1]) # 第二張收進手牌

        self.supporter_played_this_turn = True
        self.shuffle_deck()
        return True, [e.name for e in fetched]

    def play_supporter_lillie(self):
        """支援者：莉莉艾的決意 (洗回手牌，抽 8 張)"""
        if self.supporter_played_this_turn: return False, ["此回合已用過支援者"]

        # 1. 把手牌全部加到牌庫尾端
        self.deck.extend(self.hand)

        # 2. 直接清空手牌
        self.hand = []

        # 3. 記得洗牌！
        self.shuffle_deck()

        # 4. 防呆檢查：確保牌庫夠 8 張牌可以抽
        draw_count = min(8, len(self.deck))
        for _ in range(draw_count):
            self.hand.append(self.deck.pop(0))

        self.supporter_played_this_turn = True
        return True, [f"洗回手牌並抽了 {draw_count} 張牌"]

    def play_supporter_brock(self):
        """支援者：小剛的發掘 (從牌庫選擇最多兩張基礎寶可夢，或一張進化寶可夢加入手牌)"""
        if self.supporter_played_this_turn: return False, ["此回合已用過支援者"]

        pokemons_in_deck = [c for c in self.deck if isinstance(c, Pokemon)]
        if not pokemons_in_deck:
            self.supporter_played_this_turn = True
            self.shuffle_deck()
            return True, ["牌庫無寶可夢"] # 發動成功但沒找到

        fetched = []

        # 智能邏輯 1：優先找「可以進化場上寶可夢」的進化型 (抓 1 張)
        field_pokemons = self.bench + ([self.active_pokemon] if self.active_pokemon else [])
        field_names = [p.name for p in field_pokemons]

        evolution_target = None
        for p in pokemons_in_deck:
            if p.stage != 'Basic':
                # 簡單進化鏈判斷
                if (p.name == "多龍奇" and "多龍梅西亞" in field_names) or \
                    (p.name == "多龍巴魯托ex" and "多龍奇" in field_names) or \
                    ("土龍節節" in p.name and "土龍弟弟" in field_names):
                    evolution_target = p
                    break

        if evolution_target:
            fetched.append(evolution_target)
            self.deck.remove(evolution_target)
        else:
            # 智能邏輯 2：若不需進化，退而求其次抓最多兩張基礎寶可夢
            basics = [p for p in pokemons_in_deck if p.stage == 'Basic']
            # 一樣把可達鴨的優先級降到最低
            basics.sort(key=lambda x: 1 if "可達鴨" in x.name else 0)

            for _ in range(min(2, len(basics))):
                target = basics.pop(0)
                fetched.append(target)
                self.deck.remove(target)

        for c in fetched:
            self.hand.append(c)

        self.supporter_played_this_turn = True
        self.shuffle_deck()
        return True, [c.name for c in fetched]

    def play_supporter_acerola(self):
        if self.supporter_played_this_turn: return False, ["此回合已用過支援者"]
        self.supporter_played_this_turn = True
        return True, ["發動阿塞蘿拉"]

    def play_supporter_empty(self):
        if self.supporter_played_this_turn: return False, ["此回合已用過支援者"]
        self.supporter_played_this_turn = True
        return True, ["空指令"]

    def play_supporter_boss(self):
        """支援者：老大的指令"""
        if self.supporter_played_this_turn: return False, ["此回合已用過支援者"]
        self.supporter_played_this_turn = True
        return True, ["假裝拉出對手備戰"]

    # ==========================================
    # 物品與場地邏輯
    # ==========================================
    def play_item_buddy_poffin(self):
        available_space = 5 - len(self.bench)
        if available_space <= 0: return False, []

        eligible_targets = [c for c in self.deck if isinstance(c, Pokemon) and c.stage == 'Basic' and c.hp <= 70]
        if not eligible_targets: return False, []

        # 智能邏輯：把可達鴨的優先級降到最低 (除非沒怪了不然不抓)
        eligible_targets.sort(key=lambda x: 1 if "可達鴨" in x.name else 0)

        pulled_names = []
        for _ in range(min(2, available_space, len(eligible_targets))):
            target = eligible_targets.pop(0)
            self.deck.remove(target)
            self.bench.append(target)
            pulled_names.append(target.name)

        self.shuffle_deck()
        return True, pulled_names

    def play_tool(self, card):
        """裝備道具：英雄斗篷"""
        if not self.active_pokemon: return False, ["無戰鬥區寶可夢"]
        if self.active_pokemon.tool: return False, ["已裝備道具"]

        self.active_pokemon.tool = card
        if "英雄斗篷" in card.name:
            self.active_pokemon.hp += 100 # ACE SPEC 效果
        return True, [f"裝備 {card.name}"]

    def play_stadium(self, card):
        """放置競技場：險惡廢墟"""
        if self.stadium and self.stadium.name == card.name:
            return False, ["同名競技場已在場上，無法覆蓋"]
        self.stadium = card
        return True, [f"放置競技場：{card.name}"]

    def play_item_night_stretcher(self):
        """物品：夜間擔架 (從棄牌區拿回一張寶可夢或能量)"""
        eligible = [c for c in self.discard_pile if isinstance(c, (Pokemon, Energy))]
        if not eligible: return False, ["棄牌區沒目標"]

        target = eligible.pop(0)
        self.discard_pile.remove(target)
        self.hand.append(target)
        return True, [target.name]

    def play_item_ultra_ball(self):
        if len(self.hand) < 2: return False, []

        self.hand.sort(key=lambda c: 0 if isinstance(c, Energy) else (1 if "寶芬" in c.name else 2))
        discarded_1 = self.hand.pop(0)
        discarded_2 = self.hand.pop(0)
        self.discard_pile.extend([discarded_1, discarded_2])

        pokemons_in_deck = [c for c in self.deck if isinstance(c, Pokemon)]
        if not pokemons_in_deck:
            self.shuffle_deck()
            return True, ["無目標"]

        target = next((p for p in pokemons_in_deck if "多龍巴魯托ex" in p.name), None)
        if not target: target = pokemons_in_deck[0]

        self.deck.remove(target)
        self.hand.append(target)
        self.shuffle_deck()
        return True, [target.name]

    def play_item_pokegear(self):
        if len(self.deck) == 0: return False, []

        look_count = min(7, len(self.deck))
        top_cards = self.deck[:look_count]
        self.deck = self.deck[look_count:]

        supporters = [c for c in top_cards if isinstance(c, Trainer) and c.sub_category == 'Supporter']
        found = []
        if supporters:
            target = supporters[0]
            self.hand.append(target)
            top_cards.remove(target)
            found.append(target.name)

        self.deck.extend(top_cards)
        self.shuffle_deck()
        return True, found

    def attach_energy_from_hand(self, card):
        if self.energy_attached_this_turn: return False, ["一回合只能手填一次"]
        if not self.active_pokemon: return False, ["沒有戰鬥區寶可夢"]

        self.active_pokemon.attached_energies.append(card)
        self.energy_attached_this_turn = True
        return True, [f"貼附 {card.name}"]

    def evolve_pokemon(self, card):
        if not self.active_pokemon: return False, ["沒有目標"]

        valid_evolution = False
        if card.name == "多龍奇" and self.active_pokemon.name == "多龍梅西亞": valid_evolution = True
        if card.name == "多龍巴魯托ex" and self.active_pokemon.name == "多龍奇": valid_evolution = True
        if "土龍節節" in card.name and self.active_pokemon.name == "土龍弟弟": valid_evolution = True

        if valid_evolution:
            card.evolved_from = self.active_pokemon
            card.attached_energies = self.active_pokemon.attached_energies
            self.active_pokemon = card
            return True, [f"進化為 {card.name}"]

        return False, ["無法進化"]

    def perform_attack(self):
        """新增：判斷戰鬥區寶可夢是否具備發動招式的條件"""
        if not self.active_pokemon: return False, ["沒有戰鬥區寶可夢"]

        # 由於 JSON 有提供 attacks 參數，我們檢查能量是否足夠 (簡化版：只要有能量就當作能攻擊)
        # 未來可以進階比對 attacks[0]['cost'] 與 attached_energies 的屬性
        if self.active_pokemon.attacks and len(self.active_pokemon.attached_energies) > 0:
            attack_name = self.active_pokemon.attacks[0].get('name', '招式')
            return True, [f"使用招式：{attack_name}"]

        return False, ["能量不足或無法攻擊"]

    def simulate_turn_one(self):
        # 保持原本供前端呈現的簡單邏輯
        action_log = []
        self.setup_active_pokemon()
        if self.active_pokemon: action_log.append(f"開局推上前台: {self.active_pokemon.name}")
        return action_log

# --- JSON 解析器 (全面升級) ---
def parse_deck(raw_deck_data):
    parsed_cards = []
    for item in raw_deck_data:
        count = item.get('count', 1)
        for i in range(count):
            unique_id = f"{item.get('id', 'unknown')}-{i}"
            cat = item.get('category', '')

            # 過濾掉基本屬性，剩下的全部打包成 kwargs 傳給物件
            basic_keys = ['id', 'name', 'category', 'count', 'stage', 'hp', 'types', 'is_ace_spec', 'subCategory']
            kwargs = {k: v for k, v in item.items() if k not in basic_keys}

            if cat == 'Pokemon':
                card = Pokemon(unique_id, item.get('name', ''), item.get('stage', 'Basic'), item.get('hp', 0), item.get('types', []), item.get('is_ace_spec', False), **kwargs)
            elif cat == 'Trainer':
                card = Trainer(unique_id, item.get('name', ''), item.get('subCategory', ''), item.get('is_ace_spec', False), **kwargs)
            else:
                card = Energy(unique_id, item.get('name', ''), item.get('subCategory', 'Basic'), **kwargs)

            card.image = item.get('image', '')
            parsed_cards.append(card)
    return parsed_cards

def simulate_opening_hand(raw_deck_data):
    cards = parse_deck(raw_deck_data)
    state = GameState(cards)
    state.shuffle_deck()
    mulligan_count = 0

    while True:
        state.hand = state.deck[:7]
        remaining = state.deck[7:]
        has_basic = any(isinstance(c, Pokemon) and c.stage == 'Basic' for c in state.hand)
        if has_basic:
            state.deck = remaining
            break
        mulligan_count += 1
        state.deck = remaining + state.hand
        state.hand = []
        state.shuffle_deck()

    state.prizes = state.deck[:6]
    state.deck = state.deck[6:]
    initial_hand_data = [{"id": c.id, "name": c.name, "image": getattr(c, 'image', '')} for c in state.hand]
    turn_one_logs = state.simulate_turn_one()

    return {
        "initialHand": initial_hand_data,
        "remainingHand": [{"id": c.id, "name": c.name, "image": getattr(c, 'image', '')} for c in state.hand],
        "active": {"id": state.active_pokemon.id, "name": state.active_pokemon.name, "image": getattr(state.active_pokemon, 'image', '')} if state.active_pokemon else None,
        "bench": [{"id": c.id, "name": c.name, "image": getattr(c, 'image', '')} for c in state.bench],
        "prizes": [{"id": c.id, "name": c.name, "image": getattr(c, 'image', '')} for c in state.prizes],
        "logs": turn_one_logs,
        "remainingDeckCount": len(state.deck),
        "mulliganCount": mulligan_count
    }
