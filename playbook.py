"""
PTCG Playbook 系統 — 規則式決策 + 模擬執行
"""

from game_engine import (
    Card, PokemonSlot, GameState, EffectEngine,
    DecisionMaker, matches_filter, build_deck, setup_game, load_master_db,
    pick_energy_for_slot, needed_energy_types, energy_type_of,
)


# ═══════════════════════════════════════
#  Playbook 決策者
# ═══════════════════════════════════════

class PlaybookDecisionMaker(DecisionMaker):
    """用優先順序規則做決策的 AI。

    playbook 格式:
    {
        "play_priority": [
            {"card": "好友寶芬", "conditions": {"bench_open_gte": 2}},
            {"card": "高級球"},
            {"card": "探險家的嚮導"},
            {"card": "attach_energy"},
        ],
        "search_priority": ["小火龍", "拉魯拉絲", "夢妖"],
        "discard_priority": ["Energy", "夜間擔架", "調換票"],
        "bench_priority": ["小火龍", "拉魯拉絲"],
        "energy_target": ["小火龍"],
        "evolution_lines": {
            "小火龍": ["火恐龍", "噴火龍ex"],
            "拉魯拉絲": ["奇魯莉安", "沙奈朵ex"]
        },
    }
    """

    def __init__(self, playbook: dict, effect_engine: EffectEngine):
        self.pb = playbook
        self.engine = effect_engine

    # ── 主決策：下一步打什麼 ──

    def choose_action(self, state: GameState, skip: set[str] | None = None,
                      evolved_ids: set[int] | None = None,
                      used_ability_ids: set[int] | None = None) -> dict | None:
        skip = skip or set()
        evolved_ids = evolved_ids or set()
        used_ability_ids = used_ability_ids or set()
        do_not_play = set(self.pb.get('do_not_play', []))
        for rule in self.pb.get('play_priority', []):
            card_name = rule['card']
            if card_name in do_not_play:
                continue

            if card_name == 'attach_energy':
                action = self._try_attach_energy(state)
                if action:
                    return action
                continue

            if card_name == 'bench_basics':
                action = self._try_bench_basic(state)
                if action:
                    return action
                continue

            if card_name == 'evolve':
                action = self._try_evolve(state, evolved_ids)
                if action:
                    return action
                continue

            if card_name == 'use_ability':
                action = self._try_use_ability(state, used_ability_ids)
                if action:
                    return action
                continue

            if card_name in skip:
                continue

            hand_matches = [
                (i, c) for i, c in enumerate(state.hand)
                if c.name == card_name
            ]
            if not hand_matches:
                continue

            if not self._check_conditions(rule.get('conditions', {}), state):
                continue

            idx, card = hand_matches[0]
            if self.engine.can_play(card, state):
                return {'type': 'play_card', 'hand_idx': idx}

        action = self._try_attach_energy(state)
        if action:
            return action

        return None

    def _try_bench_basic(self, state: GameState) -> dict | None:
        if state.bench_open <= 0:
            return None
        bench_priority = self.pb.get('bench_priority', [])
        no_bench = set(self.pb.get('no_bench', []))
        do_not_play = set(self.pb.get('do_not_play', []))
        basics = [
            (i, c) for i, c in enumerate(state.hand)
            if c.category == 'Pokemon' and c.stage == '基礎'
            and c.name not in no_bench and c.name not in do_not_play
        ]
        if not basics:
            return None
        names = [c.name for c in [b[1] for b in basics]]
        best = self._pick_by_priority(names, bench_priority)
        idx, card = basics[best]
        return {'type': 'bench_basic', 'hand_idx': idx, 'card_name': card.name}

    def _try_evolve(self, state: GameState, evolved_ids: set[int]) -> dict | None:
        if state.turn < 2:
            return None
        evo_lines = self.pb.get('evolution_lines', {})
        do_not_play = set(self.pb.get('do_not_play', []))
        for slot in state.all_in_play:
            if id(slot) in evolved_ids:
                continue
            if slot.turns_in_play < 1:
                continue
            line = evo_lines.get(slot.base.name, [])
            for evo_name in line:
                if evo_name in do_not_play:
                    continue
                for hand_i, hc in enumerate(state.hand):
                    if hc.name == evo_name and hc.category == 'Pokemon':
                        if slot.can_evolve_to(hc):
                            return {
                                'type': 'evolve',
                                'hand_idx': hand_i,
                                'slot_id': id(slot),
                                'from_name': slot.name,
                                'to_name': evo_name,
                            }
        return None

    def _try_use_ability(self, state: GameState, used_ability_ids: set[int]) -> dict | None:
        for slot in state.all_in_play:
            if id(slot) in used_ability_ids:
                continue
            ability = self.engine.get_ability(slot.name)
            if ability:
                return {
                    'type': 'use_ability',
                    'slot_id': id(slot),
                    'pokemon_name': slot.name,
                    'ability_name': ability['name'],
                }
        return None

    def _try_attach_energy(self, state: GameState) -> dict | None:
        if state.energy_attached:
            return None
        energy_priority = self.pb.get('energy_target', [])
        energy_indices = [
            i for i, c in enumerate(state.hand)
            if c.category == 'Energy'
        ]
        if not energy_indices:
            return None
        targets = state.all_in_play
        if not targets:
            return None
        target_idx = self._pick_by_priority(
            [s.base.name for s in targets], energy_priority
        )
        # 依目標主力的能量需求挑選對的能量屬性
        override = self.pb.get('energy_profile')
        energy_idx = pick_energy_for_slot(state.hand, targets[target_idx], override)
        if energy_idx is None:
            energy_idx = energy_indices[0]
        return {
            'type': 'attach_energy',
            'hand_idx': energy_idx,
            'target_idx': target_idx,
        }

    def _check_conditions(self, conds: dict, state: GameState) -> bool:
        if 'bench_open_gte' in conds and state.bench_open < conds['bench_open_gte']:
            return False
        if 'hand_size_gte' in conds and len(state.hand) < conds['hand_size_gte']:
            return False
        if 'hand_size_lte' in conds and len(state.hand) > conds['hand_size_lte']:
            return False
        if 'turn_gte' in conds and state.turn < conds['turn_gte']:
            return False
        if 'has_bench' in conds and len(state.bench) < 1:
            return False
        return True

    # ── 子決策：效果執行中的選擇 ──

    def choose_targets(self, candidates: list, count: int, context: str) -> list[int]:
        if not candidates:
            return []
        count = min(count, len(candidates))

        do_not_play = set(self.pb.get('do_not_play', []))

        if 'search' in context or 'look_top' in context or 'recover' in context:
            priority = self.pb.get('search_priority', [])
            if do_not_play:
                allowed = [i for i, c in enumerate(candidates)
                           if (c.name if isinstance(c, Card) else c) not in do_not_play]
                if allowed:
                    filtered = [candidates[i] for i in allowed]
                    picks = self._pick_multiple_by_priority(filtered, count, priority)
                    return [allowed[p] for p in picks]
            return self._pick_multiple_by_priority(candidates, count, priority)

        if 'evolve' in context:
            evo_lines = self.pb.get('evolution_lines', {})
            for i, cand in enumerate(candidates):
                if isinstance(cand, tuple):
                    evo_name, slot_name = cand
                    line = evo_lines.get(slot_name, [])
                    if evo_name in line:
                        return [i]
            return []

        return list(range(count))

    def choose_option(self, options: list[str], context: str) -> str:
        return options[0]

    def choose_bench_slot(self, bench: list[PokemonSlot], context: str) -> int:
        bench_priority = self.pb.get('bench_priority', [])
        names = [s.base.name for s in bench]
        return self._pick_by_priority(names, bench_priority)

    def choose_discard(self, hand: list[Card], count: int, context: str) -> list[int]:
        discard_priority = self.pb.get('discard_priority', [])
        scored = []
        for i, card in enumerate(hand):
            score = 1000
            for rank, dp in enumerate(discard_priority):
                if dp == card.category or dp == card.name:
                    score = rank
                    break
            scored.append((score, i))
        scored.sort()
        return [i for _, i in scored[:count]]

    # ── 工具方法 ──

    def _pick_by_priority(self, names: list[str], priority: list[str]) -> int:
        for p in priority:
            for i, n in enumerate(names):
                if n == p:
                    return i
        return 0

    def _pick_multiple_by_priority(self, candidates: list, count: int, priority: list[str]) -> list[int]:
        def get_name(cand):
            if isinstance(cand, Card):
                return cand.name
            if isinstance(cand, tuple):
                return cand[0]
            return str(cand)

        scored = []
        for i, cand in enumerate(candidates):
            name = get_name(cand)
            score = 9999
            for rank, p in enumerate(priority):
                if name == p:
                    score = rank
                    break
            scored.append((score, i))
        scored.sort()
        return [i for _, i in scored[:count]]


