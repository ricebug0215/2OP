import React, { useState, useEffect } from 'react';
import { Search, Plus, Minus, Trash2, Zap, BookOpen, Play, X } from 'lucide-react';

const FALLBACK_IMAGE = 'https://placehold.co/240x336/1e293b/64748b?text=No+Image';

const FILTER_CONFIG = {
  Pokemon: [
    { label: '全部屬性', value: 'All' },
    { label: '草', value: 'Grass' }, { label: '火', value: 'Fire' },
    { label: '水', value: 'Water' }, { label: '雷', value: 'Lightning' },
    { label: '超', value: 'Psychic' }, { label: '鬥', value: 'Fighting' },
    { label: '惡', value: 'Darkness' }, { label: '鋼', value: 'Metal' },
    { label: '龍', value: 'Dragon' }, { label: '無', value: 'Colorless' }
  ],
  Trainer: [
    { label: '全部類型', value: 'All' },
    { label: '物品', value: 'Item' },
    { label: '支援者', value: 'Supporter' },
    { label: '道具', value: 'Tool' },
    { label: '競技場', value: 'Stadium' }
  ],
  Energy: [
    { label: '全部', value: 'All' },
    { label: '基本能量', value: 'Basic' },
    { label: '特殊能量', value: 'Special' }
  ]
};

