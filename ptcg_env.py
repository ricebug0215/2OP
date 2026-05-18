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
        self.current_turn = 1 # 初始化回合數

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
            
            # 1. 抽 7 張起手牌
            self.state.hand = self.state.deck[:7]
            self.state.deck = self.state.deck[7:]
            
            # 2. 確認手牌有基礎寶可夢並設定好戰鬥區/備戰區
            if self.state.setup_active_pokemon():
                break
                
        # 🌟 3. 新增：從牌庫頂抽出 6 張作為獎勵卡 (必須在確認起手沒問題後才放)
        self.state.prizes = self.state.deck[:6]
        self.state.deck = self.state.deck[6:]
        
        self.current_step = 0
        self.current_turn = 1 
        
        # 4. 遊戲正式開始：先攻第一回合，抽一張牌！
        self.state.draw_card(1)
        
        return self._get_obs(), {}

    def action_masks(self):
        """核心關鍵：告訴 AI 哪些動作是合法的"""
        masks = [False] * 21
        masks[0] = True # Action 0: 結束回合永遠是合法的

        # 🌟 新增：Action 20 攻擊的遮罩判斷
        if self.current_turn == 1:
            masks[20] = False # PTCG 規則：先攻第一回合不可攻擊
        else:
            if self.state.active_pokemon:
                masks[20] = True # 有戰鬥寶可夢時才可宣告攻擊（可依據能量進一步限制）

        # 檢查 Action 1~19: 手牌
        for i, card in enumerate(self.state.hand):
            if i >= 19: break # 超過動作空間上限的手牌先忽略
            action_idx = i + 1
            valid = True

            # --- 判斷這張牌現在能不能打 ---
            if isinstance(card, Trainer):
                # 🌟 1. 支援者全域限制 (加入第一回合限制)
                if card.sub_category == 'Supporter':
                    if self.current_turn == 1:
                        valid = False # 先攻第一回合不能開支援者
                    elif self.state.supporter_played_this_turn:
                        valid = False # 一回合限用一張支援者

                # 2. 個別卡牌條件檢查 (必須與 game_engine.py 的失敗條件完全一致)
                elif "高級球" in card.name and len(self.state.hand) < 3:
                    valid = False
                elif "特殊紅牌" in card.name:
                    valid = False
                elif card.sub_category == 'Tool' and (not self.state.active_pokemon or self.state.active_pokemon.tool):
                    valid = False
                elif card.sub_category == 'Stadium' and self.state.stadium and self.state.stadium.name == card.name:
                    valid = False
                elif "寶可裝置" in card.name:
                    if len(self.state.deck) == 0:
                        valid = False
                        
                elif "寶可平板" in card.name:
                    if len(self.state.deck) == 0:
                        valid = False
                    else:
                        # 檢查牌庫裡是否有「非規則寶可夢」 (名稱不包含 'ex')
                        eligible_targets = [c for c in self.state.deck if isinstance(c, Pokemon) and "ex" not in c.name]
                        if not eligible_targets:
                            valid = False # 牌庫沒有目標就禁止 AI 打出，避免浪費動作

                # ⚠️ 需要檢查牌庫與棄牌區狀態的卡片
                elif "好友寶芬" in card.name:
                    if len(self.state.bench) >= 5:
                        valid = False
                    else:
                        eligible_targets = [c for c in self.state.deck if isinstance(c, Pokemon) and c.stage == 'Basic' and c.hp <= 70]
                        if not eligible_targets:
                            valid = False

                elif "夜間擔架" in card.name:
                    eligible = [c for c in self.state.discard_pile if isinstance(c, (Pokemon, Energy))]
                    if not eligible:
                        valid = False

                elif "赤松" in card.name and not self.state.supporter_played_this_turn:
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
                    valid = False # PTCG 規則：第一回合（或剛下場）不能進化

            masks[action_idx] = valid

        return masks

    def step(self, action):
        reward = 0
        terminated = False
        self.current_step += 1

        if action == 0:
            # 🌟 宣告結束回合，回合數 +1
            self.current_turn += 1
            
            # 🌟 新增：限定只能走兩回合 (當準備進入第 3 回合時強制結束)
            if self.current_turn > 2:
                terminated = True
            else:
                # 只有在還沒超過兩回合時，才進行換回合的重置與抽牌
                self.state.supporter_played_this_turn = False
                self.state.energy_attached_this_turn = False
                
                # 🌟 新回合開始：抽一張牌
                success, _ = self.state.draw_card(1)
                
                if not success:
                    # 如果抽不出牌 (牌庫抽乾了)，遊戲強制結束
                    terminated = True
                    reward -= 200 
                else:
                    reward += 10
            
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
                        success = False
                        reward -= 30 
                    elif "好友寶芬" in card.name: success, _ = self.state.play_item_buddy_poffin()
                    elif "高級球" in card.name: success, _ = self.state.play_item_ultra_ball()
                    elif "寶可平板" in card.name: 
                        success, _ = self.state.play_item_poke_tablet() # 呼叫專屬的新函數
                    elif "寶可裝置" in card.name: 
                        success, _ = self.state.play_item_pokegear()
                    elif "夜間擔架" in card.name: success, _ = self.state.play_item_night_stretcher()

                    if success: reward += 30

                elif card.sub_category == 'Tool':
                    success, _ = self.state.play_tool(card)
                    if success: reward += 50 

                elif card.sub_category == 'Stadium':
                    success, _ = self.state.play_stadium(card)
                    if success:
                        reward += 30
                    else:
                        reward -= 30 

                elif card.sub_category == 'Supporter':
                    # 🌟 雙重檢查：防止 AI 在面具失效時意外打出
                    if self.current_turn == 1 or self.state.supporter_played_this_turn:
                        success = False
                        reward -= 100 # 嚴厲懲罰違規使用支援者
                    else:
                        if "赤松" in card.name:
                            success, _ = self.state.play_supporter_crispin()
                            if success: reward += 120 
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
                    if len(self.state.bench) < 5:
                        self.state.bench.append(card)
                        success = True
                        if "可達鴨" in card.name:
                            reward -= 50 
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

            if any("可達鴨" in p.name for p in self.state.bench + ([self.state.active_pokemon] if self.state.active_pokemon else [])):
                reward -= 50

            reward += len(self.state.bench) * 15

        return self._get_obs(), reward, terminated, False, {}