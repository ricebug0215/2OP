"""
PTCG T1/T2 Setup — Gymnasium 環境

RL agent 控制「打哪張牌 / 能量貼誰 / pass」的高層決策，
sub-decisions（搜牌目標、棄牌選擇等）仍由 playbook heuristics 處理。
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np

from game_engine import (
    GameState, Card, PokemonSlot, build_deck, setup_game, load_master_db,
    pick_energy_for_slot,
)
from playbook import EffectEngine, PlaybookDecisionMaker, evaluate_board


class PTCGSetupEnv(gym.Env):
    """
    Action space (Discrete):
        0           = pass（結束本回合行動）
        1..U        = 打出第 i 種卡（U = unique card count）
        U+1..U+6    = 貼能量到場上第 0~5 號位（active=0, bench=1..5）

    Observation space (Box):
        [0..U-1]       手牌中每種卡的張數
        [U..U+17]      場上 6 格 × 3 features (card_id, stage, energy_count)
        [U+18..U+22]   turn, energy_attached, supporter_used, deck_size, hand_size

    Reward: 0 on every step; evaluate_board() on terminal step.
    """

    metadata = {'render_modes': ['human']}

    def __init__(self, deck_list: list[dict], playbook: dict,
                 effects_path: str = 'card_effects.json',
                 turns: int = 2, going_first: bool = True):
        super().__init__()
        self.deck_list = deck_list
        self.playbook = playbook
        self.effects_path = effects_path
        self.turns = turns
        self.going_first = going_first

        self.master_db = load_master_db()
        self.effect_engine = EffectEngine(effects_path)

        self.unique_cards: list[str] = []
        seen: set[str] = set()
        for item in deck_list:
            if item['name'] not in seen:
                self.unique_cards.append(item['name'])
                seen.add(item['name'])
        self.card_to_idx = {name: i for i, name in enumerate(self.unique_cards)}
        self.n_unique = len(self.unique_cards)

        self.n_actions = 1 + self.n_unique + 6
        self.action_space = spaces.Discrete(self.n_actions)

        obs_size = self.n_unique + 6 * 3 + 5
        self.observation_space = spaces.Box(
            low=-1, high=300, shape=(obs_size,), dtype=np.float32,
        )

        self.state: GameState | None = None
        self.dm: PlaybookDecisionMaker | None = None
        self.current_turn = 0
        self._skip_cards: set[str] = set()
        self._evolved_ids: set[int] = set()
        self._used_ability_ids: set[int] = set()
        self._step_count = 0

    # ────────────────────── Gym interface ──────────────────────

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

        deck = build_deck(self.deck_list, self.master_db)
        self.state = setup_game(
            deck, going_first=self.going_first,
            active_priority=self.playbook.get('active_priority'),
            bench_priority=self.playbook.get('setup_bench_priority'),
            do_not_play=set(self.playbook.get('do_not_play', [])),
        )
        self.dm = PlaybookDecisionMaker(self.playbook, self.effect_engine)

        self.current_turn = 1
        self.state.start_turn()

        self._skip_cards = set()
        self._evolved_ids = set()
        self._used_ability_ids = set()
        self._step_count = 0

        return self._get_obs(), {'action_mask': self.get_action_mask()}

    def step(self, action: int):
        assert self.state is not None
        reward = 0.0
        done = False
        self._step_count += 1

        if action == 0:
            # pass → 進入下一回合或結束
            if self.current_turn >= self.turns:
                done = True
                reward = evaluate_board(self.state, self.playbook)
            else:
                self.current_turn += 1
                self.state.start_turn()
                self._skip_cards = set()
                self._evolved_ids = set()
                self._used_ability_ids = set()

        elif 1 <= action <= self.n_unique:
            card_name = self.unique_cards[action - 1]
            self._execute_card(card_name)

        elif self.n_unique < action < self.n_actions:
            slot_idx = action - self.n_unique - 1
            self._execute_attach_energy(slot_idx)

        if self._step_count >= 60:
            done = True
            if reward == 0:
                reward = evaluate_board(self.state, self.playbook)

        obs = self._get_obs()
        info = {'action_mask': self.get_action_mask()}
        return obs, reward, done, False, info

    # ────────────────────── Observation ──────────────────────

    def _get_obs(self) -> np.ndarray:
        hand_counts = np.zeros(self.n_unique, dtype=np.float32)
        for card in self.state.hand:
            idx = self.card_to_idx.get(card.name)
            if idx is not None:
                hand_counts[idx] += 1

        field = np.full(18, -1, dtype=np.float32)
        stage_map = {'基礎': 0, '1階進化': 1, '2階進化': 2}
        slots = self.state.all_in_play
        for i, slot in enumerate(slots[:6]):
            base = i * 3
            field[base] = self.card_to_idx.get(slot.name, -1)
            field[base + 1] = stage_map.get(slot.stage, 0)
            field[base + 2] = len(slot.attached_energy)

        game = np.array([
            self.current_turn,
            float(self.state.energy_attached),
            float(self.state.supporter_used),
            len(self.state.deck),
            len(self.state.hand),
        ], dtype=np.float32)

        return np.concatenate([hand_counts, field, game])

    # ────────────────────── Action mask ──────────────────────

    def get_action_mask(self) -> np.ndarray:
        mask = np.zeros(self.n_actions, dtype=np.int8)
        mask[0] = 1  # pass always valid

        do_not_play = set(self.playbook.get('do_not_play', []))
        hand_names_playable: set[str] = set()
        for card in self.state.hand:
            name = card.name
            if name in self._skip_cards or name in do_not_play:
                continue
            if name in hand_names_playable:
                continue

            idx = self.card_to_idx.get(name)
            if idx is None:
                continue

            if card.category == 'Pokemon' and card.stage == '基礎':
                if self.state.bench_open > 0:
                    mask[1 + idx] = 1
                    hand_names_playable.add(name)
                continue

            if card.category == 'Pokemon' and card.stage in ('1階進化', '2階進化'):
                if self.state.turn >= 2:
                    for slot in self.state.all_in_play:
                        if id(slot) in self._evolved_ids:
                            continue
                        if slot.turns_in_play < 1:
                            continue
                        if slot.can_evolve_to(card):
                            mask[1 + idx] = 1
                            hand_names_playable.add(name)
                            break
                continue

            if card.category == 'Energy':
                continue

            if card.category == 'Trainer':
                if card.sub_type == '支援者卡' and not self.state.can_play_supporter():
                    continue
                if self.effect_engine.can_play(card, self.state):
                    mask[1 + idx] = 1
                    hand_names_playable.add(name)

        # 貼能量
        if not self.state.energy_attached:
            has_energy = any(c.category == 'Energy' for c in self.state.hand)
            if has_energy:
                slots = self.state.all_in_play
                for i in range(len(slots)):
                    mask[1 + self.n_unique + i] = 1

        # abilities — 合併到 mask 中對應的寶可夢名（如果能用特性就自動觸發）
        # 特性由 _auto_use_abilities() 在每個 step 開頭自動執行

        return mask

    def action_masks(self) -> np.ndarray:
        """SB3 MaskablePPO interface."""
        return self.get_action_mask().astype(bool)

    # ────────────────────── Execution ──────────────────────

    def _auto_use_abilities(self):
        """自動觸發所有可用特性（不需要 RL 決策）"""
        for slot in self.state.all_in_play:
            if id(slot) in self._used_ability_ids:
                continue
            ability = self.effect_engine.get_ability(slot.name)
            if ability:
                result = self.effect_engine.execute_ability(slot.name, self.state, self.dm)
                if result['success']:
                    self._used_ability_ids.add(id(slot))

    def _execute_card(self, card_name: str):
        hand_match = None
        for i, c in enumerate(self.state.hand):
            if c.name == card_name:
                hand_match = (i, c)
                break
        if hand_match is None:
            return

        idx, card = hand_match

        if card.category == 'Pokemon' and card.stage == '基礎':
            card = self.state.hand.pop(idx)
            self.state.put_on_bench_card(card)
            self._auto_use_abilities()
            return

        if card.category == 'Pokemon' and card.stage in ('1階進化', '2階進化'):
            evo_lines = self.playbook.get('evolution_lines', {})
            for slot in self.state.all_in_play:
                if id(slot) in self._evolved_ids:
                    continue
                if slot.turns_in_play < 1:
                    continue
                if slot.can_evolve_to(card):
                    evo_card = self.state.hand.pop(idx)
                    slot.evolve(evo_card)
                    self._evolved_ids.add(id(slot))
                    self._auto_use_abilities()
                    return
            return

        if card.category == 'Trainer':
            result = self.effect_engine.execute(card, idx, self.state, self.dm)
            if result['success']:
                self._skip_cards.clear()
                self._auto_use_abilities()
            else:
                self._skip_cards.add(card_name)

    def _execute_attach_energy(self, slot_idx: int):
        if self.state.energy_attached:
            return
        slots = self.state.all_in_play
        if slot_idx >= len(slots):
            return
        # RL 選目標寶可夢，能量屬性由引擎依主力需求智慧挑選
        override = self.playbook.get('energy_profile')
        energy_idx = pick_energy_for_slot(self.state.hand, slots[slot_idx], override)
        if energy_idx is None:
            return
        energy_card = self.state.hand.pop(energy_idx)
        slots[slot_idx].attached_energy.append(energy_card)
        self.state.energy_attached = True


# ────────────────────── Quick validation ──────────────────────

if __name__ == '__main__':
    DECK = [
        {'name': '多龍巴魯托ex', 'count': 3}, {'name': '多龍奇', 'count': 4},
        {'name': '多龍梅西亞', 'count': 4}, {'name': '土龍弟弟', 'count': 2},
        {'name': '土龍節節', 'count': 2}, {'name': '土龍節節ex', 'count': 1},
        {'name': '願增猿', 'count': 2}, {'name': '含羞苞', 'count': 1},
        {'name': '可達鴨', 'count': 1}, {'name': '寶可平板', 'count': 4},
        {'name': '好友寶芬', 'count': 4}, {'name': '高級球', 'count': 3},
        {'name': '夜間擔架', 'count': 2}, {'name': '寶可裝置3.0', 'count': 2},
        {'name': '特殊紅牌', 'count': 2}, {'name': '英雄斗篷', 'count': 1},
        {'name': '莉莉艾的決意', 'count': 4}, {'name': '赤松', 'count': 2},
        {'name': '小剛的發掘', 'count': 2}, {'name': '阿塞蘿拉的惡作劇', 'count': 1},
        {'name': '老大的指令', 'count': 3}, {'name': '險惡廢墟', 'count': 2},
        {'name': '基本【超】能量', 'count': 3}, {'name': '基本【火】能量', 'count': 3},
        {'name': '基本【惡】能量', 'count': 2},
    ]

    PB = {
        'active_priority': ['含羞苞', '可達鴨', '願增猿', '土龍弟弟', '多龍梅西亞'],
        'setup_bench_priority': ['多龍梅西亞', '土龍弟弟', '願增猿'],
        'no_bench': ['可達鴨'],
        'play_priority': [],
        'search_priority': ['多龍梅西亞', '土龍弟弟', '多龍奇', '多龍巴魯托ex', '願增猿', '含羞苞', '土龍節節ex'],
        'discard_priority': ['Energy', '特殊紅牌', '老大的指令', '險惡廢墟'],
        'bench_priority': ['多龍梅西亞', '土龍弟弟', '願增猿'],
        'energy_target': ['多龍梅西亞', '多龍奇', '土龍弟弟'],
        'evolution_lines': {
            '多龍梅西亞': ['多龍奇', '多龍巴魯托ex'],
            '土龍弟弟': ['土龍節節ex', '土龍節節'],
        },
    }

    env = PTCGSetupEnv(DECK, PB)
    print(f'Action space: {env.action_space}  ({env.n_actions} actions)')
    print(f'Observation space: {env.observation_space.shape}')
    print(f'Unique cards: {env.n_unique}')
    print()

    # run a random-valid-action episode
    obs, info = env.reset()
    total_reward = 0
    steps = 0
    while True:
        mask = info['action_mask']
        valid = np.where(mask)[0]
        action = env.np_random.choice(valid)
        card_label = '(pass)' if action == 0 else (
            env.unique_cards[action - 1] if action <= env.n_unique
            else f'energy→slot{action - env.n_unique - 1}'
        )
        obs, reward, done, trunc, info = env.step(action)
        steps += 1
        if done:
            total_reward = reward
            break

    print(f'Episode done in {steps} steps, reward={total_reward}')
    print(f'Final hand: {[c.name for c in env.state.hand]}')
    print(f'Active: {env.state.active}')
    print(f'Bench: {[repr(s) for s in env.state.bench]}')

    # compare: run 100 random episodes vs 100 playbook episodes
    from playbook import SimulationRunner

    random_scores = []
    for _ in range(100):
        obs, info = env.reset()
        while True:
            mask = info['action_mask']
            valid = np.where(mask)[0]
            action = env.np_random.choice(valid)
            obs, reward, done, trunc, info = env.step(action)
            if done:
                random_scores.append(reward)
                break

    FULL_PB = dict(PB, play_priority=[
        {'card': 'bench_basics'},
        {'card': '好友寶芬', 'conditions': {'bench_open_gte': 2}},
        {'card': '寶可平板'}, {'card': '高級球'}, {'card': '寶可裝置3.0'},
        {'card': '夜間擔架'},
        {'card': 'evolve'}, {'card': 'use_ability'},
        {'card': 'attach_energy'},
        {'card': '莉莉艾的決意'}, {'card': '赤松'},
        {'card': '小剛的發掘', 'conditions': {'hand_size_lte': 3}},
    ])
    runner = SimulationRunner(DECK, FULL_PB)
    playbook_scores = [runner.run_once(turns=2, going_first=True)['score'] for _ in range(100)]

    print(f'\n--- Comparison (100 episodes) ---')
    print(f'Random agent:   avg={np.mean(random_scores):.1f}  median={np.median(random_scores):.1f}  '
          f'min={np.min(random_scores):.0f}  max={np.max(random_scores):.0f}')
    print(f'Playbook agent: avg={np.mean(playbook_scores):.1f}  median={np.median(playbook_scores):.1f}  '
          f'min={np.min(playbook_scores):.0f}  max={np.max(playbook_scores):.0f}')
