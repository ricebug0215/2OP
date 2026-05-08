from sb3_contrib import MaskablePPO
from ptcg_env import PTCGEnv
import json

# 1. 準備「多龍巴魯托ex」完整 60 張牌組資料
# 這裡補齊了 game_engine.py 運作所需的屬性 (category, stage, hp, subCategory)
dragapult_deck = [
    {"id": "sv6-1", "name": "多龍巴魯托ex", "count": 3, "category": "Pokemon", "stage": "Stage2", "hp": 320},
    {"id": "sv6-2", "name": "多龍奇", "count": 4, "category": "Pokemon", "stage": "Stage1", "hp": 90},
    {"id": "sv6-3", "name": "多龍梅西亞", "count": 4, "category": "Pokemon", "stage": "Basic", "hp": 70}, # 寶芬目標
    {"id": "sv6-4", "name": "土龍弟弟", "count": 2, "category": "Pokemon", "stage": "Basic", "hp": 70}, # 寶芬目標
    {"id": "sv6-5", "name": "土龍節節", "count": 2, "category": "Pokemon", "stage": "Stage1", "hp": 140},
    {"id": "sv6-6", "name": "土龍節節ex", "count": 1, "category": "Pokemon", "stage": "Stage1", "hp": 260},
    {"id": "sv6-7", "name": "願增猿", "count": 2, "category": "Pokemon", "stage": "Basic", "hp": 70}, # 寶芬目標
    {"id": "sv6-8", "name": "含羞苞", "count": 1, "category": "Pokemon", "stage": "Basic", "hp": 30}, # 寶芬目標
    {"id": "sv6-9", "name": "可達鴨", "count": 1, "category": "Pokemon", "stage": "Basic", "hp": 60}, # 寶芬目標
    {"id": "t-1", "name": "寶可平板", "count": 4, "category": "Trainer", "subCategory": "Item"},
    {"id": "t-2", "name": "好友寶芬", "count": 4, "category": "Trainer", "subCategory": "Item"},
    {"id": "t-3", "name": "高級球", "count": 3, "category": "Trainer", "subCategory": "Item"},
    {"id": "t-4", "name": "夜間擔架", "count": 2, "category": "Trainer", "subCategory": "Item"},
    {"id": "t-5", "name": "寶可裝置3.0", "count": 2, "category": "Trainer", "subCategory": "Item"},
    {"id": "t-6", "name": "特殊紅牌", "count": 2, "category": "Trainer", "subCategory": "Item"},
    {"id": "t-7", "name": "英雄斗篷", "count": 1, "category": "Trainer", "subCategory": "Tool"},
    {"id": "t-8", "name": "莉莉艾的決意", "count": 4, "category": "Trainer", "subCategory": "Supporter"},
    {"id": "t-9", "name": "赤松", "count": 2, "category": "Trainer", "subCategory": "Supporter"},
    {"id": "t-10", "name": "小剛的發掘", "count": 2, "category": "Trainer", "subCategory": "Supporter"},
    {"id": "t-11", "name": "阿賽蘿拉的惡作劇", "count": 1, "category": "Trainer", "subCategory": "Supporter"},
    {"id": "t-12", "name": "老大的指令", "count": 3, "category": "Trainer", "subCategory": "Supporter"},
    {"id": "t-13", "name": "險惡廢墟", "count": 2, "category": "Trainer", "subCategory": "Stadium"},
    {"id": "e-1", "name": "基本超能量", "count": 3, "category": "Energy"},
    {"id": "e-2", "name": "基本火能量", "count": 3, "category": "Energy"},
    {"id": "e-3", "name": "基本惡能量", "count": 2, "category": "Energy"}
]

# 防呆檢查：確認牌組真的剛好是 60 張
total_cards = sum(c.get('count', 1) for c in dragapult_deck)
print(f"📦 載入牌組：多龍巴魯托ex，總共 {total_cards} 張")
assert total_cards == 60, "牌組數量必須剛好 60 張！"

# 2. 建立訓練環境
env = PTCGEnv(dragapult_deck)

# 3. 實體化大腦 (使用 PPO 演算法)
print("\n🧠 AI 多龍大師誕生，準備開始訓練...")
model = MaskablePPO("MlpPolicy", env, verbose=1)

# 4. 讓 AI 自己玩 100,000 步
print("⚔️ 開始在精神時光屋打牌...")
model.learn(total_timesteps=100000)

# 5. 儲存訓練好的大腦
model.save("ptcg_master_dragapult_ai")
print("\n💾 訓練完成，大腦已儲存為 ptcg_master_dragapult_ai.zip")
