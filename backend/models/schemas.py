from pydantic import BaseModel, Field
from typing import Optional, List


class ChatRequest(BaseModel):
    session_id: str
    message: str


class GuestChatRequest(BaseModel):
    message: str


class SessionCreate(BaseModel):
    title: Optional[str] = "新对话"


class SessionRename(BaseModel):
    title: str = Field(..., min_length=1, max_length=50)


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    display_name: Optional[str] = ""


class UserLogin(BaseModel):
    username: str
    password: str