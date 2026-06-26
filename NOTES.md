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
6. 棄牌能量分先後：`choose_discard` 在「能量分類」內再依屬性排序 ——
   主力需要的屬性（`_main_needed_types`，取自 `main_attacker` × `energy_profile`/
   `ENERGY_PROFILES`）留到最後才丟、不需要的先丟（多龍套：草先丟、火/超留）。
7. 戰術棄牌用能量不再被誤貼：新增 `attachable_energy_types()`（= 宣告主力進化線
   需求屬性聯集）。`pick_energy_for_slot` 先以此過濾，牌組用不到的能量（如多龍套
   的惡能量，是給高級球等代價棄掉的）一律不貼、回 None。三處同步：引擎 picker、
   `playbook._try_attach_energy`（None 就跳過不硬塞）、`rl_env` action mask
   （只有非貼附用能量時不開放填能）。未宣告主力/主力吃無色 → 空集合 → 沿用舊行為。
   **⚠️ 改了 RL 環境動態（mask + transition），需重新訓練模型才會對齊新引擎。**
8. 赤松 search→attach 屬性感知：`search_deck` 的 `destination:attach` 路徑原本用
   `choose_targets`(能量挑不到屬性→挑到惡) + `choose_bench_slot`(不看屬性) →
   會把惡能貼到多龍奇。修法：context 帶上 dest；新增 `DecisionMaker.choose_attach_slot`
   (playbook 覆寫成「貼給需要此屬性且還沒貼的主力」)；`choose_targets` 對能量候選改走
   `_pick_energy_targets`(可貼附屬性優先、貼附用絕不挑惡)。
9. 高級球太激進(同回合連打、棄掉莉莉艾/小剛)：新增 `_protected_names`(抽牌支援者+主力)，
   `choose_discard` 讓關鍵牌最後才丟；`choose_action` 加 `_cost_affordable` 閘門 ——
   棄牌代價若得動到關鍵牌就不打該卡，連帶自然抑制連打第二張高級球。
   （這兩項也動到 RL 會用到的 `choose_discard`/`choose_targets` → 同樣需重訓。）
10. 「不像真人」稽核四項修正(2026-06-25)：
    - A 夜間擔架情境選擇：`choose_option` 加分支 —— 棄牌區有主力/進化素材→回收寶可夢；
      否則棄了 ≥3 張主力需求能量→回收能量循環。(原本永遠 options[0]=回收寶可夢)
    - B 搜尋避免拿重複：dm 加 `bind_state` 持有場面；`_rank_search_candidates` +
      `_board_count`，同名(場上鏈+手牌)已有 ≥3 張的寶可夢降級，優先拿缺的。
      門檻設 3(只擋第 4 張起)是為了不損分又對準「已三隻還搜第四隻」的抱怨。
    - C 棄牌保護充能能量：主力需求能量(火/超)在 `choose_discard` 提到 5000 層級，
      只比關鍵牌(100000)早丟；非需求能量(草/惡)維持最先丟。
    - D 莉莉艾出牌條件：`_shuffle_draw_worth` —— 手牌 ≥ count(8) 時不打 `shuffle_hand_draw`
      (洗掉好牌又不賺)；手牌 ≤7 仍照打(抽到 8 仍是淨正、挖展開牌)。
    影響：demo 500–1000 局 avg ~149–155(基準 ~156，B/D 的小幅降分是擋掉負期望/過量play
    的合理代價)。A/C 幾乎中性。B/C/A 也動到 RL 子決策 → 併入既有重訓需求。

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
