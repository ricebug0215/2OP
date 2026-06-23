"""
PTCG 遊戲引擎 — T1/T2 展開模擬用
"""

import json
import random
from copy import deepcopy
from pathlib import Path


# ═══════════════════════════════════════
#  資料模型
# ═══════════════════════════════════════

class Card:
    __slots__ = ('name', 'category', 'sub_type', 'stage', 'hp',
                 'poke_type', 'is_ace_spec', 'regulation_mark',
                 'evolves_from', 'image_url')

    def __init__(self, name, category, **kw):
        self.name = name
        self.category = category
        self.sub_type = kw.get('sub_type', '')
        self.stage = kw.get('stage', '')
        self.hp = kw.get('hp', 0)
        self.poke_type = kw.get('poke_type', '')
        self.is_ace_spec = kw.get('is_ace_spec', False)
        self.regulation_mark = kw.get('regulation_mark', '')
        self.evolves_from = kw.get('evolves_from', '')
        self.image_url = kw.get('image_url', '')

    def __repr__(self):
        return f'{self.name}({self.category})'


class PokemonSlot:
    """場上的一隻寶可夢"""

    def __init__(self, card: Card):
        self.cards = [card]
        self.attached_energy: list[Card] = []
        self.turns_in_play = 0

    @property
    def top(self) -> Card:
        return self.cards[-1]

    @property
    def base(self) -> Card:
        return self.cards[0]

    @property
    def name(self) -> str:
        return self.top.name

    @property
    def stage(self) -> str:
        return self.top.stage

    @property
    def hp(self) -> int:
        return self.top.hp

    def can_evolve_to(self, evo_card: Card, skip_stage=False) -> bool:
        if skip_stage:
            return (self.stage == '基礎' and evo_card.stage == '2階進化')
        return (
            (self.stage == '基礎' and evo_card.stage == '1階進化') or
            (self.stage == '1階進化' and evo_card.stage == '2階進化')
        )

    def evolve(self, evo_card: Card):
        self.cards.append(evo_card)

    def __repr__(self):
        e = f' [{len(self.attached_energy)}E]' if self.attached_energy else ''
        chain = '→'.join(c.name for c in self.cards)
        return f'<{chain}{e}>'


# ═══════════════════════════════════════
#  遊戲狀態
# ═══════════════════════════════════════

