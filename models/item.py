from typing import Optional
from pydantic import BaseModel

# 1. 생성(POST) 요청 데이터
class ItemCreate(BaseModel):
    title: str
    description: Optional[str] = None

# 2. 수정(PUT) 요청 데이터 (모든 필드는 선택 사항)
class ItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

# 3. 응답(Response) 데이터
class ItemResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None