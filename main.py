import os
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI
from dotenv import load_dotenv

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


from models import ItemCreate, ItemUpdate, ItemResponse




# .env 환경변수 로드
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL이 설정되지 않았습니다.")

# 비동기 커넥션 풀 전역 변수
pool: Optional[AsyncConnectionPool] = None

# FastAPI 시작/종료 시 커넥션 풀 관리
@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    # 서버 시작 시 커넥션 풀 초기화
    pool = AsyncConnectionPool(
        conninfo=DATABASE_URL,
        open=False,
        min_size=1,
        max_size=10
    )
    await pool.open()
    print("PostgreSQL Connection Pool이 연결되었습니다.")
    
    yield
    
    # 서버 종료 시 커넥션 풀 닫기
    await pool.close()
    print("PostgreSQL Connection Pool이 종료되었습니다.")

app = FastAPI(title="FastAPI + Psycopg3 CRUD", lifespan=lifespan)


from fastapi import HTTPException, status

# 1. CREATE (POST) - 새 아이템 생성
@app.post("/items/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(item: ItemCreate):
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            # SQL 실행 및 RETURNING을 통한 생성 데이터 반환
            await cur.execute(
                """
                INSERT INTO items (title, description)
                VALUES (%s, %s)
                RETURNING id, title, description;
                """,
                (item.title, item.description)
            )
            new_item = await cur.fetchone()
            
            # 트랜잭션 커밋 (DB에 실질 저장)
            await conn.commit()
            
            if not new_item:
                raise HTTPException(status_code=400, detail="아이템 생성에 실패했습니다.")
                
            return new_item


from typing import List

# 2. READ ALL (GET) - 전체 아이템 목록 조회
@app.get("/items/", response_model=List[ItemResponse])
async def read_items():
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT id, title, description FROM items ORDER BY id ASC;"
            )
            items = await cur.fetchall()
            return items


# 3. READ ONE BY ID (GET) - 특정 아이템 단일 조회
@app.get("/items/{item_id}", response_model=ItemResponse)
async def read_item(item_id: int):
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT id, title, description FROM items WHERE id = %s;",
                (item_id,)
            )
            item = await cur.fetchone()
            
            # 조회가 되지 않으면 404 에러 반환
            if not item:
                raise HTTPException(status_code=404, detail="아이템을 찾을 수 없습니다.")
                
            return item


# 4. UPDATE (PUT) - 아이템 수정
@app.put("/items/{item_id}", response_model=ItemResponse)
async def update_item(item_id: int, item: ItemUpdate):
    # None이 아닌(값이 전달된) 필드만 추출
    update_data = {k: v for k, v in item.model_dump().items() if v is not None}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="수정할 데이터가 전달되지 않았습니다.")

    # 동적 SET 구문 생성 (예: "title = %s, description = %s")
    set_clause = ", ".join([f"{key} = %s" for key in update_data.keys()])
    values = list(update_data.values())
    values.append(item_id)  # WHERE 절의 %s에 들어갈 item_id 추가

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            query = f"""
                UPDATE items
                SET {set_clause}
                WHERE id = %s
                RETURNING id, title, description;
            """
            await cur.execute(query, values)
            updated_item = await cur.fetchone()
            
            if not updated_item:
                raise HTTPException(status_code=404, detail="수정할 아이템을 찾을 수 없습니다.")
                
            await conn.commit()
            return updated_item


# 5. DELETE (DELETE) - 아이템 삭제
@app.delete("/items/{item_id}")
async def delete_item(item_id: int):
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "DELETE FROM items WHERE id = %s RETURNING id;",
                (item_id,)
            )
            deleted_item = await cur.fetchone()
            
            if not deleted_item:
                raise HTTPException(status_code=404, detail="삭제할 아이템을 찾지 못했습니다.")
                
            await conn.commit()
            return {"message": f"ID {item_id} 아이템이 성공적으로 삭제되었습니다."}