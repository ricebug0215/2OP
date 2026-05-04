import sqlite3
import pandas as pd
from sqlalchemy import create_engine

# 1. 讀取 SQLite 檔案
sqlite_conn = sqlite3.connect('pokemon_tcg_full.db')
df = pd.DataFrame(pd.read_sql_query("SELECT * FROM cards", sqlite_conn))
sqlite_conn.close()

# 2. 連接到 PostgreSQL (請修改成你的帳號密碼與資料庫名稱)
# 格式: postgresql://使用者名稱:密碼@localhost:5432/資料庫名稱
pg_engine = create_engine('postgresql://postgres:fuck@localhost:5433/2OP')

# 3. 直接寫入 PostgreSQL
# if_exists='replace' 表示如果表已存在就替換，'append' 則是附加
df.to_sql('cards', pg_engine, index=False, if_exists='replace')

print("資料已成功從 SQLite 搬移至 PostgreSQL！")