// 預設常見牌組清單 (範例：多龍巴魯托)
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
      { name: "阿賽蘿拉的惡作劇", count: 1 },
      { name: "老大的指令", count: 3 },
      { name: "險惡廢墟", count: 2 },
      { name: "基本超能量", count: 3 },
      { name: "基本火能量", count: 3 },
      { name: "基本惡能量", count: 2 } // 為了測試先填滿 60 張
    ]
  },
  {
    name: "🔥 噴火龍 ex",
    cardList: [
      { name: "惡太晶噴火龍ex", count: 3 },
      { name: "火恐龍", count: 1 },
      { name: "小火龍", count: 4 },
      { name: "神奇糖果", count: 4 },
      { name: "英雄斗篷", count: 1 },
      { name: "基本火能量", count: 47 }
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

  useEffect(() => {
    setSubFilter('All');
  }, [filter]);

  useEffect(() => {
    const fetchCards = async () => {
      try {
        const url = `http://127.0.0.1:8000/api/cards?name=${searchTerm}&category=${filter}&type=${subFilter}`;
        const response = await fetch(url);
        const data = await response.json();
        setCards(data);
      } catch (error) {
        console.error("無法連線至 API 伺服器:", error);
      }
    };
    const debounce = setTimeout(fetchCards, 300);
    return () => clearTimeout(debounce);
  }, [searchTerm, filter, subFilter]);

  // 一鍵匯入預設牌組
  const loadPresetDeck = async (deckIndex) => {
    if (deck.length > 0) {
      const confirmOverwrite = window.confirm("匯入新牌組將會清空您目前的牌組，確定要繼續嗎？");
      if (!confirmOverwrite) return;
    }
    
    setIsSimulating(true); 
    const selectedList = PRESET_DECKS[deckIndex].cardList;
    
    try {
      const response = await fetch('http://127.0.0.1:8000/api/import-deck', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(selectedList)
      });
      
      if (!response.ok) throw new Error("匯入請求失敗");
      
      const result = await response.json();
      const fullDeckCards = result.deck; // 拿取牌組
      const notFoundList = result.notFound; // 拿取找不到的牌
      
      // 如果有牌找不到，明確彈出視窗告訴你缺了誰！
      if (notFoundList.length > 0) {
        alert(`匯入完成，但以下卡片在資料庫中找不到：\n\n${notFoundList.join(', ')}\n\n請檢查 PRESET_DECKS 中的名稱是否正確。`);
      }
      
      setDeck(fullDeckCards);
    } catch (error) {
      console.error("匯入失敗:", error);
      alert("無法連線到資料庫匯入卡片，請確認 server.py 正在運行。");
    } finally {
      setIsSimulating(false);
    }
  };

  const addToDeck = (card) => {
    const cardInDeck = deck.find(c => c.id === card.id);
    const totalCount = deck.reduce((sum, c) => sum + c.count, 0);
    if (totalCount >= 60) {
      alert("牌組已滿 60 張！");
      return;
    }
    if (card.is_ace_spec) {
      const hasAceSpec = deck.some(c => c.is_ace_spec);
      if (hasAceSpec) {
        alert("王牌特種 (ACE SPEC) 全牌組只能放一張！");
        return;
      }
    }
    const isBasicEnergy = card.category === 'Energy' && (card.subCategory === 'Basic' || card.name.includes('基本'));
    if (!isBasicEnergy && !card.is_ace_spec) {
      if (cardInDeck && cardInDeck.count >= 4) {
        alert(`「${card.name}」在牌組中最多只能放 4 張！`);
        return;
      }
    }
    if (cardInDeck) {
      setDeck(deck.map(c => c.id === card.id ? { ...c, count: c.count + 1 } : c));
    } else {
      setDeck([...deck, { ...card, count: 1 }]);
    }
  };

  const removeFromDeck = (cardId) => {
    const cardInDeck = deck.find(c => c.id === cardId);
    if (!cardInDeck) return;
    if (cardInDeck.count > 1) {
      setDeck(deck.map(c => c.id === cardId ? { ...c, count: c.count - 1 } : c));
    } else {
      setDeck(deck.filter(c => c.id !== cardId));
    }
  };

  const startSimulation = async () => {
    if (deckCount !== 60) return;
    setIsSimulating(true);
    
    try {
      const response = await fetch('http://127.0.0.1:8000/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(deck)
      });
      const data = await response.json();
      setSimulationResult(data);
      setShowModal(true);
    } catch (error) {
      console.error("模擬失敗:", error);
      alert("無法連線到伺服器，請確認 server.py 正在運行。");
    } finally {
      setIsSimulating(false);
    }
  };

  const deckCount = deck.reduce((sum, c) => sum + c.count, 0);

  return (
    <div className="flex h-screen w-screen bg-[#020617] text-white font-sans overflow-hidden">
      
      {/* 左側：卡廊區 */}
      <div className="flex-1 flex flex-col border-r border-gray-800">
        <div className="p-6 bg-[#0f172a] shadow-xl space-y-4 z-20">
          <h1 className="text-2xl font-black flex items-center gap-3 tracking-tight">
            <Zap className="text-yellow-400 fill-yellow-400" /> PTCG 先二展開器
          </h1>
          
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-3 text-gray-400 w-5 h-5" />
              <input 
                type="text" 
                placeholder="搜尋卡片名稱..." 
                className="w-full bg-[#1e293b] border border-gray-700 rounded-xl py-2.5 pl-10 pr-4 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <select 
              className="bg-[#1e293b] border border-gray-700 rounded-xl px-4 py-2 focus:outline-none"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              <option value="All">全部類別</option>
              <option value="Pokemon">寶可夢</option>
              <option value="Trainer">訓練家</option>
              <option value="Energy">能量</option>
            </select>
          </div>

          {/* 動態子篩選列 */}
          {FILTER_CONFIG[filter] && (
            <div className="flex flex-wrap gap-2 pt-2">
              {FILTER_CONFIG[filter].map((item) => (
                <button
                  key={item.value}
                  onClick={() => setSubFilter(item.value)}
                  className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all border ${
                    subFilter === item.value
                      ? 'bg-blue-600 border-blue-400 shadow-[0_0_10px_rgba(37,99,235,0.4)]'
                      : 'bg-[#1e293b] border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 卡片網格 */}
        <div className="flex-1 overflow-y-auto p-8 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-8 bg-[#020617]">
          {cards.map(card => (
            <div 
              key={card.id} 
              className={`group relative transition-all duration-300 hover:-translate-y-2 cursor-pointer ${card.is_ace_spec ? 'scale-105 z-10' : ''}`} 
              onClick={() => addToDeck(card)}
            >
              <div className={`relative rounded-2xl overflow-hidden shadow-2xl transition-all ${
                card.is_ace_spec 
                  ? 'ring-4 ring-pink-500 shadow-[0_0_20px_rgba(236,72,153,0.6)]' 
                  : 'ring-1 ring-white/10 group-hover:ring-blue-500/50'
              }`}>
                <img 
                  src={card.image ? card.image.replace('high.webp', 'low.webp') : FALLBACK_IMAGE} 
                  alt={card.name} 
                  loading="lazy"
                  onError={(e) => { e.target.onerror = null; e.target.src = FALLBACK_IMAGE; }}
                  className="w-full h-auto block bg-gray-800 min-h-[200px]" 
                />
                <div className="absolute inset-0 bg-blue-600/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity backdrop-blur-[2px]">
                  <div className="bg-white text-blue-600 rounded-full p-2"><Plus className="w-8 h-8 stroke-[3px]" /></div>
                </div>
              </div>
              <p className={`mt-3 text-sm font-bold text-center ${card.is_ace_spec ? 'text-pink-400' : 'text-gray-400 group-hover:text-white'}`}>
                {card.name}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* 右側：牌組清單區 */}
      <div className="w-96 bg-[#0f172a] flex flex-col shadow-2xl z-30">
        
        {/* 快速匯入區塊 */}
        <div className="p-4 border-b border-gray-800 bg-[#1e293b]">
          <label className="text-xs font-bold text-gray-400 mb-2 block uppercase tracking-wider">
            快速匯入主流牌組
          </label>
          <select
            className="w-full bg-[#0f172a] border border-blue-500/30 rounded-xl px-4 py-2.5 text-sm font-bold text-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer appearance-none transition-all hover:border-blue-500/60"
            onChange={(e) => {
              if (e.target.value !== "") {
                loadPresetDeck(e.target.value);
                e.target.value = "";
              }
            }}
            defaultValue=""
          >
            <option value="" disabled className="text-gray-500">選擇你想測試的牌組...</option>
            {PRESET_DECKS.map((preset, idx) => (
              <option key={idx} value={idx} className="text-white">
                {preset.name}
              </option>
            ))}
          </select>
        </div>

        <div className="p-6 border-b border-gray-800">
          <div className="flex justify-between items-end mb-4">
            <h2 className="text-xl font-bold">目前牌組</h2>
            <span className={`text-sm font-mono font-bold ${deckCount === 60 ? 'text-green-400' : 'text-blue-400'}`}>
              {deckCount} / 60
            </span>
          </div>
          <div className="w-full bg-gray-800 h-2.5 rounded-full overflow-hidden">
            <div className={`h-full transition-all duration-500 ${deckCount === 60 ? 'bg-green-500' : 'bg-blue-500'}`} style={{ width: `${(deckCount/60)*100}%` }}></div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {deck.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500 opacity-50"><BookOpen className="w-12 h-12 mb-2" /><p>尚未加入卡片</p></div>
          ) : (
            deck.map(card => (
              <div key={card.id} className="flex items-center justify-between bg-[#1e293b] p-3 rounded-xl border border-white/5 group hover:bg-[#253248] transition-all">
                <span className={`flex-1 truncate text-sm font-semibold ${card.is_ace_spec ? 'text-pink-400' : 'text-gray-200'}`}>{card.name}</span>
                <div className="flex items-center gap-3">
                  <div className="flex items-center bg-gray-900/50 p-1 rounded-lg border border-white/5">
                    <button onClick={() => removeFromDeck(card.id)} className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-gray-700"><Minus className="w-3.5 h-3.5" /></button>
                    <span className="w-8 text-center text-sm font-black text-blue-400">{card.count}</span>
                    <button onClick={() => addToDeck(card)} className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-gray-700"><Plus className="w-3.5 h-3.5" /></button>
                  </div>
                  <button onClick={() => setDeck(deck.filter(c => c.id !== card.id))} className="opacity-0 group-hover:opacity-100 w-8 h-8 flex items-center justify-center text-gray-500 hover:text-red-500 hover:bg-red-500/10 rounded-lg transition-all"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="p-6 bg-[#020617] border-t border-gray-800">
          <button 
            onClick={startSimulation}
            disabled={deckCount < 60 || isSimulating}
            className={`w-full py-4 rounded-2xl font-black text-lg transition-all shadow-lg flex justify-center items-center gap-2 ${
              deckCount === 60 ? 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:scale-[1.02]' : 'bg-gray-800 text-gray-600 cursor-not-allowed'
            }`}
          >
            {isSimulating ? '發牌中...' : '模擬起手與獎賞卡'}
          </button>
        </div>
      </div>

      {/* --- 彈出式對話筐 (Simulation Modal) --- */}
      {showModal && simulationResult && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-black/90 backdrop-blur-md animate-in fade-in duration-300">
          
          <div className="relative w-full max-w-5xl bg-[#0f172a] border border-blue-500/30 rounded-[40px] shadow-[0_0_80px_rgba(37,99,235,0.25)] overflow-hidden flex flex-col">
            
            <div className="p-8 border-b border-gray-800 flex justify-between items-center bg-[#1e293b]/50">
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

            <div className="p-10 flex-1">
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
                        <div key={`prize-${card.id}-${idx}`} className="relative rounded-lg overflow-hidden shadow-md ring-1 ring-white/10 group">
                          <img 
                            src={card.image ? card.image.replace('high.webp', 'low.webp') : FALLBACK_IMAGE} 
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
                      <div key={`${card.id}-${idx}`} className="space-y-2 md:space-y-3 group">
                        <div className="relative rounded-md md:rounded-xl overflow-hidden shadow-2xl ring-1 ring-white/10 group-hover:ring-blue-500 transition-all">
                          <img 
                            src={card.image ? card.image.replace('high.webp', 'low.webp') : FALLBACK_IMAGE} 
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

            <div className="p-8 border-t border-gray-800 bg-[#020617] flex justify-center gap-4">
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