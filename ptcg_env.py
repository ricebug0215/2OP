import gymnasium as gym
from gymnasium import spaces
import numpy as np
from game_engine import GameState, parse_deck, Pokemon, Trainer, Energy

class PTCGEnv(gym.Env):
    def __init__(self, raw_deck_data):
        super(PTCGEnv, self).__init__()
        self.raw_deck_data = raw_deck_data
        self.action_space = spaces.Discrete(21)
        self.observation_space = spaces.Box(low=0, high=500, shape=(10,), dtype=np.float32)
        self.state = None

    def _get_obs(self):
        obs = np.zeros(10, dtype=np.float32)
        if self.state.active_pokemon:
            obs[0] = len(self.state.hand)
            obs[1] = self.state.active_pokemon.hp
            obs[2] = len(self.state.bench)
            obs[3] = len(self.state.deck)
            obs[4] = 1 if self.state.energy_attached_this_turn else 0
            obs[5] = len(self.state.active_pokemon.attached_energies)
            stage_map = {'Basic': 1, 'Stage1': 2, 'Stage2': 3}
            obs[6] = stage_map.get(self.state.active_pokemon.stage, 0)
            obs[7] = 1 if len(self.state.active_pokemon.attacks) > 0 else 0
        return obs

    def reset(self, seed=None):
        super().reset(seed=seed)
        while True:
            cards = parse_deck(self.raw_deck_data)
            self.state = GameState(cards)
            self.state.shuffle_deck()
            self.state.hand = self.state.deck[:7]
            self.state.deck = self.state.deck[7:]
            if self.state.setup_active_pokemon():
                break
        self.current_step = 0
        return self._get_obs(), {}

    def action_masks(self):
        """核心關鍵：告訴 AI 哪些動作是合法的"""
        masks = [False] * 21
        masks[0] = True # Action 0: 結束回合永遠是合法的

        # 檢查 Action 1~19: 手牌
        for i, card in enumerate(self.state.hand):
            if i >= 19: break # 超過動作空間上限的手牌先忽略
            action_idx = i + 1
            valid = True

            # --- 判斷這張牌現在能不能打 ---
            if isinstance(card, Trainer):
                # 1. 支援者全域限制
                if card.sub_category == 'Supporter' and self.state.supporter_played_this_turn:
                    valid = False

                # 2. 個別卡牌條件檢查 (必須與 game_engine.py 的失敗條件完全一致)
                elif "高級球" in card.name and len(self.state.hand) < 3:
                    valid = False
                elif "特殊紅牌" in card.name:
                    valid = False
                elif card.sub_category == 'Tool' and (not self.state.active_pokemon or self.state.active_pokemon.tool):
                    valid = False
                elif card.sub_category == 'Stadium' and self.state.stadium and self.state.stadium.name == card.name:
                    valid = False
                elif ("寶可平板" in card.name or "寶可裝置" in card.name) and len(self.state.deck) == 0:
                    valid = False

                # ⚠️ 修正重點：需要檢查牌庫與棄牌區狀態的卡片
                elif "好友寶芬" in card.name:
                    if len(self.state.bench) >= 5:
                        valid = False
                    else:
                        # 檢查牌庫裡是否還有合法的檢索對象
                        eligible_targets = [c for c in self.state.deck if isinstance(c, Pokemon) and c.stage == 'Basic' and c.hp <= 70]
                        if not eligible_targets:
                            valid = False

                elif "夜間擔架" in card.name:
                    # 檢查棄牌區有沒有東西可以撿
                    eligible = [c for c in self.state.discard_pile if isinstance(c, (Pokemon, Energy))]
                    if not eligible:
                        valid = False

                elif "赤松" in card.name and not self.state.supporter_played_this_turn:
                    # 檢查牌庫是否還有能量
                    energies = [c for c in self.state.deck if isinstance(c, Energy)]
                    if not energies:
                        valid = False

                elif "小剛" in card.name and not self.state.supporter_played_this_turn:
                    if len(self.state.deck) == 0:
                        valid = False

                elif "阿塞蘿拉" in card.name:
                    valid = False

            elif isinstance(card, Energy):
                if self.state.energy_attached_this_turn or not self.state.active_pokemon:
                    valid = False

            elif isinstance(card, Pokemon):
                if card.stage == 'Basic':
                    if len(self.state.bench) >= 5:
                        valid = False
                else:
                    # 第一回合不能進化，強制擋下
                    valid = False

            masks[action_idx] = valid

        return masks

    def step(self, action):
        reward = 0
        terminated = False
        self.current_step += 1

        if action == 0:
            terminated = True
        elif action == 20:
            success, _ = self.state.perform_attack()
            if success:
                reward += 300
                terminated = True
            else:
                reward -= 100
        elif 1 <= action <= len(self.state.hand):
            card_idx = action - 1
            card = self.state.hand.pop(card_idx)
            success = False

            # --- 訓練家卡 ---
            if isinstance(card, Trainer):
                if card.sub_category == 'Item':
                    if "特殊紅牌" in card.name:
                        # 規則限制：先二對手獎勵卡不可能為 3 張
                        success = False
                        reward -= 30 # 嚴厲懲罰打出無法發動的牌
                    elif "好友寶芬" in card.name: success, _ = self.state.play_item_buddy_poffin()
                    elif "高級球" in card.name: success, _ = self.state.play_item_ultra_ball()
                    elif "寶可平板" in card.name or "寶可裝置" in card.name: success, _ = self.state.play_item_pokegear()
                    elif "夜間擔架" in card.name: success, _ = self.state.play_item_night_stretcher()

                    if success: reward += 30

                elif card.sub_category == 'Tool':
                    success, _ = self.state.play_tool(card)
                    if success: reward += 50 # 斗篷很重要，加分

                elif card.sub_category == 'Stadium':
                    success, _ = self.state.play_stadium(card)
                    if success:
                        reward += 30
                    else:
                        reward -= 30 # 懲罰亂蓋同名競技場

                elif card.sub_category == 'Supporter':
                    if self.state.supporter_played_this_turn:
                        success = False
                        reward -= 30 # 嚴厲懲罰一回合打兩張支援者
                    else:
                        if "赤松" in card.name:
                            success, _ = self.state.play_supporter_crispin()
                            if success: reward += 120 # 赤松能解決能量問題，超大獎勵
                        elif "小剛" in card.name:
                            success, _ = self.state.play_supporter_brock()
                            if success: reward += 100
                        elif "莉莉艾" in card.name: success, _ = self.state.play_supporter_lillie()
                        elif "老大" in card.name: success, _ = self.state.play_supporter_boss()
                        elif "阿塞蘿拉" in card.name: success, _ = self.state.play_supporter_acerola()
                        else: success, _ = self.state.play_supporter_empty()

                        if success: reward += 80

            # --- 能量卡 ---
            elif isinstance(card, Energy):
                success, _ = self.state.attach_energy_from_hand(card)
                if success: reward += 50

            # --- 寶可夢卡 ---
            elif isinstance(card, Pokemon):
                if card.stage == 'Basic':
                    # 手動下基礎怪到備戰區
                    if len(self.state.bench) < 5:
                        self.state.bench.append(card)
                        success = True
                        if "可達鴨" in card.name:
                            reward -= 50 # 戰略懲罰：不知道對手是誰不准下可達鴨佔位置！
                        else:
                            reward += 10
                else:
                    success, _ = self.state.evolve_pokemon(card)
                    if success: reward += 80

            if success:
                if isinstance(card, Trainer) and card.sub_category != 'Tool' and card.sub_category != 'Stadium':
                    self.state.discard_pile.append(card)
            else:
                self.state.hand.insert(card_idx, card)
                reward -= 20
        else:
            reward -= 50

        if self.current_step >= 30:
            terminated = True

        if terminated:
            if self.state.active_pokemon:
                if self.state.active_pokemon.name == "多龍巴魯托ex": reward += 200
                elif self.state.active_pokemon.name == "多龍奇": reward += 100
                if len(self.state.active_pokemon.attached_energies) > 0: reward += 100

            # 結算時若發現場上有可達鴨，再次扣除總分
            if any("可達鴨" in p.name for p in self.state.bench + ([self.state.active_pokemon] if self.state.active_pokemon else [])):
                reward -= 50

            reward += len(self.state.bench) * 15

        return self._get_obs(), reward, terminated, False, {}