class GameState:
    MAX_BENCH = 5
    HAND_SIZE = 7
    PRIZE_COUNT = 6

    def __init__(self):
        self.deck: list[Card] = []
        self.hand: list[Card] = []
        self.discard: list[Card] = []
        self.prizes: list[Card] = []
        self.active: PokemonSlot | None = None
        self.bench: list[PokemonSlot] = []
        self.supporter_used = False
        self.energy_attached = False
        self.turn = 0
        self.going_first = True

    # ── 查詢 ──

    @property
    def bench_open(self) -> int:
        return self.MAX_BENCH - len(self.bench)

    @property
    def all_in_play(self) -> list[PokemonSlot]:
        slots = []
        if self.active:
            slots.append(self.active)
        slots.extend(self.bench)
        return slots

    def hand_indices(self, predicate) -> list[int]:
        return [i for i, c in enumerate(self.hand) if predicate(c)]

    def deck_indices(self, predicate) -> list[int]:
        return [i for i, c in enumerate(self.deck) if predicate(c)]

    # ── 基本操作 ──

    def draw_cards(self, n: int) -> list[Card]:
        drawn = self.deck[:n]
        self.deck = self.deck[n:]
        self.hand.extend(drawn)
        return drawn

    def remove_from_hand(self, idx: int) -> Card:
        return self.hand.pop(idx)

    def discard_from_hand(self, indices: list[int]) -> list[Card]:
        indices_sorted = sorted(indices, reverse=True)
        discarded = []
        for i in indices_sorted:
            discarded.append(self.hand.pop(i))
        self.discard.extend(discarded)
        return discarded

    def remove_from_deck(self, indices: list[int]) -> list[Card]:
        indices_sorted = sorted(indices, reverse=True)
        removed = []
        for i in indices_sorted:
            removed.append(self.deck.pop(i))
        return removed

    def put_on_bench_card(self, card: Card) -> bool:
        if len(self.bench) >= self.MAX_BENCH:
            return False
        if card.category != 'Pokemon' or card.stage != '基礎':
            return False
        self.bench.append(PokemonSlot(card))
        return True

    def shuffle_deck(self):
        random.shuffle(self.deck)

    def switch_active_bench(self, bench_idx: int):
        if self.active and 0 <= bench_idx < len(self.bench):
            self.active, self.bench[bench_idx] = self.bench[bench_idx], self.active

    def start_turn(self):
        self.turn += 1
        self.supporter_used = False
        self.energy_attached = False
        for slot in self.all_in_play:
            slot.turns_in_play += 1
        self.draw_cards(1)

    def can_play_supporter(self) -> bool:
        if self.supporter_used:
            return False
        if self.turn == 1 and self.going_first:
            return False
        return True

    def clone(self) -> 'GameState':
        return deepcopy(self)

    def _card_dict(self, c: 'Card') -> dict:
        return {'name': c.name, 'category': c.category, 'image': c.image_url,
                'stage': c.stage, 'hp': c.hp, 'sub_type': c.sub_type}

    def _slot_dict(self, s: 'PokemonSlot') -> dict:
        return {
            'name': s.name, 'image': s.top.image_url, 'stage': s.stage,
            'hp': s.hp, 'energy': len(s.attached_energy),
            'energy_cards': [self._card_dict(e) for e in s.attached_energy],
            'chain': [self._card_dict(c) for c in s.cards],
            'repr': repr(s),
        }

    def summary(self) -> dict:
        return {
            'turn': self.turn,
            'hand': [c.name for c in self.hand],
            'hand_cards': [self._card_dict(c) for c in self.hand],
            'hand_size': len(self.hand),
            'active': repr(self.active) if self.active else None,
            'active_detail': self._slot_dict(self.active) if self.active else None,
            'bench': [repr(s) for s in self.bench],
            'bench_details': [self._slot_dict(s) for s in self.bench],
            'bench_count': len(self.bench),
            'deck_size': len(self.deck),
            'discard_size': len(self.discard),
            'discard_cards': [self._card_dict(c) for c in self.discard],
            'prizes': len(self.prizes),
            'prize_cards': [self._card_dict(c) for c in self.prizes],
        }


# ═══════════════════════════════════════
#  DSL 篩選器
# ═══════════════════════════════════════

def matches_filter(card: Card, f: dict) -> bool:
    if 'category' in f and card.category != f['category']:
        return False
    if 'category_in' in f:
        matched = False
        for cat in f['category_in']:
            if cat == 'BasicEnergy':
                if card.category == 'Energy' and card.sub_type == '基本能量卡':
                    matched = True
            elif card.category == cat:
                matched = True
        if not matched:
            return False
    if 'stage' in f and card.stage != f['stage']:
        return False
    if 'stage_in' in f and card.stage not in f['stage_in']:
        return False
    if 'hp_lte' in f and card.hp > f['hp_lte']:
        return False
    if 'hp_gte' in f and card.hp < f['hp_gte']:
        return False
    if 'poke_type' in f and card.poke_type != f['poke_type']:
        return False
    if 'sub_type' in f and card.sub_type != f['sub_type']:
        return False
    if 'name' in f and card.name != f['name']:
        return False
    return True


# ═══════════════════════════════════════
#  決策者介面（Playbook / RL 共用）
# ═══════════════════════════════════════

class DecisionMaker:
    """AI 或 Playbook 的決策介面"""

    def choose_action(self, state: GameState) -> dict | None:
        """回傳下一步動作，None = 結束回合。
        動作格式: {"type": "play_card", "hand_idx": int}
                  {"type": "attach_energy", "hand_idx": int, "target_idx": int}
                  {"type": "retreat"}
        """
        raise NotImplementedError

    def choose_targets(self, candidates: list, count: int, context: str) -> list[int]:
        """從候選列表中選 count 個（回傳 index）"""
        raise NotImplementedError

    def choose_option(self, options: list[str], context: str) -> str:
        """多選一（回傳 option id）"""
        raise NotImplementedError

    def choose_bench_slot(self, bench: list[PokemonSlot], context: str) -> int:
        """選擇備戰區的一隻"""
        raise NotImplementedError

    def choose_discard(self, hand: list[Card], count: int, context: str) -> list[int]:
        """選擇從手牌丟棄哪些牌（回傳 hand index）"""
        raise NotImplementedError


