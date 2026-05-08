import React, { useState, useEffect } from 'react';
import { Search, Plus, Minus, Trash2, Zap, BookOpen, X } from 'lucide-react';

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

export default function App() {
  const [cards, setCards] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [filter, setFilter] = useState('All');
  const [subFilter, setSubFilter] = useState('All');
  const [deck, setDeck] = useState([]);
  const [simulationResult, setSimulationResult] = useState(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoadingCards, setIsLoadingCards] = useState(false);

  // 計算牌組資訊
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
    // 👇 關鍵修改 1：改用 name 來尋找卡片
    const cardInDeck = deck.find(c => c.name === card.name);
    if (deckCount >= 60) return alert("牌組已滿 60 張！");

    if (card.isAceSpec) {
      const hasAceSpec = deck.some(c => c.isAceSpec);
      // 防止同一張 ACE SPEC 點第二次時誤報
      if (hasAceSpec && !cardInDeck) return alert("ACE SPEC 全牌組只能放一張！"); 
    }

    const isBasicEnergy = card.category === 'Energy' && (card.subCategory?.includes('基本') || card.name.includes('基本'));
    if (!isBasicEnergy && !card.isAceSpec) {
      if (cardInDeck && cardInDeck.count >= 4) return alert(`「${card.name}」最多只能放 4 張！`);
    }
    
    if (cardInDeck) {
      // 👇 關鍵修改 2：改用 name 來增加數量
      setDeck(deck.map(c => c.name === card.name ? { ...c, count: c.count + 1 } : c));
    } else {
      setDeck([...deck, { ...card, count: 1 }]);
    }
  };

  // 👇 關鍵修改 3：接收 cardName 作為參數
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
    try {
      const resp = await fetch('http://127.0.0.1:8000/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(deck)
      });
      setSimulationResult(await resp.json());
      setShowModal(true);
    } catch (e) { alert("連線錯誤"); }
    finally { setIsSimulating(false); }
  };

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
        
        {/* 1. 快速載入 */}
        <div className="p-4 bg-[#1e293b] border-b border-gray-800">
          <select className="w-full bg-[#0f172a] rounded-lg p-2 text-blue-400 font-bold" onChange={e => e.target.value && loadPresetDeck(e.target.value)} defaultValue="">
            <option value="" disabled>快速載入主流牌組...</option>
            {PRESET_DECKS.map((p, i) => <option key={i} value={i}>{p.name}</option>)}
          </select>
        </div>

        {/* 2. 牌組統計與進度條 */}
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

        {/* 3. 牌組清單 (含操作按鈕) */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {deck.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-600 opacity-50 space-y-2">
              <BookOpen className="w-10 h-10" />
              <p className="text-sm font-bold">牌組是空的</p>
            </div>
          ) : (
            deck.map(c => (
              <div key={c.id} className="flex items-center justify-between bg-[#1e293b] p-3 rounded-xl border border-white/5 group transition-all hover:bg-[#253248]">
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
          {isSimulating ? '發牌中...' : '開始模擬起手'}
        </button>
      </div>

      {/* 彈出視窗 */}
      {showModal && simulationResult && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-black/90 backdrop-blur-md animate-in fade-in duration-300">
          
          <div className="relative w-full max-w-5xl bg-[#0f172a] border border-blue-500/30 rounded-[40px] shadow-[0_0_80px_rgba(37,99,235,0.25)] overflow-hidden flex flex-col max-h-[90vh]">
            
            <div className="p-8 border-b border-gray-800 flex justify-between items-center bg-[#1e293b]/50 shrink-0">
              <div>
                <h2 className="text-4xl font-black text-white flex items-center gap-4">
                  <Zap className="text-yellow-400 fill-yellow-400 w-10 h-10" /> 模擬起手結果
                </h2>
                <p className="text-gray-400 mt-2 text-lg">依照 PTCG 標準規則自動洗牌與發牌</p>
              </div>
              <button 
                onClick={() => setShowModal(false)}
                className="bg-gray-800 hover:bg-gray-700 text-white p-3 rounded-full transition-colors"
              >
                <X className="w-8 h-8" />
              </button>
            </div>

            <div className="p-10 overflow-y-auto flex-1">
              <div className="grid grid-cols-1 lg:grid-cols-4 gap-10">
                
                {/* 左側資訊統計與獎賞卡 */}
                <div className="lg:col-span-1 space-y-6">
                  <div className="bg-[#020617] p-6 rounded-3xl border border-white/5 shadow-inner">
                    <p className="text-gray-500 text-xs font-black uppercase tracking-widest mb-1">Mulligan 次數</p>
                    <h3 className="text-6xl font-black text-blue-400 font-mono">
                      {simulationResult.mulliganCount}
                    </h3>
                  </div>
                  
                  <div className="bg-[#020617] p-5 rounded-3xl border border-white/5 shadow-inner">
                    <p className="text-pink-500 text-xs font-black uppercase tracking-widest mb-3 flex items-center gap-2">
                      <span className="w-1.5 h-1.5 bg-pink-500 rounded-full animate-pulse"></span>
                      獎賞卡 (Prize Cards)
                    </p>
                    <div className="grid grid-cols-3 gap-2">
                      {simulationResult.prizes.map((card, idx) => (
                        <div key={`prize-${idx}`} className="relative rounded-lg overflow-hidden shadow-md ring-1 ring-white/10 group">
                          <img 
                            src={card.image || FALLBACK_IMAGE} 
                            alt={card.name} 
                            className="w-full h-auto transition-transform duration-300 group-hover:scale-110"
                          />
                          <div className="absolute inset-x-0 bottom-0 bg-black/80 p-1 translate-y-full group-hover:translate-y-0 transition-transform duration-200">
                            <p className="text-[8px] text-white text-center font-bold truncate">{card.name}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* 右側手牌展示 (7 張單排並自動縮放) */}
                <div className="lg:col-span-3">
                  <h3 className="text-xl font-bold mb-6 text-gray-300 flex items-center gap-2">
                    <div className="w-2 h-2 bg-blue-500 rounded-full animate-ping"></div>
                    起手 7 張牌
                  </h3>
                  
                  <div className="grid grid-cols-7 gap-2 sm:gap-3 md:gap-4">
                    {simulationResult.hand.map((card, idx) => (
                      <div key={`hand-${idx}`} className="space-y-2 md:space-y-3 group">
                        <div className="relative rounded-md md:rounded-xl overflow-hidden shadow-2xl ring-1 ring-white/10 group-hover:ring-blue-500 transition-all">
                          <img 
                            src={card.image || FALLBACK_IMAGE} 
                            alt={card.name} 
                            className="w-full h-auto"
                          />
                        </div>
                        <p className="text-[10px] md:text-xs text-center text-gray-500 font-bold truncate px-1">
                          {card.name}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

              </div>
            </div>

            <div className="p-8 border-t border-gray-800 bg-[#020617] flex justify-center gap-4 shrink-0">
              <button 
                onClick={startSimulation}
                className="px-10 py-4 bg-blue-600 hover:bg-blue-500 text-white rounded-2xl font-black text-xl transition-all shadow-lg hover:shadow-blue-500/20 active:scale-95"
              >
                重新發牌
              </button>
              <button 
                onClick={() => setShowModal(false)}
                className="px-10 py-4 bg-gray-800 hover:bg-gray-700 text-white rounded-2xl font-black text-xl transition-all"
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