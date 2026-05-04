import React, { useState, useEffect } from 'react';
import { Search, Plus, Minus, Trash2, Zap, BookOpen } from 'lucide-react';
// 放在 import 下方，FILTER_CONFIG 的上方
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
  ]
};

export default function App() {
  // 存放從 Python 後端拿到的真實卡牌資料
  const [cards, setCards] = useState([]); 
  const [searchTerm, setSearchTerm] = useState('');
  const [filter, setFilter] = useState('All');
  const [subFilter, setSubFilter] = useState('All');
  const [deck, setDeck] = useState([]);

  // 當主分類切換時，子分類歸零
  useEffect(() => {
    setSubFilter('All');
  }, [filter]);

  // 核心：每次搜尋條件改變，就去問 Python 後端拿資料
  useEffect(() => {
    const fetchCards = async () => {
      try {
        const url = `http://127.0.0.1:8000/api/cards?name=${searchTerm}&category=${filter}&type=${subFilter}`;
        const response = await fetch(url);
        const data = await response.json();
        setCards(data); // 將拿到的資料存入 cards
      } catch (error) {
        console.error("無法連接到 Python 後端:", error);
      }
    };

    // 加入 300 毫秒的延遲 (Debounce)，避免打字太快讓後端當機
    const timeoutId = setTimeout(fetchCards, 300);
    return () => clearTimeout(timeoutId);
  }, [searchTerm, filter, subFilter]);

  // 牌組控制邏輯
  const addToDeck = (card) => {
    const cardInDeck = deck.find(c => c.id === card.id);
    const total = deck.reduce((sum, c) => sum + c.count, 0);
    if (total >= 60) return;
    if (card.category !== 'Energy' && cardInDeck?.count >= 4) return;
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
    <div className="flex h-screen w-screen bg-[#020617] text-white overflow-hidden">
      {/* 左側卡廊 */}
      <div className="flex-1 flex flex-col border-r border-gray-800">
        <div className="p-6 bg-[#0f172a] space-y-4 shadow-xl">
          <h1 className="text-2xl font-black flex items-center gap-2"><Zap className="text-yellow-400 fill-yellow-400" /> PTCG 先二展開器</h1>
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-3 w-5 h-5 text-gray-500" />
              <input 
                className="w-full bg-[#1e293b] border border-gray-700 rounded-xl py-2 pl-10 pr-4 outline-none focus:ring-2 focus:ring-blue-500" 
                placeholder="搜尋卡片..." 
                value={searchTerm} 
                onChange={e => setSearchTerm(e.target.value)} 
              />
            </div>
            <select className="bg-[#1e293b] border border-gray-700 rounded-xl px-4" value={filter} onChange={e => setFilter(e.target.value)}>
              <option value="All">全部</option>
              <option value="Pokemon">寶可夢</option>
              <option value="Trainer">訓練家</option>
              <option value="Energy">能量</option>
            </select>
          </div>
          {(filter === 'Pokemon' || filter === 'Trainer') && (
            <div className="flex flex-wrap gap-2 pt-2">
              {FILTER_CONFIG[filter].map(item => (
                <button 
                  key={item.value} 
                  onClick={() => setSubFilter(item.value)} 
                  className={`px-3 py-1 rounded-full text-xs font-bold border transition-all ${subFilter === item.value ? 'bg-blue-600 border-blue-400 shadow-[0_0_10px_rgba(37,99,235,0.4)]' : 'bg-[#1e293b] border-gray-700 text-gray-400 hover:text-gray-200'}`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
        </div>
        
        {/* 卡片顯示區：將原本的 filteredCards 改成從後端拿到的 cards */}
        <div className="flex-1 overflow-y-auto p-8 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6">
          {cards.map(card => (
            <div key={card.id} className="group cursor-pointer transition-transform hover:-translate-y-1" onClick={() => addToDeck(card)}>
              <div className="relative rounded-xl overflow-hidden shadow-lg ring-1 ring-white/10 group-hover:ring-blue-500">
                {/* 這裡的 card.image 是後端幫我們轉好的 image_url */}
                <img 
                  // 1. 先安全檢查：如果 card.image 存在才做 replace，否則直接用備用圖
                  src={card.image ? card.image.replace('high.webp', 'low.webp') : FALLBACK_IMAGE} 
                  alt={card.name} 
                  loading="lazy"
                  className="w-full h-auto block" 
                  // 2. 錯誤捕捉：如果網址存在但圖片載入失敗(破圖)，立刻替換成備用圖
                  onError={(e) => {
                    e.target.onerror = null; // 防止無限迴圈
                    e.target.src = FALLBACK_IMAGE;
                  }}
                />
                <div className="absolute inset-0 bg-blue-600/20 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity backdrop-blur-[2px]">
                  <Plus className="bg-white text-blue-600 rounded-full p-2 w-10 h-10 shadow-lg" />
                </div>
              </div>
              <p className="mt-2 text-xs text-center text-gray-400 group-hover:text-white">{card.name}</p>
            </div>
          ))}
          {/* 如果後端沒傳資料回來，顯示提示 */}
          {cards.length === 0 && (
            <div className="col-span-full text-center text-gray-500 mt-20">沒有找到符合條件的卡片</div>
          )}
        </div>
      </div>

      {/* 右側清單 (維持你喜歡的排版) */}
      <div className="w-96 bg-[#0f172a] flex flex-col shadow-2xl">
        <div className="p-6 border-b border-gray-800">
          <div className="flex justify-between items-end mb-4 font-bold">
            <span className="text-xl">目前牌組</span>
            <span className={`font-mono ${deckCount === 60 ? 'text-green-400' : 'text-blue-400'}`}>{deckCount} / 60</span>
          </div>
          <div className="w-full bg-gray-800 h-2.5 rounded-full overflow-hidden">
            <div className={`h-full transition-all duration-500 ${deckCount === 60 ? 'bg-green-500' : 'bg-blue-500'}`} style={{ width: `${(deckCount/60)*100}%` }}></div>
          </div>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {deck.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-600 opacity-50"><BookOpen className="w-12 h-12 mb-2" /><p>尚未加入卡片</p></div>
          ) : (
            deck.map(card => (
              <div key={card.id} className="flex items-center justify-between bg-[#1e293b] p-3 rounded-xl group border border-white/5 hover:bg-[#253248] transition-colors">
                <span className="flex-1 truncate text-sm font-semibold text-gray-200">{card.name}</span>
                <div className="flex items-center gap-3">
                  <div className="flex items-center bg-gray-900/50 rounded-lg p-1 border border-white/5">
                    <button onClick={() => removeFromDeck(card.id)} className="w-7 h-7 flex items-center justify-center hover:bg-gray-700 rounded-md transition-colors"><Minus className="w-3.5 h-3.5" /></button>
                    <span className="w-8 text-center text-sm font-black text-blue-400">{card.count}</span>
                    <button onClick={() => addToDeck(card)} className="w-7 h-7 flex items-center justify-center hover:bg-gray-700 rounded-md transition-colors"><Plus className="w-3.5 h-3.5" /></button>
                  </div>
                  <button onClick={() => setDeck(deck.filter(c => c.id !== card.id))} className="opacity-0 group-hover:opacity-100 p-2 text-gray-500 hover:text-red-500 hover:bg-red-500/10 rounded-lg transition-all"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
            ))
          )}
        </div>
        
        <div className="p-6 bg-[#020617]/50 border-t border-gray-800">
          <button disabled={deckCount < 60} className={`w-full py-4 rounded-2xl font-black text-lg transition-all shadow-lg ${deckCount === 60 ? 'bg-gradient-to-r from-green-600 to-emerald-600 hover:scale-[1.02] active:scale-[0.98]' : 'bg-gray-800 text-gray-600 cursor-not-allowed'}`}>
            {deckCount === 60 ? '開始模擬展開' : `還差 ${60 - deckCount} 張卡片`}
          </button>
        </div>
      </div>
    </div>
  );
}