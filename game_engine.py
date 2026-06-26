"""
PTCG 遊戲引擎 — T1/T2 展開模擬用
"""

import json
import random
import re
from copy import deepcopy
from pathlib import Path


# ═══════════════════════════════════════
#  進化關係表 (由 generate_effects.py --evolution 產生)
# ═══════════════════════════════════════

def _load_json_map(filename: str) -> dict:
    path = Path(__file__).parent / filename
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


# {進化卡名: 進化前卡名}
EVOLVES_FROM: dict[str, str] = _load_json_map('evolution_chains.json')

# {寶可夢名: [主力需要的能量屬性]}；[] 表示無色攻擊手(任意能量)
ENERGY_PROFILES: dict[str, list] = _load_json_map('energy_profiles.json')


def energy_type_of(card: 'Card') -> str:
    """從能量卡名解析提供的屬性，例: 基本【火】能量 → 火。無法解析回傳 ''。"""
    if card.category != 'Energy':
        return ''
    m = re.search(r'【(.)】', card.name)
    return m.group(1) if m else ''


def evolution_line_of(name: str) -> set[str]:
    """回傳該卡所屬進化線的所有成員(含自己)，用 EVOLVES_FROM 解析。"""
    # 往上找線根
    root = name
    seen = {root}
    while root in EVOLVES_FROM and EVOLVES_FROM[root] not in seen:
        root = EVOLVES_FROM[root]
        seen.add(root)
    # 往下 BFS
    children: dict[str, list[str]] = {}
    for evo, pre in EVOLVES_FROM.items():
        children.setdefault(pre, []).append(evo)
    members = {root}
    queue = [root]
    while queue:
        cur = queue.pop()
        for ch in children.get(cur, []):
            if ch not in members:
                members.add(ch)
                queue.append(ch)
    return members


def expand_main_attackers(names) -> list[str]:
    """把使用者宣告的主力(可能只點了 ex 或基礎)展開成整條進化線。

    例: ['多龍巴魯托ex'] → ['多龍梅西亞','多龍奇','多龍巴魯托','多龍巴魯托ex']
    這樣不論場上是哪一階都能被辨識為主力。
    """
    expanded = set()
    for n in names or []:
        expanded |= evolution_line_of(n)
    return sorted(expanded)


def is_main_attacker(slot: 'PokemonSlot', main_attackers) -> bool:
    """slot 是否屬於使用者宣告的主力進化線。

    main_attackers 可宣告為線根基礎(多龍梅西亞)或任一階(多龍巴魯托ex)，
    只要 slot 演化鏈(slot.cards)中任一張命中即視為主力。
    """
    if not main_attackers:
        return False
    return any(c.name in main_attackers for c in slot.cards)


def needed_energy_types(slot: 'PokemonSlot', override: dict | None = None,
                        main_attackers=None) -> list[str]:
    """查該寶可夢的能量需求。[] 表示任意能量皆可(無屬性壓力)。

    override:        playbook 可傳入 {寶可夢名: [屬性]} 覆寫自動推導值。
    main_attackers:  若提供(非 None)，只有宣告的主力才回傳屬性需求，
                     其餘寶可夢一律視為任意能量([])，避免把能量壓力
                     錯誤套到非主力(如願增猿、被當後備的土龍)。
                     None 表示不過濾(沿用舊行為，所有有 profile 的線皆生效)。
    """
    override = override or {}
    for c in slot.cards:
        if c.name in override:
            return override[c.name]
    if main_attackers is not None and not is_main_attacker(slot, main_attackers):
        return []
    for c in slot.cards:
        if c.name in ENERGY_PROFILES:
            return ENERGY_PROFILES[c.name]
    return []


def attachable_energy_types(main_attackers=None, override: dict | None = None) -> set[str]:
    """牌組「可貼附」的能量屬性 = 所有宣告主力進化線需要的屬性聯集。

    用途: 區分「填能用能量」與「戰術棄牌用能量」。例如多龍套主力吃火/超，
    牌裡的惡能量是給高級球等代價棄掉的，不該被貼到寶可夢身上。

    回傳空集合表示不限制(未宣告主力，或主力吃無色任意能量) → 沿用舊行為。
    """
    if not main_attackers:
        return set()
    override = override or {}
    types: set[str] = set()
    for name in main_attackers:
        if name in override:
            types.update(override[name])
        elif name in ENERGY_PROFILES:
            types.update(ENERGY_PROFILES[name])
    return types


