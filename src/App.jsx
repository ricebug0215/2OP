import React, { useState, useEffect } from 'react';
import { Search, Plus, Minus, Trash2, Zap, BookOpen, X, ChevronDown, ChevronUp, Eye } from 'lucide-react';

const FALLBACK_IMAGE = 'https://placehold.co/240x336/1e293b/64748b?text=No+Image';

const FILTER_CONFIG = {
  Pokemon: [
    { label: '全部屬性', value: 'All' },
    { label: '草', value: '草' }, { label: '火', value: '火' },
    { label: '水', value: '水' }, { label: '雷', value: '雷' },
    { label: '超', value: '超' }, { label: '鬥', value: '鬥' },
    { label: '惡', value: '惡' }, { label: '鋼', value: '鋼' },
    { label: '龍', value: '龍' }, { label: '無', value: '無' }
  ],
  Trainer: [
    { label: '全部類型', value: 'All' },
    { label: '物品', value: '物品卡' },
    { label: '支援者', value: '支援者卡' },
    { label: '道具', value: '寶可夢道具卡' },
    { label: '競技場', value: '競技場卡' }
  ],
  Energy: [
    { label: '全部', value: 'All' },
    { label: '基本能量', value: '基本能量卡' },
    { label: '特殊能量', value: '特殊能量卡' }
  ]
};

const PRESET_DECKS = [
  {
    name: "多龍巴魯托 ex",
    cardList: [
      { name: "多龍巴魯托ex", count: 3 },
      { name: "多龍奇", count: 4 },
      { name: "多龍梅西亞", count: 4 },
      { name: "土龍弟弟", count: 2 },
      { name: "土龍節節", count: 2 },
      { name: "土龍節節ex", count: 1 },
      { name: "願增猿", count: 2 },
      { name: "含羞苞", count: 1 },
      { name: "可達鴨", count: 1 },
      { name: "寶可平板", count: 4 },
      { name: "好友寶芬", count: 4 },
      { name: "高級球", count: 3 },
      { name: "夜間擔架", count: 2 },
      { name: "寶可裝置3.0", count: 2 },
      { name: "特殊紅牌", count: 2 },
      { name: "英雄斗篷", count: 1 },
      { name: "莉莉艾的決意", count: 4 },
      { name: "赤松", count: 2 },
      { name: "小剛的發掘", count: 2 },
      { name: "阿塞蘿拉的惡作劇", count: 1 },
      { name: "老大的指令", count: 3 },
      { name: "險惡廢墟", count: 2 },
      { name: "基本【超】能量", count: 3 },
      { name: "基本【火】能量", count: 3 },
      { name: "基本【惡】能量", count: 2 }
    ]
  }
];

const ENERGY_COLORS = {
  '草': '#4ade80', '火': '#f97316', '水': '#38bdf8', '雷': '#facc15',
  '超': '#c084fc', '鬥': '#b45309', '惡': '#7c3aed', '鋼': '#94a3b8',
  '龍': '#fbbf24', '無': '#d1d5db',
};

function getEnergyType(energyName) {
  const match = energyName.match(/【(.+?)】/);
  return match ? match[1] : '無';
}

function getTier(score, tiers) {
  if (tiers) {
    if (score >= tiers.p95) return { label: '天胡', color: 'text-yellow-300', bg: 'bg-yellow-500/15 border-yellow-500/40' };
    if (score >= tiers.p75) return { label: '優良', color: 'text-green-400', bg: 'bg-green-500/15 border-green-500/40' };
    if (score >= tiers.p50) return { label: '普通', color: 'text-blue-400', bg: 'bg-blue-500/15 border-blue-500/40' };
    if (score >= tiers.p25) return { label: '不好', color: 'text-orange-400', bg: 'bg-orange-500/15 border-orange-500/40' };
    return { label: '天崩', color: 'text-red-400', bg: 'bg-red-500/15 border-red-500/40' };
  }
  if (score >= 160) return { label: '天胡', color: 'text-yellow-300', bg: 'bg-yellow-500/15 border-yellow-500/40' };
  if (score >= 120) return { label: '優良', color: 'text-green-400', bg: 'bg-green-500/15 border-green-500/40' };
  if (score >= 80)  return { label: '普通', color: 'text-blue-400', bg: 'bg-blue-500/15 border-blue-500/40' };
  if (score >= 40)  return { label: '不好', color: 'text-orange-400', bg: 'bg-orange-500/15 border-orange-500/40' };
  return { label: '天崩', color: 'text-red-400', bg: 'bg-red-500/15 border-red-500/40' };
}

