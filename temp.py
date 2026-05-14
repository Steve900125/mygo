import os
import sys
import psycopg
from dotenv import load_dotenv

load_dotenv()

CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": int(os.getenv("POSTGRES_PORT", "5433")),
    "user": os.getenv("AUTH_DB_USER", "admin"),
    "password": os.getenv("AUTH_DB_PASSWORD", "changeme"),
    "dbname": os.getenv("AUTH_DB_NAME")
}


def test_connection():
    print(f"連線到 {CONFIG['host']}:{CONFIG['port']} (db={CONFIG['dbname']}, user={CONFIG['user']})")
    try:
        with psycopg.connect(**CONFIG, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                # 1. 基本連線測試
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                print(f"✅ 連線成功\n   版本: {version}")

                # 2. 當前資料庫與使用者
                cur.execute("SELECT current_database(), current_user, now();")
                db, user, now = cur.fetchone()
                print(f"   DB: {db} | User: {user} | Time: {now}")

                # 3. 列出所有 schema 中的資料表
                cur.execute("""
                    SELECT table_schema, table_name
                    FROM information_schema.tables
                    WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY table_schema, table_name;
                """)
                tables = cur.fetchall()
                if tables:
                    print(f"   找到 {len(tables)} 張資料表:")
                    for schema, name in tables:
                        print(f"     - {schema}.{name}")
                else:
                    print("   (尚無使用者資料表)")
        return True

    except psycopg.OperationalError as e:
        print(f"❌ 連線失敗: {e}")
        return False
    except Exception as e:
        print(f"❌ 發生錯誤: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    sys.exit(0 if test_connection() else 1)