def pick_energy_for_slot(hand: list, slot: 'PokemonSlot',
                         override: dict | None = None,
                         main_attackers=None) -> int | None:
    """從手牌挑最適合貼給 slot 的能量，回傳 hand index（無可貼能量回傳 None）。

    優先序: 主力仍缺的屬性 > 主力需求屬性 > 任意可貼附能量。
    先以牌組可貼附屬性過濾，牌組用不到的能量(如戰術棄牌的惡能量)一律不貼。
    非主力寶可夢無屬性需求，給任一張可貼附能量即可。
    """
    energy_idxs = [i for i, c in enumerate(hand) if c.category == 'Energy']
    if not energy_idxs:
        return None
    # 牌組可貼附屬性: 非空時排除牌組用不到的能量(留作棄牌資源)
    deck_types = attachable_energy_types(main_attackers, override)
    if deck_types:
        energy_idxs = [i for i in energy_idxs
                       if energy_type_of(hand[i]) in deck_types]
        if not energy_idxs:
            return None  # 手上只有非貼附用能量，不貼
    needed = needed_energy_types(slot, override, main_attackers)
    if not needed:  # 無色攻擊手或非主力，任一可貼附能量皆可
        return energy_idxs[0]
    attached = [energy_type_of(c) for c in slot.attached_energy]
    remaining = [t for t in needed if t not in attached]
    target_types = remaining or needed
    for i in energy_idxs:
        if energy_type_of(hand[i]) in target_types:
            return i
    return energy_idxs[0]  # 無匹配屬性但屬於可貼附範圍，退回任意


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
        # evolves_from 優先取卡牌自身欄位，否則查全域進化表
        pre = evo_card.evolves_from or EVOLVES_FROM.get(evo_card.name, '')

        if skip_stage:
            # 神奇糖果: 基礎 → 2階，需確認 2階確實在此基礎的進化線上
            if not (self.stage == '基礎' and evo_card.stage == '2階進化'):
                return False
            if pre:
                # 往回追一階: 2階的前身(1階)的前身應為當前基礎
                root = EVOLVES_FROM.get(pre, '')
                if root:
                    return root == self.name
            return True  # 無進化表資料時退回階級判斷

        if pre:
            return pre == self.name
        # 無進化表資料時退回階級判斷 (向後相容)
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

    def choose_option(self, options: list[str], state: 'GameState', context: str) -> str:
        """多選一（回傳 option id）"""
        raise NotImplementedError

    def choose_bench_slot(self, bench: list[PokemonSlot], context: str) -> int:
        """選擇備戰區的一隻"""
        raise NotImplementedError

    def choose_attach_slot(self, slots: list[PokemonSlot], energy_card: Card,
                           context: str) -> int:
        """選擇要把某張能量貼給場上哪一隻(預設沿用 choose_bench_slot)。
        覆寫此方法可依能量屬性挑出真正需要它的主力。"""
        return self.choose_bench_slot(slots, context)

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
            chosen_id = dm.choose_option(viable_ids, state, f'{card.name} mode')
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
                f'{card_name} search {dest}'
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
                        target_idx = dm.choose_attach_slot(
                            slots, p, f'{card_name} attach energy')
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
        evolves_from=entry.get('evolves_from', '') or EVOLVES_FROM.get(entry.get('name', ''), ''),
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
               bench_priority: list[str] | None = None,
               do_not_play: set[str] | None = None) -> GameState:
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

    _dnp = do_not_play or set()
    basics_in_hand = [i for i, c in enumerate(state.hand)
                      if c.category == 'Pokemon' and c.stage == '基礎']

    if not basics_in_hand:
        return state

    # prefer non-banned basics; fall back to all basics if every basic is banned
    allowed_basics = [i for i in basics_in_hand if state.hand[i].name not in _dnp]
    active_pool = allowed_basics or basics_in_hand

    if active_priority:
        best_idx = active_pool[0]
        best_rank = 9999
        for idx in active_pool:
            name = state.hand[idx].name
            rank = next((r for r, p in enumerate(active_priority) if p == name), 9999)
            if rank < best_rank:
                best_rank = rank
                best_idx = idx
        active_card = state.hand.pop(best_idx)
    else:
        active_card = state.hand.pop(active_pool[0])
    state.active = PokemonSlot(active_card)

    if bench_priority:
        remaining_basics = [(i, c) for i, c in enumerate(state.hand)
                            if c.category == 'Pokemon' and c.stage == '基礎'
                            and c.name not in _dnp]
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
