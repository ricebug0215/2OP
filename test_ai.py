from sb3_contrib import MaskablePPO
from ptcg_env import PTCGEnv

# 1. 準備牌組資料 (需與環境初始化一致)
dragapult_deck = [
    {"id": "sv6-1", "name": "多龍巴魯托ex", "count": 3, "category": "Pokemon", "stage": "Stage2", "hp": 320},
    {"id": "sv6-2", "name": "多龍奇", "count": 4, "category": "Pokemon", "stage": "Stage1", "hp": 90},
    {"id": "sv6-3", "name": "多龍梅西亞", "count": 4, "category": "Pokemon", "stage": "Basic", "hp": 70},
    {"id": "sv6-4", "name": "土龍弟弟", "count": 2, "category": "Pokemon", "stage": "Basic", "hp": 70},
    {"id": "sv6-5", "name": "土龍節節", "count": 2, "category": "Pokemon", "stage": "Stage1", "hp": 140},
    {"id": "sv6-6", "name": "土龍節節ex", "count": 1, "category": "Pokemon", "stage": "Stage1", "hp": 260},
    {"id": "sv6-7", "name": "願增猿", "count": 2, "category": "Pokemon", "stage": "Basic", "hp": 70},
    {"id": "sv6-8", "name": "含羞苞", "count": 1, "category": "Pokemon", "stage": "Basic", "hp": 30},
    {"id": "sv6-9", "name": "可達鴨", "count": 1, "category": "Pokemon", "stage": "Basic", "hp": 60},
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

# 2. 建立測試環境
env = PTCGEnv(dragapult_deck)

# 3. 載入訓練好的模型
model_path = "ptcg_master_dragapult_ai"
print(f"📥 正在載入模型：{model_path}.zip ...")
try:
    model = MaskablePPO.load(model_path)
except FileNotFoundError:
    print(f"❌ 找不到模型檔案 {model_path}.zip，請確認檔名或先執行訓練！")
    exit()

# 4. 開始單局測試展示
print("\n" + "="*60)
print("🤖 AI 多龍大師 決策展示賽開始")
print("="*60)

obs, _ = env.reset()
total_reward = 0

for step in range(30):
    print(f"\n[回合 {step + 1}] {'-'*45}")

    # --- 1. 取得決策前的真實狀態 ---
    state = env.state
    hand_names = [c.name for c in state.hand]
    print(f"👀 決策前手牌 ({len(hand_names)}張): {hand_names}")

    # --- 2. AI 預測 ---
    action_masks = env.action_masks()
    action, _states = model.predict(obs, action_masks=action_masks, deterministic=True)
    action = int(action)

    # --- 3. 翻譯 Action 為人類可讀文字 ---
    if action == 0:
        action_str = "🛑 宣告結束回合"
    elif action == 20:
        action_str = "⚔️ 宣言攻擊！"
    elif 1 <= action <= len(state.hand):
        # 這裡使用的是決策前的 state.hand
        card_to_play = state.hand[action - 1]
        action_str = f"🃏 嘗試打出卡片：【{card_to_play.name}】"
    else:
        action_str = f"❌ 嘗試執行無效的操作 (Action index {action})"

    print(f"👉 AI 選擇動作: {action_str}")

    # --- 4. 讓環境執行 AI 選擇的動作 ---
    obs, reward, terminated, truncated, info = env.step(action)
    total_reward += reward

    # --- 5. 印出執行後的詳細盤面 ---
    active_pkm = env.state.active_pokemon
    active_str = "無"
    if active_pkm:
        energies = [e.name.replace('基本', '').replace('能量', '') for e in active_pkm.attached_energies]
        tool = active_pkm.tool.name if active_pkm.tool else "無"
        active_str = f"{active_pkm.name} (HP: {active_pkm.hp}) | 貼附能量: {energies} | 裝備: {tool}"

    bench_str = [f"{p.name}" for p in env.state.bench]
    stadium = env.state.stadium.name if env.state.stadium else "無"

    print(f"  ├ 戰鬥區 : {active_str}")
    print(f"  ├ 備戰區 ({len(bench_str)}/5): {bench_str}")
    print(f"  ├ 競技場 : {stadium}")
    print(f"  ├ 規則限制 : 支援者已用? {'✅' if env.state.supporter_played_this_turn else '❌'} | 手填能量已用? {'✅' if env.state.energy_attached_this_turn else '❌'}")
    print(f"  ├ 牌庫狀況 : 剩餘 {len(env.state.deck)} 張 | 棄牌區 {len(env.state.discard_pile)} 張")
    print(f"  └ 💰 本步獲得分數: {reward} (本局累計: {total_reward})")

    if terminated:
        print("\n" + "="*60)
        print(f"🎉 回合結束！AI 已經完成展開。本局總得分：{total_reward}")
        print("="*60)
        break