function EnergyBadges({ energyCards }) {
  if (!energyCards || energyCards.length === 0) return null;
  return (
    <div className="flex gap-0.5 flex-wrap mt-1 justify-center">
      {energyCards.map((e, i) => {
        const type = getEnergyType(e.name);
        const color = ENERGY_COLORS[type] || ENERGY_COLORS['無'];
        return (
          <div
            key={i}
            className="w-4 h-4 rounded-full border border-white/30 flex items-center justify-center text-[7px] font-black shadow-sm"
            style={{ backgroundColor: color }}
            title={e.name}
          >
            {type}
          </div>
        );
      })}
    </div>
  );
}

function PokemonSlotCard({ slot, size = 'md' }) {
  if (!slot) return null;
  const sizeClass = size === 'lg' ? 'w-32' : 'w-20';
  const hasChain = slot.chain && slot.chain.length > 1;
  return (
    <div className={`${sizeClass} flex-shrink-0 group`}>
      <div className="relative rounded-sm overflow-hidden">
        <img src={slot.image || FALLBACK_IMAGE} alt={slot.name} className="w-full h-auto" />
        {hasChain && (
          <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/95 to-transparent px-1 pt-5 pb-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <p className="text-[8px] text-blue-300 font-bold text-center leading-tight">
              {slot.chain.map(c => c.name).join(' → ')}
            </p>
          </div>
        )}
      </div>
      <p className="text-[10px] text-center text-gray-400 font-bold truncate mt-1">{slot.name}</p>
      <EnergyBadges energyCards={slot.energy_cards} />
    </div>
  );
}