# ═══════════════════════════════════════
#  模擬執行器
# ═══════════════════════════════════════

class SimulationRunner:
    def __init__(self, deck_list: list[dict], playbook: dict,
                 effects_path: str = 'card_effects.json'):
        self.deck_list = deck_list
        self.playbook = playbook
        self.master_db = load_master_db()
        self.effect_engine = EffectEngine(effects_path)

    def run_once(self, turns: int = 2, going_first: bool = True) -> dict:
        deck = build_deck(self.deck_list, self.master_db)
        state = setup_game(
            deck, going_first=going_first,
            active_priority=self.playbook.get('active_priority'),
            bench_priority=self.playbook.get('setup_bench_priority'),
            do_not_play=set(self.playbook.get('do_not_play', [])),
        )
        dm = PlaybookDecisionMaker(self.playbook, self.effect_engine)

        log = []
        setup_info = {
            'hand': [c.name for c in state.hand],
            'active': state.active.name if state.active else None,
            'bench': [s.name for s in state.bench],
            'prizes_set_aside': len(state.prizes),
            'deck_remaining': len(state.deck),
        }
        log.append({'phase': 'setup', 'detail': setup_info})

        for t in range(1, turns + 1):
            state.start_turn()
            turn_entry = {
                'phase': f'T{t}',
                'hand_at_start': [c.name for c in state.hand],
                'steps': [],
            }
            turn_entry['drew'] = state.hand[-1].name if state.hand else None

            safety = 0
            step_num = 0
            skip_cards: set[str] = set()
            evolved_ids: set[int] = set()
            used_ability_ids: set[int] = set()

            while safety < 30:
                safety += 1
                action = dm.choose_action(state, skip=skip_cards,
                                          evolved_ids=evolved_ids,
                                          used_ability_ids=used_ability_ids)
                if action is None:
                    break

                def _make_step(action_text, details=None):
                    nonlocal step_num
                    step_num += 1
                    return {
                        'step': step_num,
                        'action': action_text,
                        'details': details or [],
                        'hand_after': [c.name for c in state.hand],
                        'field_after': {
                            'active': repr(state.active) if state.active else None,
                            'bench': [repr(s) for s in state.bench],
                        },
                        'deck_size': len(state.deck),
                        'discard_size': len(state.discard),
                    }

                if action['type'] == 'bench_basic':
                    idx = action['hand_idx']
                    cname = action['card_name']
                    if idx < len(state.hand):
                        card = state.hand.pop(idx)
                        state.put_on_bench_card(card)
                        turn_entry['steps'].append(
                            _make_step(f'放置【{cname}】到備戰區'))
                    continue

                elif action['type'] == 'use_ability':
                    slot_id = action['slot_id']
                    pname = action['pokemon_name']
                    aname = action['ability_name']
                    result = self.effect_engine.execute_ability(pname, state, dm)
                    if result['success']:
                        used_ability_ids.add(slot_id)
                        turn_entry['steps'].append(
                            _make_step(f'特性【{aname}】（{pname}）', result['steps']))
                    continue

                elif action['type'] == 'evolve':
                    hand_idx = action['hand_idx']
                    slot_id = action['slot_id']
                    from_name = action['from_name']
                    to_name = action['to_name']
                    if hand_idx < len(state.hand):
                        evo_card = state.hand.pop(hand_idx)
                        for slot in state.all_in_play:
                            if id(slot) == slot_id:
                                slot.evolve(evo_card)
                                evolved_ids.add(slot_id)
                                break
                        turn_entry['steps'].append(
                            _make_step(f'進化: {from_name} → {to_name}'))
                    continue

                elif action['type'] == 'play_card':
                    idx = action['hand_idx']
                    if idx >= len(state.hand):
                        break
                    card = state.hand[idx]
                    card_name = card.name
                    result = self.effect_engine.execute(card, idx, state, dm)
                    if result['success']:
                        skip_cards.clear()
                        turn_entry['steps'].append(
                            _make_step(f'使用【{card_name}】', result['steps']))
                    else:
                        skip_cards.add(card_name)

                elif action['type'] == 'attach_energy':
                    idx = action['hand_idx']
                    target_idx = action['target_idx']
                    if idx >= len(state.hand):
                        break
                    energy_card = state.hand.pop(idx)
                    targets = state.all_in_play
                    if 0 <= target_idx < len(targets):
                        targets[target_idx].attached_energy.append(energy_card)
                        state.energy_attached = True
                        turn_entry['steps'].append(
                            _make_step(f'貼能量【{energy_card.name}】→ {targets[target_idx].name}'))

            log.append(turn_entry)

        return {
            'board': state.summary(),
            'score': evaluate_board(state, self.playbook),
            'log': log,
        }

    def run_many(self, n: int = 1000, turns: int = 2, going_first: bool = True) -> dict:
        results = []
        scores = []
        for _ in range(n):
            result = self.run_once(turns=turns, going_first=going_first)
            results.append(result)
            scores.append(result['score'])

        scores.sort()
        total = len(scores)
        return {
            'runs': total,
            'avg_score': sum(scores) / total,
            'median_score': scores[total // 2],
            'min_score': scores[0],
            'max_score': scores[-1],
            'p25_score': scores[total // 4],
            'p75_score': scores[3 * total // 4],
            'sample_boards': [r['board'] for r in results[:5]],
            'sample_logs': [r['log'] for r in results[:3]],
        }


# ═══════════════════════════════════════
#  場面評估
# ═══════════════════════════════════════

def evaluate_board(state: GameState, playbook: dict | None = None) -> float:
    pb = playbook or {}
    core_pokemon = set(pb.get('bench_priority', []))
    energy_targets = set(pb.get('energy_target', []))
    evo_lines = pb.get('evolution_lines', {})
    score = 0.0

    # ── 場面基礎 ──
    score += len(state.bench) * 10
    all_evo_names = set()
    for evos in evo_lines.values():
        all_evo_names.update(evos)
    for slot in state.all_in_play:
        if slot.name in core_pokemon or slot.base.name in core_pokemon:
            score += 20
        elif slot.name in all_evo_names:
            score += 20

    # ── 進化 ──
    for slot in state.all_in_play:
        if slot.stage == '1階進化':
            score += 15
        elif slot.stage == '2階進化':
            score += 40

    # ── 能量 ──
    energy_override = pb.get('energy_profile')
    for slot in state.all_in_play:
        for _ in slot.attached_energy:
            score += 8
        is_target = slot.base.name in energy_targets or slot.name in energy_targets
        if is_target:
            score += len(slot.attached_energy) * 5
        # 屬性正確獎勵: 主力需求屬性的能量貼對才加分
        needed = needed_energy_types(slot, energy_override)
        if needed:
            for e in slot.attached_energy:
                if energy_type_of(e) in needed:
                    score += 6  # 屬性匹配
                else:
                    score -= 2  # 貼錯屬性到有明確需求的主力，小幅扣分

    # ── 資源轉化 ──
    field_score = score
    hand_size = len(state.hand)
    if hand_size > 8:
        score -= (hand_size - 8) * 3
    if hand_size < 3 and field_score > 50:
        score += 5

    deck_size = len(state.deck)
    if deck_size < 10:
        score -= (10 - deck_size) * 2

    return score


# ═══════════════════════════════════════
#  快速測試
# ═══════════════════════════════════════

if __name__ == '__main__':
    demo_deck = [
        # Pokemon (20)
        {"name": "多龍巴魯托ex", "count": 3},
        {"name": "多龍奇", "count": 4},
        {"name": "多龍梅西亞", "count": 4},
        {"name": "土龍弟弟", "count": 2},
        {"name": "土龍節節", "count": 2},
        {"name": "土龍節節ex", "count": 1},
        {"name": "願增猿", "count": 2},
        {"name": "含羞苞", "count": 1},
        {"name": "可達鴨", "count": 1},
        # Trainer (32)
        {"name": "寶可平板", "count": 4},
        {"name": "好友寶芬", "count": 4},
        {"name": "高級球", "count": 3},
        {"name": "夜間擔架", "count": 2},
        {"name": "寶可裝置3.0", "count": 2},
        {"name": "特殊紅牌", "count": 2, "category": "Trainer", "sub_type": "物品卡"},
        {"name": "英雄斗篷", "count": 1, "category": "Trainer", "sub_type": "寶可夢道具"},
        {"name": "莉莉艾的決意", "count": 4},
        {"name": "赤松", "count": 2},
        {"name": "小剛的發掘", "count": 2},
        {"name": "阿塞蘿拉的惡作劇", "count": 1, "category": "Trainer", "sub_type": "支援者卡"},
        {"name": "老大的指令", "count": 3, "category": "Trainer", "sub_type": "支援者卡"},
        {"name": "險惡廢墟", "count": 2, "category": "Trainer", "sub_type": "競技場卡"},
        # Energy (8)
        {"name": "基本【超】能量", "count": 3},
        {"name": "基本【火】能量", "count": 3},
        {"name": "基本【惡】能量", "count": 2},
    ]

    demo_playbook = {
        "active_priority": ["含羞苞", "願增猿", "土龍弟弟", "多龍梅西亞"],
        "setup_bench_priority": ["多龍梅西亞", "土龍弟弟", "願增猿"],
        "no_bench": ["土龍弟弟", "可達鴨"],
        "play_priority": [
            {"card": "bench_basics"},
            {"card": "好友寶芬", "conditions": {"bench_open_gte": 2}},
            {"card": "寶可平板"},
            {"card": "高級球"},
            {"card": "寶可裝置3.0"},
            {"card": "夜間擔架"},
            {"card": "evolve"},
            {"card": "use_ability"},
            {"card": "attach_energy"},
            {"card": "莉莉艾的決意"},
            {"card": "赤松"},
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
            "土龍弟弟": ["土龍節節ex", "土龍節節"]
        },
    }

    runner = SimulationRunner(demo_deck, demo_playbook)

    print('=' * 50)
    print(' 單次模擬詳細記錄')
    print('=' * 50)
    result = runner.run_once()

    for entry in result['log']:
        if entry.get('phase') == 'setup':
            d = entry['detail']
            print(f"\n【起始設置】")
            print(f"  手牌: {', '.join(d['hand'])}")
            print(f"  戰鬥區: {d['active']}")
            bench_names = d.get('bench', [])
            print(f"  備戰區: {', '.join(bench_names) or '（空）'}")
            print(f"  獎賞卡: {d['prizes_set_aside']} 張")
            print(f"  牌庫: {d['deck_remaining']} 張")
        else:
            phase = entry['phase']
            print(f"\n{'─' * 40}")
            print(f"【{phase}】手牌: {', '.join(entry['hand_at_start'])}")
            if 'drew' in entry and entry['drew']:
                print(f"  ↳ 抽牌: {entry['drew']}")
            if not entry['steps']:
                print(f"  （無操作）")
            for s in entry['steps']:
                print(f"\n  步驟 {s['step']}: {s['action']}")
                for detail in s['details']:
                    print(f"    → {detail}")
                f = s['field_after']
                print(f"    場面: 戰鬥={f['active']}  備戰={f['bench'] or '（空）'}")
                print(f"    手牌: {', '.join(s['hand_after']) or '（空）'}")
                print(f"    牌庫: {s['deck_size']} 張  棄牌: {s['discard_size']} 張")

    print(f"\n{'─' * 40}")
    b = result['board']
    print(f"【T2 結算】")
    print(f"  戰鬥區: {b['active']}")
    print(f"  備戰區: {b['bench'] or '（空）'}")
    print(f"  手牌({b['hand_size']}): {', '.join(b['hand'])}")
    print(f"  牌庫: {b['deck_size']} 張  棄牌: {b['discard_size']} 張")
    print(f"  場面評分: {result['score']:.0f}")

    print(f"\n{'=' * 50}")
    print(f" 1000 次統計")
    print(f"{'=' * 50}")
    stats = runner.run_many(1000)
    print(f"  平均分: {stats['avg_score']:.1f}")
    print(f"  中位數: {stats['median_score']:.1f}")
    print(f"  範圍:   {stats['min_score']:.0f} ~ {stats['max_score']:.0f}")
    print(f"  25%~75%: {stats['p25_score']:.0f} ~ {stats['p75_score']:.0f}")
