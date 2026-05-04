import React, { useState, useEffect } from 'react';
import { Search, Plus, Minus, Trash2, Zap, BookOpen } from 'lucide-react';

// 備用圖片：當資料庫沒圖或是破圖時顯示
const FALLBACK_IMAGE = 'https://placehold.co/240x336/1e293b/64748b?text=No+Image';

// 篩選器配置 (已加入能量的子選單)
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

export default function App() {
  const [cards, setCards] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [filter, setFilter] = useState('All');
  const [subFilter, setSubFilter] = useState('All');
  const [deck, setDeck] = useState([]);

  // 當主分類切換時，自動重設子篩選
  useEffect(() => {
    setSubFilter('All');
  }, [filter]);

  // 從 Python 後端抓取卡片資料
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

  // 加入牌組核心邏輯
  const addToDeck = (card) => {
    const cardInDeck = deck.find(c => c.id === card.id);
    const totalCount = deck.reduce((sum, c) => sum + c.count, 0);

    if (totalCount >= 60) {
      alert("牌組已滿 60 張！");
      return;
    }

    // 1. ACE SPEC 判定 (全牌組限一張)
    if (card.is_ace_spec) {
      const hasAceSpec = deck.some(c => c.is_ace_spec);
      if (hasAceSpec) {
        alert("王牌特種 (ACE SPEC) 全牌組只能放一張！");
        return;
      }
    }

    // 2. 數量限制判定 (基本能量無限，其餘最多 4 張)
    const isBasicEnergy = card.category === 'Energy' && (card.subCategory === 'Basic' || card.name.includes('基本'));
    
    if (!isBasicEnergy && !card.is_ace_spec) {
      if (cardInDeck && cardInDeck.count >= 4) {
        alert(`「${card.name}」在牌組中最多只能放 4 張！`);
        return;
      }
    }

    // 3. 執行加入
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

  const deckCount = deck.reduce((sum, c) => sum + c.count, 0);

  return (
    <div className="flex h-screen w-screen bg-[#020617] text-white font-sans overflow-hidden">
      
      {/* 左側：卡廊區 */}
      <div className="flex-1 flex flex-col border-r border-gray-800">
        <div className="p-6 bg-[#0f172a] shadow-xl space-y-4">
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
            <div className="flex flex-wrap gap-2 pt-2 animate-in fade-in slide-in-from-top-2 duration-300">
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

        {/* 卡片網格：渲染與特效 (已移除閃爍特效) */}
        <div className="flex-1 overflow-y-auto p-8 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-8 bg-[#020617]">
          {cards.map(card => (
            <div 
              key={card.id} 
              // 如果是 ACE SPEC，卡片會稍微放大一點點
              className={`group relative transition-all duration-300 hover:-translate-y-2 cursor-pointer ${card.is_ace_spec ? 'scale-105 z-10' : ''}`} 
              onClick={() => addToDeck(card)}
            >
              {/* 如果是 ACE SPEC，加上粉紅色靜態邊框與光暈 (已移除 animate-pulse) */}
              <div className={`relative rounded-2xl overflow-hidden shadow-2xl transition-all ${
                card.is_ace_spec 
                  ? 'ring-4 ring-pink-500 shadow-[0_0_20px_rgba(236,72,153,0.6)]' // animate-pulse REMOVED here
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
              {/* 如果是 ACE SPEC，字體也變成粉紅色 */}
              <p className={`mt-3 text-sm font-bold text-center ${card.is_ace_spec ? 'text-pink-400' : 'text-gray-400 group-hover:text-white'}`}>
                {card.name}
              </p>
            </div>
          ))}
          
          {cards.length === 0 && (
            <div className="col-span-full text-center text-gray-500 mt-20 font-bold">
              沒有找到符合條件的卡片
            </div>
          )}
        </div>
      </div>

      {/* 右側：牌組清單區 */}
      <div className="w-96 bg-[#0f172a] flex flex-col shadow-2xl">
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
            <div className="flex flex-col items-center justify-center h-full text-gray-500 opacity-50">
              <BookOpen className="w-12 h-12 mb-2" />
              <p>尚未加入卡片</p>
            </div>
          ) : (
            deck.map(card => (
              <div key={card.id} className="flex items-center justify-between bg-[#1e293b] p-3 rounded-xl border border-white/5 group hover:bg-[#253248] transition-all">
                <span className={`flex-1 truncate text-sm font-semibold ${card.is_ace_spec ? 'text-pink-400' : 'text-gray-200'}`}>
                  {card.name}
                </span>
                <div className="flex items-center gap-3">
                  <div className="flex items-center bg-gray-900/50 p-1 rounded-lg border border-white/5">
                    <button onClick={() => removeFromDeck(card.id)} className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-gray-700 transition-colors"><Minus className="w-3.5 h-3.5" /></button>
                    <span className="w-8 text-center text-sm font-black text-blue-400">{card.count}</span>
                    <button onClick={() => addToDeck(card)} className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-gray-700 transition-colors"><Plus className="w-3.5 h-3.5" /></button>
                  </div>
                  <button onClick={() => setDeck(deck.filter(c => c.id !== card.id))} className="opacity-0 group-hover:opacity-100 w-8 h-8 flex items-center justify-center text-gray-500 hover:text-red-500 hover:bg-red-500/10 rounded-lg transition-all"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="p-6 bg-[#020617]/50 border-t border-gray-800">
          <button 
            disabled={deckCount < 60}
            className={`w-full py-4 rounded-2xl font-black text-lg transition-all shadow-lg ${
              deckCount === 60 
                ? 'bg-gradient-to-r from-green-600 to-emerald-600 hover:scale-[1.02] active:scale-[0.98]' 
                : 'bg-gray-800 text-gray-600 cursor-not-allowed'
            }`}
          >
            {deckCount === 60 ? '開始模擬展開' : `還差 ${60 - deckCount} 張卡片`}
          </button>
        </div>
      </div>
    </div>
  );
}