function StepLog({ log }) {
  const [expanded, setExpanded] = useState(true);
  const setupEntry = log.find(e => e.phase === 'setup');
  const turns = log.filter(e => e.phase && e.phase !== 'setup');

  return (
    <div className="bg-[#020617] rounded-2xl border border-white/5">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between p-4 text-left">
        <span className="text-sm font-black text-gray-300">操作紀錄</span>
        {expanded ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />}
      </button>
      {expanded && (
        <div className="px-4 pb-4 space-y-4 max-h-64 overflow-y-auto">
          {setupEntry && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-black text-gray-400 bg-gray-500/10 px-2 py-0.5 rounded">起始設置</span>
              </div>
              <div className="ml-4 space-y-1">
                <p className="text-xs text-gray-300">
                  <span className="text-gray-500">起手牌：</span>{setupEntry.detail.hand.join('、')}
                </p>
                <p className="text-xs text-gray-300">
                  <span className="text-gray-500">戰鬥區：</span>{setupEntry.detail.active || '（無）'}
                </p>
                {setupEntry.detail.bench.length > 0 && (
                  <p className="text-xs text-gray-300">
                    <span className="text-gray-500">備戰區：</span>{setupEntry.detail.bench.join('、')}
                  </p>
                )}
                <p className="text-[10px] text-gray-600">
                  獎賞 {setupEntry.detail.prizes_set_aside} 張 ｜ 牌庫 {setupEntry.detail.deck_remaining} 張
                </p>
              </div>
            </div>
          )}

          {turns.map((turn, ti) => (
            <div key={ti}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-black text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded">{turn.phase}</span>
                {turn.drew && <span className="text-xs text-gray-500">抽牌: {turn.drew}</span>}
              </div>
              {turn.steps.length === 0 && <p className="text-xs text-gray-600 ml-4">（無操作）</p>}
              {turn.steps.map((step, si) => (
                <div key={si} className="ml-4 mb-1.5 flex items-start gap-2">
                  <span className="text-[10px] font-mono text-gray-600 mt-0.5 flex-shrink-0 w-4 text-right">{step.step}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-gray-300 font-bold">{step.action}</p>
                    {step.details.map((d, di) => (
                      <p key={di} className="text-[11px] text-gray-500 ml-2">→ {d}</p>
                    ))}
                    <p className="text-[10px] text-gray-600 mt-0.5">
                      牌庫 {step.deck_size} 張 ｜ 棄牌 {step.discard_size} 張
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


export default function App() {
  const [cards, setCards] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [filter, setFilter] = useState('All');
  const [subFilter, setSubFilter] = useState('All');
  const [deck, setDeck] = useState([]);
  const [simulationResult, setSimulationResult] = useState(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [discardOpen, setDiscardOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoadingCards, setIsLoadingCards] = useState(false);

  const deckCount = deck.reduce((sum, c) => sum + (c.count || 1), 0);
  const pokemonCount = deck.filter(c => c.category === 'Pokemon').reduce((sum, c) => sum + c.count, 0);
  const trainerCount = deck.filter(c => c.category === 'Trainer').reduce((sum, c) => sum + c.count, 0);
  const energyCount = deck.filter(c => c.category === 'Energy').reduce((sum, c) => sum + c.count, 0);

  useEffect(() => { setSubFilter('All'); }, [filter]);
  useEffect(() => { setPage(1); }, [searchTerm, filter, subFilter]);

  useEffect(() => {
    const fetchCards = async () => {
      setIsLoadingCards(true);
      try {
        const url = `http://127.0.0.1:8000/api/cards?name=${searchTerm}&category=${filter}&type=${subFilter}&page=${page}&limit=48`;
        const response = await fetch(url);
        const data = await response.json();
        setCards(data.items);
        setTotalPages(Math.ceil(data.total / 48) || 1);
      } catch (error) { console.error("伺服器連線失敗"); }
      finally { setIsLoadingCards(false); }
    };
    const debounce = setTimeout(fetchCards, 300);
    return () => clearTimeout(debounce);
  }, [searchTerm, filter, subFilter, page]);

  const loadPresetDeck = async (idx) => {
    if (deck.length > 0 && !window.confirm("確定清空現有牌組？")) return;
    setIsSimulating(true);
    try {
      const response = await fetch('http://127.0.0.1:8000/api/import-deck', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(PRESET_DECKS[idx].cardList)
      });
      const result = await response.json();
      if (result.notFound.length > 0) alert(`找不到：${result.notFound.join(', ')}`);
      setDeck(result.deck);
    } catch (e) { alert("匯入失敗"); }
    finally { setIsSimulating(false); }
  };

  const addToDeck = (card) => {
    const cardInDeck = deck.find(c => c.name === card.name);
    if (deckCount >= 60) return alert("牌組已滿 60 張！");
    if (card.isAceSpec) {
      const hasAceSpec = deck.some(c => c.isAceSpec);
      if (hasAceSpec && !cardInDeck) return alert("ACE SPEC 全牌組只能放一張！");
    }
    const isBasicEnergy = card.category === 'Energy' && (card.subCategory?.includes('基本') || card.name.includes('基本'));
    if (!isBasicEnergy && !card.isAceSpec) {
      if (cardInDeck && cardInDeck.count >= 4) return alert(`「${card.name}」最多只能放 4 張！`);
    }
    if (cardInDeck) {
      setDeck(deck.map(c => c.name === card.name ? { ...c, count: c.count + 1 } : c));
    } else {
      setDeck([...deck, { ...card, count: 1 }]);
    }
  };

  const removeFromDeck = (cardName) => {
    const cardInDeck = deck.find(c => c.name === cardName);
    if (!cardInDeck) return;
    if (cardInDeck.count > 1) {
      setDeck(deck.map(c => c.name === cardName ? { ...c, count: c.count - 1 } : c));
    } else {
      setDeck(deck.filter(c => c.name !== cardName));
    }
  };

  const startSimulation = async () => {
    if (deckCount !== 60) return alert("請先湊齊 60 張牌！");
    setIsSimulating(true);
    setDiscardOpen(false);
    try {
      const deckList = deck.map(c => ({ name: c.name, count: c.count, category: c.category, sub_type: c.subCategory || '' }));
      const resp = await fetch('http://127.0.0.1:8000/api/simulate-t2', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ deck: deckList })
      });
      const result = await resp.json();
      setSimulationResult(result);
      setShowModal(true);
    } catch (e) { alert("連線錯誤"); }
    finally { setIsSimulating(false); }
  };

  const board = simulationResult?.board;
  const score = simulationResult?.score;
  const tiers = simulationResult?.tiers;
  const tier = score != null ? getTier(score, tiers) : null;

  return (
    <div className="flex h-screen w-screen bg-[#020617] text-white overflow-hidden">

      {/* 左：畫廊 */}
      <div className="flex-1 flex flex-col border-r border-gray-800 relative">
        <div className="p-6 bg-[#0f172a] shadow-md z-20">
          <h1 className="text-2xl font-black flex items-center gap-3 mb-4"><Zap className="text-yellow-400 fill-yellow-400" /> PTCG 展開模擬器</h1>
          <div className="flex gap-3">
            <input
              className="flex-1 bg-[#1e293b] border border-gray-700 rounded-xl px-4 py-2"
              placeholder="搜尋卡片..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
            />
            <select className="bg-[#1e293b] border border-gray-700 rounded-xl px-4" value={filter} onChange={e => setFilter(e.target.value)}>
              <option value="All">全部</option>
              <option value="Pokemon">寶可夢</option>
              <option value="Trainer">訓練家</option>
              <option value="Energy">能量</option>
            </select>
          </div>

          {FILTER_CONFIG[filter] && filter !== 'All' && (
            <div className="flex flex-wrap gap-3 pt-4 pb-1 pl-1">
              {FILTER_CONFIG[filter].map((item) => (
                <button
                  key={item.value}
                  onClick={() => setSubFilter(item.value)}
                  className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all border ${
                    subFilter === item.value
                      ? 'bg-blue-600 border-blue-400 shadow-[0_0_10px_rgba(37,99,235,0.4)] text-white'
                      : 'bg-[#1e293b] border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-8 bg-[#020617]">
          {isLoadingCards ? (
            <div className="flex justify-center items-center h-full text-blue-500 font-bold text-lg">讀取卡片中...</div>
          ) : cards.length === 0 ? (
            <div className="flex justify-center items-center h-full text-gray-500 font-bold text-lg">找不到符合條件的卡片</div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-6 pb-6">
              {cards.map(card => (
                <div key={card.id} className="cursor-pointer hover:-translate-y-1 transition-transform group" onClick={() => addToDeck(card)}>
                  <div className={`relative rounded-xl overflow-hidden ${card.isAceSpec ? 'ring-2 ring-pink-500 shadow-[0_0_15px_rgba(236,72,153,0.4)]' : ''}`}>
                    <img src={card.image || FALLBACK_IMAGE} className="w-full h-auto shadow-lg border border-white/10" alt={card.name} />
                  </div>
                  <p className={`mt-2 text-xs text-center font-bold ${card.isAceSpec ? 'text-pink-400' : 'text-gray-400'}`}>{card.name}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="p-4 bg-[#0f172a] border-t border-gray-800 flex justify-center items-center gap-6 shadow-[0_-10px_20px_rgba(0,0,0,0.2)] z-30">
          <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="px-6 py-2 bg-[#1e293b] rounded-lg font-bold disabled:opacity-30 hover:bg-blue-600 transition-colors">上一頁</button>
          <span className="text-gray-400 font-mono font-bold text-lg"><span className="text-white">{page}</span> / {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} className="px-6 py-2 bg-[#1e293b] rounded-lg font-bold disabled:opacity-30 hover:bg-blue-600 transition-colors">下一頁</button>
        </div>
      </div>

      {/* 右：牌組管理區 */}
      <div className="w-96 bg-[#0f172a] flex flex-col z-40 shadow-2xl border-l border-gray-800">

        <div className="p-4 bg-[#1e293b] border-b border-gray-800">
          <select className="w-full bg-[#0f172a] rounded-lg p-2 text-blue-400 font-bold" onChange={e => e.target.value && loadPresetDeck(e.target.value)} defaultValue="">
            <option value="" disabled>快速載入主流牌組...</option>
            {PRESET_DECKS.map((p, i) => <option key={i} value={i}>{p.name}</option>)}
          </select>
        </div>

        <div className="p-5 border-b border-gray-800 space-y-4">
          <div className="flex justify-between items-end">
            <h2 className="text-xl font-black">目前牌組</h2>
            <span className={`text-sm font-mono font-bold ${deckCount === 60 ? 'text-green-400' : 'text-blue-400'}`}>
              {deckCount} / 60
            </span>
          </div>
          <div className="w-full bg-gray-900 h-2 rounded-full overflow-hidden">
            <div className={`h-full transition-all duration-500 ${deckCount === 60 ? 'bg-green-500' : 'bg-blue-500'}`} style={{ width: `${(deckCount/60)*100}%` }}></div>
          </div>
          <div className="flex justify-between text-[10px] font-black uppercase tracking-tighter text-gray-500">
            <div className="flex flex-col items-center"><span>Pokemon</span><span className="text-blue-400 text-sm">{pokemonCount}</span></div>
            <div className="flex flex-col items-center"><span>Trainer</span><span className="text-purple-400 text-sm">{trainerCount}</span></div>
            <div className="flex flex-col items-center"><span>Energy</span><span className="text-yellow-400 text-sm">{energyCount}</span></div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {deck.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-600 opacity-50 space-y-2">
              <BookOpen className="w-10 h-10" />
              <p className="text-sm font-bold">牌組是空的</p>
            </div>
          ) : (
            deck.map(c => (
              <div key={c.name} className="flex items-center justify-between bg-[#1e293b] p-3 rounded-xl border border-white/5 group transition-all hover:bg-[#253248]">
                <span className={`text-sm font-bold truncate pr-2 ${c.isAceSpec ? 'text-pink-400' : 'text-gray-200'}`}>{c.name}</span>
                <div className="flex items-center gap-2">
                  <div className="flex items-center bg-gray-900/50 rounded-lg border border-white/5 p-1">
                    <button onClick={() => removeFromDeck(c.name)} className="p-1 hover:text-red-400"><Minus className="w-3 h-3" /></button>
                    <span className="w-6 text-center text-xs font-mono font-bold text-blue-400">{c.count}</span>
                    <button onClick={() => addToDeck(c)} className="p-1 hover:text-green-400"><Plus className="w-3 h-3" /></button>
                  </div>
                  <button onClick={() => setDeck(deck.filter(item => item.name !== c.name))} className="p-1.5 text-gray-600 hover:text-red-500 transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        <button onClick={startSimulation} disabled={deckCount !== 60 || isSimulating} className="m-6 p-4 bg-blue-600 rounded-xl font-black text-lg hover:bg-blue-500 disabled:bg-gray-800 transition-colors shadow-lg">
          {isSimulating ? '模擬中...' : '開始展開模擬'}
        </button>
      </div>

      {/* T2 模擬結果 */}
      {showModal && board && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/90 backdrop-blur-md">
          <div className={`relative w-full bg-[#0f172a] border border-blue-500/30 rounded-3xl shadow-[0_0_80px_rgba(37,99,235,0.15)] overflow-hidden flex flex-col max-h-[95vh] transition-all duration-500 ease-in-out ${discardOpen ? 'max-w-[1400px]' : 'max-w-5xl'}`}>

            {/* Header */}
            <div className="px-8 py-5 border-b border-gray-800 flex justify-between items-center bg-[#1e293b]/50 shrink-0">
              <div className="flex items-center gap-5">
                <h2 className="text-2xl font-black text-white flex items-center gap-3">
                  <Zap className="text-yellow-400 fill-yellow-400 w-7 h-7" /> T2 展開結果
                </h2>
                {tier && (
                  <div className={`px-4 py-1.5 rounded-xl border ${tier.bg} flex items-center gap-2`}>
                    <span className={`text-xl font-black ${tier.color}`}>{tier.label}</span>
                    <span className="text-[10px] text-gray-600 font-mono">({Math.round(score)})</span>
                  </div>
                )}
              </div>
              <button onClick={() => { setShowModal(false); setDiscardOpen(false); }} className="bg-gray-800 hover:bg-gray-700 text-white p-2 rounded-full transition-colors">
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Body: board + discard panel */}
            <div className="flex-1 overflow-hidden flex">

              {/* Main board area */}
              <div className="flex-1 min-w-0 overflow-y-auto p-6 transition-all duration-500 ease-in-out">
                <div className="grid grid-cols-[140px_1fr_120px] gap-6 items-start mb-6">

                  {/* Left: Prizes (face up) */}
                  <div>
                    <p className="text-[10px] font-black text-pink-500 uppercase tracking-wider mb-2 text-center">獎賞卡</p>
                    <div className="grid grid-cols-2 gap-1.5">
                      {board.prize_cards.map((card, i) => (
                        <div key={i} className="rounded overflow-hidden ring-1 ring-white/10">
                          <img src={card.image || FALLBACK_IMAGE} alt={card.name} className="w-full h-auto" />
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Center: Active + Bench */}
                  <div className="flex flex-col items-center gap-4">
                    <div>
                      <p className="text-[10px] font-black text-yellow-500 uppercase tracking-wider mb-2 text-center">戰鬥區</p>
                      {board.active_detail ? (
                        <PokemonSlotCard slot={board.active_detail} size="lg" />
                      ) : (
                        <div className="w-32 aspect-[2.5/3.5] bg-[#1e293b] rounded-lg border border-dashed border-gray-700 flex items-center justify-center">
                          <span className="text-gray-700 text-xs">空</span>
                        </div>
                      )}
                    </div>

                    <div>
                      <p className="text-[10px] font-black text-green-500 uppercase tracking-wider mb-2 text-center">備戰區</p>
                      <div className="flex gap-2 justify-center">
                        {board.bench_details.map((slot, i) => (
                          <PokemonSlotCard key={i} slot={slot} size="md" />
                        ))}
                        {Array.from({ length: 5 - board.bench_details.length }).map((_, i) => (
                          <div key={`empty-${i}`} className="w-20 aspect-[2.5/3.5] bg-[#0a0f1e] rounded border border-dashed border-gray-800" />
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Right: Deck + Discard */}
                  <div className="space-y-4">
                    <div>
                      <p className="text-[10px] font-black text-blue-400 uppercase tracking-wider mb-2 text-center">牌庫</p>
                      <div className="aspect-[2.5/3.5] bg-[#1e293b] rounded-lg border border-white/10 flex flex-col items-center justify-center">
                        <span className="text-2xl font-black text-blue-400 font-mono">{board.deck_size}</span>
                        <span className="text-[10px] text-gray-500">張</span>
                      </div>
                    </div>
                    <div
                      className="cursor-pointer group"
                      onClick={() => board.discard_cards.length > 0 && setDiscardOpen(!discardOpen)}
                    >
                      <p className="text-[10px] font-black text-orange-400 uppercase tracking-wider mb-2 text-center">棄牌區</p>
                      <div className={`aspect-[2.5/3.5] bg-[#1e293b] rounded-lg border flex flex-col items-center justify-center transition-colors ${discardOpen ? 'border-orange-500/60 ring-1 ring-orange-500/30' : 'border-white/10 group-hover:border-orange-500/50'}`}>
                        <span className="text-2xl font-black text-orange-400 font-mono">{board.discard_size}</span>
                        <span className="text-[10px] text-gray-500">張</span>
                      </div>
                      {board.discard_size > 0 && (
                        <p className="text-[10px] text-gray-600 text-center mt-1.5 flex items-center justify-center gap-1 group-hover:text-orange-400 transition-colors">
                          <Eye className="w-3 h-3" /> {discardOpen ? '收起' : '展開'}
                        </p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Hand */}
                <div className="mb-6">
                  <p className="text-[10px] font-black text-cyan-400 uppercase tracking-wider mb-3">手牌（{board.hand_size} 張）</p>
                  <div className="flex gap-2 overflow-x-auto pb-2">
                    {board.hand_cards.map((card, i) => (
                      <div key={i} className="w-20 flex-shrink-0">
                        <div className="rounded-lg overflow-hidden ring-1 ring-white/10 hover:ring-cyan-500/50 transition-all">
                          <img src={card.image || FALLBACK_IMAGE} alt={card.name} className="w-full h-auto" />
                        </div>
                        <p className="text-[9px] text-center text-gray-500 font-bold truncate mt-1">{card.name}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Step Log */}
                <StepLog log={simulationResult.log} />
              </div>

              {/* Discard panel (slides in from right) */}
              <div
                className={`shrink-0 overflow-y-auto border-l bg-[#0a0f1e] transition-all duration-500 ease-in-out ${
                  discardOpen ? 'w-72 opacity-100 p-4 border-gray-800' : 'w-0 opacity-0 p-0 border-transparent'
                }`}
              >
                <div className="min-w-[260px]">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-xs font-black text-orange-400">棄牌區（{board.discard_size} 張）</p>
                    <button onClick={() => setDiscardOpen(false)} className="text-gray-500 hover:text-white">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {board.discard_cards.map((card, i) => (
                      <div key={i}>
                        <div className="rounded-sm overflow-hidden ring-1 ring-white/10">
                          <img src={card.image || FALLBACK_IMAGE} alt={card.name} className="w-full h-auto" />
                        </div>
                        <p className="text-[9px] text-center text-gray-500 font-bold truncate mt-1">{card.name}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="px-8 py-4 border-t border-gray-800 bg-[#020617] flex justify-center gap-4 shrink-0">
              <button
                onClick={startSimulation}
                className="px-8 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-black text-base transition-all shadow-lg active:scale-95"
              >
                重新模擬
              </button>
              <button
                onClick={() => { setShowModal(false); setDiscardOpen(false); }}
                className="px-8 py-3 bg-gray-800 hover:bg-gray-700 text-white rounded-xl font-black text-base transition-all"
              >
                返回編輯
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
