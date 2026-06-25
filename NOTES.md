# 開發筆記 / Session Handoff

PTCG T1/T2 展開模擬器。RL（MaskablePPO）+ playbook heuristic 混合架構。
模型在 `models/ptcg_setup_ppo_best`。venv 在 `./venv`（外部管理環境，pip 要用 venv）。

## 核心檔案

- **`game_engine.py`** — 引擎。含 `EVOLVES_FROM` / `ENERGY_PROFILES` 全域表、
  `needed_energy_types` / `pick_energy_for_slot` / `is_main_attacker` /
  `evolution_line_of` / `expand_main_attackers` / `energy_type_of`、
  `can_evolve_to`（名字感知，防跨線進化）。
  `choose_option` 簽名已改為 `(options, state, context)`。
- **`playbook.py`** — `PlaybookDecisionMaker` + `evaluate_board`（計分含屬性感知）
  + `SimulationRunner`。
- **`rl_env.py`** — Gym 環境。RL 選目標寶可夢，能量屬性由引擎智慧挑。
- **`generate_effects.py`** — 爬蟲 + LLM pipeline。模式：
  - （無旗標 = 產生 DSL，需 `ANTHROPIC_API_KEY`）
  - `--dry`（只抓文字不呼叫 LLM）
  - `--missing`（缺定義的 Trainer 卡）
  - `--evolution`（更新 evolution_chains.json）
  - `--energy-profile`（更新 energy_profiles.json）
- **`server.py`**（FastAPI）+ **`src/App.jsx`**（React 前端）。
- 資料檔：`card_effects.json`、`evolution_chains.json`（{進化卡:進化前}）、
  `energy_profiles.json`（{寶可夢:[屬性]}）。

## 已完成（近期 session）

1. LLM pipeline + 補齊 5 張缺卡（特殊紅牌 / 英雄斗篷 / 險惡廢墟 /
   阿塞蘿拉的惡作劇 / 老大的指令，標 `opponent_effect` / `not_implemented`）。
2. 進化鏈自動抓取 + 修正 `can_evolve_to` 名字感知（防跨進化線錯誤進化）。
3. 填能屬性正確：
   - `energy_profiles` 自動推導主力招式能量需求（爬最高階 ex 的招式）
   - `main_attacker` 由使用者宣告（自動推導 + 可覆寫）
   - 計分 / 填能屬性壓力**只對宣告的主力生效**（避免錯誤獎勵願增猿等非主力）
4. `supporter_priority`（修「寶可裝置3.0 選第一張支援者」bug）；
   `小剛的發掘` 啟發式（備戰基礎 ≥3 且 主力基礎在場 → 才拿進化，否則鋪場）。
5. 前端：⚔️ 主力標記（**整條進化線當單位、同亮度連動**）；禁卡維持逐卡。
   後端 `GET /api/evolution-chains` 端點 + `simulate-t2` 收 `main_attacker` 並展開進化線。

## 關鍵決策（為什麼這樣做）

- **主力 = 使用者宣告**：主力是牌組策略的固定事實，每局都一樣 → RL 沒有局間變異可學，
  自動偵測又脆（願增猿招式要超、實際靠特性要惡，純看招式會判錯）。
- **禁卡逐卡（刻意）**：禁 ex 不會禁基礎，可表達「只停 1 階不進化到 ex」。連動會誤導，故不連動。
- **禁基礎的行為**：不會進備戰（三條上場路徑全過濾）；連戰鬥區也避開，
  只在手牌基礎全被禁、無合法替代時才被迫上戰鬥。

## 開放項目

- `土龍節節` 逃跑抽出（抽 3 後把自己洗回牌庫）需要新動作原語 —— 未做。
- 特殊能量效果（如燃料【火】能量）—— 框架留好（`energy_type_of` 解析屬性），未實作效果。
- `夜間擔架` 的 `choose_one` 仍預設選第一個（回收寶可夢），未加情境啟發式。
- web 端 playbook 其餘 priority（search_priority / evolution_lines 等）仍寫死多龍牌組，
  未支援任意牌組自動產生 playbook。
- 已改 `choose_option` 簽名為 `(options, state, context)`，partner 若有自訂
  `DecisionMaker` 子類別需同步更新簽名。

## 換新牌組流程

1. `python generate_effects.py --evolution <寶可夢...>`（補進化關係）
2. `python generate_effects.py --energy-profile <寶可夢...>`（補主力能量需求）
3.（選用）對缺的 Trainer 卡跑 DSL 產生
   注意：evolution_chains.json / energy_profiles.json 只含已抓過的卡，新增寶可夢要重跑。
