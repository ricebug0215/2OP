import copy
import random

# --- 基礎卡片物件 ---
class Card:
    def __init__(self, id, name, category):
        self.id = id
        self.name = name
        self.category = category

class Pokemon(Card):
    def __init__(self, id, name, stage, hp, types, is_ace_spec=False):
        super().__init__(id, name, 'Pokemon')
        self.stage = stage
        self.hp = hp
        self.types = types
        self.is_ace_spec = is_ace_spec

class Trainer(Card):
    def __init__(self, id, name, sub_category, is_ace_spec=False):
        super().__init__(id, name, 'Trainer')
        self.sub_category = sub_category
        self.is_ace_spec = is_ace_spec

class Energy(Card):
    def __init__(self, id, name, sub_category):
        super().__init__(id, name, 'Energy')
        self.sub_category = sub_category

# --- 遊戲狀態機 ---
class GameState:
    def __init__(self, deck_list):
        self.deck = deck_list
        self.hand = []
        self.active_pokemon = None
        self.bench = []
        self.prizes = []
        self.discard_pile = []

    def clone(self):
        return copy.deepcopy(self)

    def shuffle_deck(self):
        random.shuffle(self.deck)

    def setup_active_pokemon(self):
        """開局準備：挑選高血量基礎寶可夢放戰鬥區，其餘放備戰"""
        basics_in_hand = [c for c in self.hand if isinstance(c, Pokemon) and c.stage == 'Basic']
        if not basics_in_hand: return False
            
        basics_in_hand.sort(key=lambda x: int(x.hp) if str(x.hp).isdigit() else 0, reverse=True)
        
        self.active_pokemon = basics_in_hand.pop(0)
        self.hand.remove(self.active_pokemon)
        
        for p in list(basics_in_hand):
            if len(self.bench) < 5:
                self.bench.append(p)
                self.hand.remove(p)
        return True

    def play_item_buddy_poffin(self):
        """物品卡 AI：好友寶芬"""
        available_space = 5 - len(self.bench)
        if available_space <= 0:
            return False, []
            
        eligible_targets = [
            c for c in self.deck 
            if isinstance(c, Pokemon) and c.stage == 'Basic' and str(c.hp).isdigit() and int(c.hp) <= 70
        ]
        
        if not eligible_targets:
            return False, []
            
        num_to_pull = min(2, available_space, len(eligible_targets))
        
        pulled_names = []
        for _ in range(num_to_pull):
            target = eligible_targets.pop(0)
            self.deck.remove(target)
            self.bench.append(target)
            pulled_names.append(target.name)
            
        self.shuffle_deck()
        return True, pulled_names

    def simulate_turn_one(self):
        """先攻一回合腳本"""
        action_log = []
        
        self.setup_active_pokemon()
        if self.active_pokemon:
            action_log.append(f"開局推上前台: {self.active_pokemon.name}")
        
        items_in_hand = [c for c in self.hand if isinstance(c, Trainer) and c.sub_category == 'Item']
        
        for item in items_in_hand:
            if "好友寶芬" in item.name:
                success, pulled_names = self.play_item_buddy_poffin()
                if success:
                    self.hand.remove(item)
                    self.discard_pile.append(item)
                    action_log.append(f"打出 {item.name}，將 {', '.join(pulled_names)} 呼喚至備戰區！")
                    
        return action_log

# --- 與 Server 溝通的介面 ---
def parse_deck(raw_deck_data):
    parsed_cards = []
    for item in raw_deck_data:
        count = item.get('count', 1)
        for i in range(count):
            unique_id = f"{item['id']}-{i}"
            if item['category'] == 'Pokemon':
                card = Pokemon(unique_id, item['name'], item.get('stage', 'Basic'), item.get('hp', 0), item.get('types', []), item.get('is_ace_spec', False))
            elif item['category'] == 'Trainer':
                card = Trainer(unique_id, item['name'], item.get('subCategory', ''), item.get('is_ace_spec', False))
            else:
                card = Energy(unique_id, item['name'], item.get('subCategory', 'Basic'))
            card.image = item.get('image', '')
            parsed_cards.append(card)
    return parsed_cards

def simulate_opening_hand(raw_deck_data):
    cards = parse_deck(raw_deck_data)
    state = GameState(cards)
    
    state.shuffle_deck()
    mulligan_count = 0
    
    # 執行起手與 Mulligan 邏輯
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
        
        if mulligan_count > 15:
            state.deck = remaining
            break
            
    state.prizes = state.deck[:6]
    state.deck = state.deck[6:]
    
    # 備份原始手牌
    initial_hand_data = [{"id": c.id, "name": c.name, "image": getattr(c, 'image', '')} for c in state.hand]
    
    # AI 執行操作
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