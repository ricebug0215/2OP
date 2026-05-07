import gymnasium as gym
from gymnasium import spaces
import numpy as np
from game_engine import GameState, parse_deck, Pokemon, Trainer

class PTCGEnv(gym.Env):
    """自定義的 PTCG 強化學習環境"""
    
    def __init__(self, raw_deck_data):
        super(PTCGEnv, self).__init__()
        self.raw_deck_data = raw_deck_data
        
        # 1. 動作空間 (Action Space)：AI 能做什麼？
        # 假設 AI 每回合最多只有 20 種可能的動作 (例如: 0=結束回合, 1=打出第一張手牌, 2=打出第二張...)
        self.action_space = spaces.Discrete(20)
        
        # 2. 觀察空間 (Observation Space)：AI 能看到什麼？
        # 為了簡化，我們先讓 AI 看一個長度為 10 的數字陣列：
        # [手牌數量, 戰鬥區血量, 備戰區怪獸數量, 牌庫剩餘張數, ...]
        self.observation_space = spaces.Box(low=0, high=300, shape=(10,), dtype=np.float32)
        
        self.state = None
        
    def _get_obs(self):
        """將 GameState 翻譯成 AI 看得懂的數字陣列"""
        obs = np.zeros(10, dtype=np.float32)
        if self.state.active_pokemon:
            obs[0] = len(self.state.hand)
            obs[1] = int(self.state.active_pokemon.hp)
            obs[2] = len(self.state.bench)
            obs[3] = len(self.state.deck)
            # ... 其他位置可以放更多資訊
        return obs

    def reset(self, seed=None):
        """重置環境（開始新的一局）"""
        super().reset(seed=seed)
        cards = parse_deck(self.raw_deck_data)
        self.state = GameState(cards)
        self.state.shuffle_deck()
        
        # 簡化版的起手發牌
        self.state.hand = self.state.deck[:7]
        self.state.deck = self.state.deck[7:]
        self.state.setup_active_pokemon()
        
        self.current_step = 0
        return self._get_obs(), {}

    def step(self, action):
        """AI 執行一個動作，環境回傳結果與分數"""
        reward = 0
        terminated = False
        self.current_step += 1
        
        # 解譯 AI 的動作 (action 是一個 0~19 的數字)
        if action == 0:
            # AI 決定結束回合
            terminated = True
        elif 1 <= action <= len(self.state.hand):
            # AI 決定打出手牌 (例如 action=1 代表打出 index 0 的牌)
            card_idx = action - 1
            card = self.state.hand[card_idx]
            
            if isinstance(card, Trainer) and card.sub_category == 'Item':
                if "好友寶芬" in card.name:
                    success, _ = self.state.play_item_buddy_poffin()
                    if success:
                        self.state.hand.pop(card_idx)
                        reward += 50 # 獎勵！成功發動關鍵卡
                    else:
                        reward -= 10 # 懲罰！發動失敗 (例如備戰滿了)
            else:
                reward -= 5 # 懲罰！打出了目前不能打的牌 (例如第一回合不能下支援者)
        else:
            reward -= 10 # 懲罰！選擇了無效動作 (例如手牌只有 5 張卻選了打出第 8 張)
            
        # 安全機制：最多讓 AI 嘗試 20 步就強制結束，避免死迴圈
        if self.current_step >= 20:
            terminated = True
            
        # 回合結束的最終結算獎勵
        if terminated:
            reward += len(self.state.bench) * 20 # 備戰區越多怪，分數越高！
            
        return self._get_obs(), reward, terminated, False, {}