# ═══════════════════════════════════════
#  效果執行引擎
# ═══════════════════════════════════════

class EffectEngine:
    def __init__(self, effects_path: str = 'card_effects.json'):
        with open(effects_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        self.card_db: dict = raw.get('cards', {})
        self.ability_db: dict = raw.get('abilities', {})

    def get_effect(self, card_name: str) -> dict | None:
        return self.card_db.get(card_name)

    def can_play(self, card: Card, state: GameState) -> bool:
        effect = self.get_effect(card.name)
        if not effect:
            return False

        sub = effect.get('sub_type', card.sub_type)
        if sub == '支援者卡' and not state.can_play_supporter():
            return False

        if effect.get('is_ace_spec') and card.is_ace_spec:
            pass

        cost = effect.get('cost')
        if cost and cost.get('action') == 'discard_from_hand':
            needed = cost['count']
            available = len(state.hand) - 1
            if available < needed:
                return False

        if effect.get('mode') == 'choose_one':
            return self._any_option_viable(effect['options'], state)

        return self._effects_viable(effect.get('effects', []), state, card)

    def _any_option_viable(self, options: list, state: GameState) -> bool:
        for opt in options:
            viable = True
            for eff in opt.get('effects', []):
                if eff['action'] == 'recover':
                    matches = [c for c in state.discard if matches_filter(c, eff.get('filter', {}))]
                    if not matches:
                        viable = False
                        break
            if viable:
                return True
        return False

    def _effects_viable(self, effects: list, state: GameState, card: Card) -> bool:
        for eff in effects:
            act = eff['action']
            if act == 'search_deck':
                dest = eff.get('destination', 'hand')
                if dest == 'bench' and state.bench_open <= 0:
                    return False
                filt = eff.get('filter', {})
                if not any(matches_filter(c, filt) for c in state.deck):
                    return False
            if act == 'switch_active':
                if not state.bench:
                    return False
            if act == 'evolve':
                if state.turn < 2:
                    return False
                has_target = False
                skip = eff.get('skip_stage', False)
                for slot in state.all_in_play:
                    if slot.turns_in_play < 1:
                        continue
                    if skip and slot.stage != '基礎':
                        continue
                    for hc in state.hand:
                        if hc.name == card.name:
                            continue
                        if hc.category == 'Pokemon' and slot.can_evolve_to(hc, skip_stage=skip):
                            has_target = True
                            break
                    if has_target:
                        break
                if not has_target:
                    return False
        return True

    def execute(self, card: Card, hand_idx: int, state: GameState, dm: DecisionMaker) -> dict:
        """執行卡牌效果，回傳 {"success": bool, "steps": list[str]}"""
        effect = self.get_effect(card.name)
        if not effect:
            return {'success': False, 'steps': []}

        steps: list[str] = []
        sub = effect.get('sub_type', card.sub_type)

        cost = effect.get('cost')
        if cost and cost.get('action') == 'discard_from_hand':
            needed = cost['count']
            available = [(i, c) for i, c in enumerate(state.hand) if i != hand_idx]
            if len(available) < needed:
                return {'success': False, 'steps': []}
            chosen_local = dm.choose_discard(
                [c for _, c in available], needed, f'{card.name} cost'
            )
            chosen = [available[ci][0] for ci in chosen_local[:needed]]
            discarded_names = [state.hand[ci].name for ci in chosen]
            adjusted_hand_idx = hand_idx
            for ci in sorted(chosen, reverse=True):
                if ci < hand_idx:
                    adjusted_hand_idx -= 1
            state.discard_from_hand(chosen)
            hand_idx = adjusted_hand_idx
            steps.append(f'丟棄 {_join(discarded_names)} 作為代價')

        state.remove_from_hand(hand_idx)
        state.discard.append(card)

        if sub == '支援者卡':
            state.supporter_used = True

        if effect.get('mode') == 'choose_one':
            viable_ids = []
            for opt in effect['options']:
                if self._option_viable(opt, state):
                    viable_ids.append(opt['id'])
            if not viable_ids:
                return {'success': True, 'steps': steps}
            chosen_id = dm.choose_option(viable_ids, f'{card.name} mode')
            steps.append(f'選擇模式: {chosen_id}')
            opt_data = next(o for o in effect['options'] if o['id'] == chosen_id)
            for eff in opt_data.get('effects', []):
                steps.extend(self._run_effect(eff, state, dm, card.name))
        else:
            for eff in effect.get('effects', []):
                steps.extend(self._run_effect(eff, state, dm, card.name))

        return {'success': True, 'steps': steps}

    def _option_viable(self, opt: dict, state: GameState) -> bool:
        for eff in opt.get('effects', []):
            if eff['action'] == 'recover':
                matches = [c for c in state.discard if matches_filter(c, eff.get('filter', {}))]
                if not matches:
                    return False
        return True

    def _run_effect(self, eff: dict, state: GameState, dm: DecisionMaker, card_name: str) -> list[str]:
        action = eff['action']
        steps: list[str] = []

        if action == 'draw':
            n = eff['count']
            drawn = state.draw_cards(n)
            steps.append(f'抽 {n} 張: {_join(c.name for c in drawn)}')

        elif action == 'search_deck':
            filt = eff.get('filter', {})
            up_to = eff.get('up_to', 1)
            dest = eff.get('destination', 'hand')
            dest_label = {'hand': '手牌', 'bench': '備戰區', 'attach': '寶可夢'}.get(dest, dest)
            candidates = [(i, c) for i, c in enumerate(state.deck) if matches_filter(c, filt)]
            if not candidates:
                state.shuffle_deck()
                steps.append('牌庫中無符合條件的牌')
                return steps
            pick_count = min(up_to, len(candidates))
            if dest == 'bench':
                pick_count = min(pick_count, state.bench_open)
            chosen_indices = dm.choose_targets(
                [c for _, c in candidates], pick_count,
                f'{card_name} search'
            )
            deck_indices = [candidates[i][0] for i in chosen_indices]
            picked = state.remove_from_deck(deck_indices)
            if dest == 'hand':
                state.hand.extend(picked)
            elif dest == 'bench':
                for p in picked:
                    state.put_on_bench_card(p)
            elif dest == 'attach':
                for p in picked:
                    slots = state.all_in_play
                    if slots:
                        target_idx = dm.choose_bench_slot(
                            slots, f'{card_name} attach energy')
                        slots[target_idx].attached_energy.append(p)
                        dest_label = f'貼在 {slots[target_idx].name} 身上'
            state.shuffle_deck()
            steps.append(f'從牌庫搜尋 {_join(c.name for c in picked)} → {dest_label}')

        elif action == 'look_top':
            count = eff['count']
            top_cards = state.deck[:count]
            state.deck = state.deck[count:]
            pick_filter = eff.get('pick_filter', {})
            pick_up_to = eff.get('pick_up_to', 1)
            rest_action = eff.get('rest', 'shuffle_back')
            eligible = [(i, c) for i, c in enumerate(top_cards) if matches_filter(c, pick_filter)]
            picked_indices_in_top = []
            if eligible:
                pick_count = min(pick_up_to, len(eligible))
                chosen = dm.choose_targets(
                    [c for _, c in eligible], pick_count,
                    f'{card_name} look_top'
                )
                picked_indices_in_top = [eligible[i][0] for i in chosen]
            picked = [top_cards[i] for i in picked_indices_in_top]
            rest = [c for i, c in enumerate(top_cards) if i not in picked_indices_in_top]
            state.hand.extend(picked)
            rest_label = {'shuffle_back': '洗回牌庫', 'discard': '丟棄', 'bottom': '放回牌庫底'}.get(rest_action, rest_action)
            if rest_action == 'shuffle_back':
                state.deck.extend(rest)
                state.shuffle_deck()
            elif rest_action == 'discard':
                state.discard.extend(rest)
            elif rest_action == 'bottom':
                state.deck.extend(rest)
            steps.append(
                f'查看牌庫頂 {count} 張 → 選擇 {_join(c.name for c in picked) or "無"}，'
                f'剩餘{rest_label}: {_join(c.name for c in rest) or "無"}'
            )

        elif action == 'discard_hand':
            names = [c.name for c in state.hand]
            state.discard.extend(state.hand)
            state.hand.clear()
            steps.append(f'丟棄全部手牌: {_join(names) or "（空）"}')

        elif action == 'shuffle_hand_draw':
            count = eff['count']
            if count == 'prizes_remaining':
                count = len(state.prizes)
            old_hand = [c.name for c in state.hand]
            state.deck.extend(state.hand)
            state.hand.clear()
            state.shuffle_deck()
            drawn = state.draw_cards(count)
            steps.append(f'手牌洗入牌庫，抽 {count} 張: {_join(c.name for c in drawn)}')

        elif action == 'switch_active':
            if state.bench:
                idx = dm.choose_bench_slot(state.bench, f'{card_name} switch')
                old_active = state.active.name if state.active else '?'
                new_active = state.bench[idx].name
                state.switch_active_bench(idx)
                steps.append(f'替換戰鬥區: {old_active} ↔ {new_active}')

        elif action == 'evolve':
            skip = eff.get('skip_stage', False)
            evo_candidates = []
            for hand_i, hc in enumerate(state.hand):
                if hc.category != 'Pokemon':
                    continue
                if skip and hc.stage != '2階進化':
                    continue
                if not skip and hc.stage not in ('1階進化', '2階進化'):
                    continue
                for slot_i, slot in enumerate(state.all_in_play):
                    if slot.turns_in_play < 1:
                        continue
                    if skip and slot.stage != '基礎':
                        continue
                    if slot.can_evolve_to(hc, skip_stage=skip):
                        evo_candidates.append((hand_i, slot_i, hc, slot))

            if evo_candidates:
                chosen = dm.choose_targets(
                    [(hc.name, slot.name) for _, _, hc, slot in evo_candidates],
                    1, f'{card_name} evolve'
                )
                if chosen:
                    hi, si, hc, slot = evo_candidates[chosen[0]]
                    old_name = slot.name
                    actual_hi = state.hand.index(hc)
                    evo_card = state.hand.pop(actual_hi)
                    slot.evolve(evo_card)
                    method = '（神奇糖果）' if skip else ''
                    steps.append(f'進化{method}: {old_name} → {evo_card.name}')

        elif action == 'recover':
            filt = eff.get('filter', {})
            count = eff.get('count', 1)
            dest = eff.get('destination', 'hand')
            dest_label = '手牌' if dest == 'hand' else '牌庫'
            candidates = [(i, c) for i, c in enumerate(state.discard) if matches_filter(c, filt)]
            if not candidates:
                return steps
            pick_count = min(count, len(candidates))
            chosen = dm.choose_targets(
                [c for _, c in candidates], pick_count,
                f'{card_name} recover'
            )
            discard_indices = [candidates[i][0] for i in chosen]
            recovered = []
            for i in sorted(discard_indices, reverse=True):
                recovered.append(state.discard.pop(i))
            if dest == 'hand':
                state.hand.extend(recovered)
            elif dest == 'deck':
                state.deck.extend(recovered)
                state.shuffle_deck()
            steps.append(f'從棄牌區回收 {_join(c.name for c in recovered)} → {dest_label}')

        return steps

    def get_ability(self, pokemon_name: str) -> dict | None:
        return self.ability_db.get(pokemon_name)

    def execute_ability(self, pokemon_name: str, state: GameState, dm: DecisionMaker) -> dict:
        ability = self.get_ability(pokemon_name)
        if not ability:
            return {'success': False, 'steps': []}
        steps: list[str] = []
        for eff in ability.get('effects', []):
            steps.extend(self._run_effect(eff, state, dm, f'{pokemon_name}（{ability["name"]}）'))
        return {'success': True, 'steps': steps}


def _join(items) -> str:
    names = list(items) if not isinstance(items, list) else items
    return '、'.join(names) if names else ''


# ═══════════════════════════════════════
#  牌組建構
# ═══════════════════════════════════════

def load_master_db() -> list[dict]:
    cards = []
    files = {
        'Pokemon': 'ptcg_full_database.json',
        'Trainer': 'ptcg_trainer_database.json',
        'Energy': 'ptcg_energy_database.json',
    }
    base = Path(__file__).parent
    for category, filename in files.items():
        path = base / filename
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for entry in data:
                    entry['_category'] = category
                cards.extend(data)
    return cards


def find_card_in_db(name: str, master_db: list[dict]) -> dict | None:
    for entry in master_db:
        if entry.get('name') == name:
            return entry
    return None


def dict_to_card(entry: dict, category: str = '') -> Card:
    cat = category or entry.get('_category', entry.get('category', ''))
    return Card(
        name=entry.get('name', ''),
        category=cat,
        sub_type=entry.get('subType', entry.get('sub_type', '')),
        stage=entry.get('stage', ''),
        hp=entry.get('hp', 0),
        poke_type=entry.get('type', ''),
        is_ace_spec=entry.get('isAceSpec', False),
        regulation_mark=entry.get('regulationMark', ''),
        evolves_from=entry.get('evolves_from', ''),
        image_url=entry.get('imageUrl', entry.get('image_url', '')),
    )


def build_deck(deck_list: list[dict], master_db: list[dict] | None = None) -> list[Card]:
    """從牌組列表建構 Card 物件列表。
    deck_list 格式: [{"name": "小火龍", "count": 4, "category": "Pokemon"}, ...]
    category 可省略，會自動從 master_db 查找。
    """
    if master_db is None:
        master_db = load_master_db()

    deck: list[Card] = []
    for entry in deck_list:
        name = entry['name']
        count = entry.get('count', 1)
        db_entry = find_card_in_db(name, master_db)
        if db_entry:
            for _ in range(count):
                deck.append(dict_to_card(db_entry))
        else:
            cat = entry.get('category', 'Unknown')
            for _ in range(count):
                deck.append(Card(
                    name=name,
                    category=cat,
                    sub_type=entry.get('sub_type', ''),
                    stage=entry.get('stage', ''),
                    hp=entry.get('hp', 0),
                    poke_type=entry.get('poke_type', ''),
                ))
    return deck


# ═══════════════════════════════════════
#  遊戲初始化（洗牌、發牌、讓牌）
# ═══════════════════════════════════════

def setup_game(deck: list[Card], going_first: bool = True,
               active_priority: list[str] | None = None,
               bench_priority: list[str] | None = None) -> GameState:
    state = GameState()
    state.deck = list(deck)
    state.going_first = going_first
    state.shuffle_deck()

    mulligan_count = 0
    while mulligan_count <= 20:
        state.hand = state.deck[:GameState.HAND_SIZE]
        state.deck = state.deck[GameState.HAND_SIZE:]
        has_basic = any(
            c.category == 'Pokemon' and c.stage == '基礎'
            for c in state.hand
        )
        if has_basic:
            break
        state.deck.extend(state.hand)
        state.hand.clear()
        state.shuffle_deck()
        mulligan_count += 1

    state.prizes = state.deck[:GameState.PRIZE_COUNT]
    state.deck = state.deck[GameState.PRIZE_COUNT:]

    basics_in_hand = [i for i, c in enumerate(state.hand)
                      if c.category == 'Pokemon' and c.stage == '基礎']

    if not basics_in_hand:
        return state

    if active_priority:
        best_idx = basics_in_hand[0]
        best_rank = 9999
        for idx in basics_in_hand:
            name = state.hand[idx].name
            rank = next((r for r, p in enumerate(active_priority) if p == name), 9999)
            if rank < best_rank:
                best_rank = rank
                best_idx = idx
        active_card = state.hand.pop(best_idx)
    else:
        active_card = state.hand.pop(basics_in_hand[0])
    state.active = PokemonSlot(active_card)

    if bench_priority:
        remaining_basics = [(i, c) for i, c in enumerate(state.hand)
                            if c.category == 'Pokemon' and c.stage == '基礎']
        to_bench = []
        for pname in bench_priority:
            for i, c in remaining_basics:
                if c.name == pname and i not in [x[0] for x in to_bench]:
                    to_bench.append((i, c))
                    break
            if len(to_bench) >= GameState.MAX_BENCH:
                break
        for idx, card in sorted(to_bench, key=lambda x: x[0], reverse=True):
            state.hand.pop(idx)
            state.put_on_bench_card(card)

    return state
