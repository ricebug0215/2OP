from stable_baselines3 import PPO
from ptcg_env import PTCGEnv
import json

# 1. 準備一副測試用牌組資料 (這裡你可以從前端 console.log 複製一包 JSON 過來)
# 確保裡面有很多低血量基礎怪跟好友寶芬
dummy_deck = [
    {"id": "sv5-1", "name": "小火龍", "category": "Pokemon", "stage": "Basic", "hp": 70, "count": 4},
    {"id": "sv5-153", "name": "好友寶芬", "category": "Trainer", "subCategory": "Item", "count": 4},
    # ... 湊滿 60 張
]
while sum(c.get('count', 1) for c in dummy_deck) < 60:
    dummy_deck.append({"id": "energy", "name": "基本火能量", "category": "Energy", "count": 1})

# 2. 建立訓練環境
env = PTCGEnv(dummy_deck)

# 3. 實體化大腦 (使用 PPO 演算法，這跟 ChatGPT 底層用的強化學習邏輯同源)
print("🧠 AI 誕生，準備開始訓練...")
model = PPO("MlpPolicy", env, verbose=1)

# 4. 讓 AI 自己玩 10,000 步 (可以改成十萬、百萬)
print("⚔️ 開始在精神時光屋打牌...")
model.learn(total_timesteps=10000)

# 5. 儲存訓練好的大腦
model.save("ptcg_master_ai")
print("💾 訓練完成，大腦已儲存為 ptcg_master_ai.zip")

# 6. 驗收成果：讓訓練好的 AI 玩一場給你看
obs, _ = env.reset()
print("\n--- 驗收 AI 的神之一手 ---")
for i in range(20):
    # AI 根據目前的盤面 (obs)，預測下一步該怎麼走
    action, _states = model.predict(obs)
    print(f"第 {i+1} 步：AI 選擇了動作 {action}")
    
    obs, reward, done, _, _ = env.step(action)
    print(f" -> 獲得分數: {reward}, 目前備戰區怪獸數: {len(env.state.bench)}")
    
    if done:
        print("回合結束！")
        break