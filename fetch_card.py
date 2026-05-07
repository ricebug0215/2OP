const puppeteer = require('puppeteer');
const fs = require('fs');

async function scrapePTCGStandardCards() {
    console.log('啟動瀏覽器...');
    const browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();

    // 1. 進入亞洲官方繁中卡牌搜尋頁面
    await page.goto('https://asia.pokemon-card.com/tw/card-search/', { waitUntil: 'networkidle2' });

    // 2. 鎖定「標準賽」環境
    // 官方網站通常有賽制的 Checkbox，這裡需要根據實際 DOM 結構點擊
    // 假設標準賽的 input value 或 id 為對應值 (需根據網頁實際檢場元素替換 selector)
    console.log('設定標準環境過濾條件...');
    await page.waitForSelector('.search-filter-standard'); // 替換為實際的 CSS 選擇器
    await page.click('.search-filter-standard');
    
    // 點擊搜尋按鈕
    await page.click('.btn-search');
    await page.waitForNavigation({ waitUntil: 'networkidle2' });

    let allCards = [];
    let hasNextPage = true;

    // 3. 翻頁與資料提取迴圈
    while (hasNextPage) {
        console.log('正在抓取當前頁面資料...');
        
        // 提取頁面中所有的卡牌資料
        const cardsOnPage = await page.evaluate(() => {
            const cardElements = document.querySelectorAll('.card-item'); // 替換為實際卡牌的 class
            return Array.from(cardElements).map(card => {
                return {
                    name: card.querySelector('.card-name')?.innerText.trim() || '',
                    id: card.querySelector('.card-id')?.innerText.trim() || '', // 賽制標記或卡號
                    imageUrl: card.querySelector('img')?.src || '',
                    type: card.querySelector('.card-type')?.innerText.trim() || '',
                    // 可以進一步進入卡牌詳情頁抓取招式與特性，或是直接在此層級抓取
                };
            });
        });

        allCards.push(...cardsOnPage);

        // 檢查是否有下一頁的按鈕並點擊
        const nextButton = await page.$('.pagination-next:not(.disabled)'); // 替換為實際的分頁選擇器
        if (nextButton) {
            await Promise.all([
                nextButton.click(),
                page.waitForNavigation({ waitUntil: 'networkidle2' })
            ]);
        } else {
            hasNextPage = false;
        }
    }

    // 4. 將完整資料匯出成 JSON 供系統使用
    fs.writeFileSync('ptcg_standard_tw.json', JSON.stringify(allCards, null, 2), 'utf-8');
    console.log(`抓取完成！共取得 ${allCards.length} 張標準環境卡牌資料。`);

    await browser.close();
}

scrapePTCGStandardCards().catch(console.error);