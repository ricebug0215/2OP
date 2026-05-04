import sqlite3

def clean_database():
    conn = sqlite3.connect('pokemon_tcg_full.db')
    cursor = conn.cursor()

    print("🧹 開始清理非標環境卡片...")

    # 定義標準：
    # 1. 標誌必須是 H, I, J 其中之一
    # 2. 或者它是「基本能量」(subCategory 為 'Basic')，基本能量不受標誌限制
    
    # 我們刪除「既不是 HIJ」且「也不是基本能量」的卡片
    cursor.execute('''
        DELETE FROM cards 
        WHERE (regulationMark NOT IN ('H', 'I', 'J') OR regulationMark IS NULL)
        AND (subCategory != 'Basic' OR subCategory IS NULL)
    ''')

    deleted_count = conn.total_changes
    conn.commit()
    conn.close()

    print(f"✨ 清理完成！總共移除了 {deleted_count} 張過期或不符規格的卡片。")
    print("現在你的資料庫只剩下 HIJ 環境卡片與基本能量了。")

if __name__ == "__main__":
    clean_database()