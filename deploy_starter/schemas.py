"""
Pydantic 请求/响应模型定义
"""
from typing import Any
from pydantic import BaseModel


# ==================== Chat 相关模型 ====================

class ContentItem(BaseModel):
    """消息内容项"""
    type: str  # e.g.: "text", "data", etc.
    text: str | None = None  # Text content (optional)
    data: dict[str, Any] | None = None  # Data content (optional)
    status: str | None = None  # Status

    class Config:
        extra = "allow"  # Allow extra fields


class MessageItem(BaseModel):
    """消息项"""
    role: str  # e.g.: "user", "assistant"
    content: list[ContentItem] | None = None  # content array (optional)
    type: str | None = None  # Message type: message, plugin_call, plugin_call_output, etc.

    class Config:
        extra = "allow"  # Allow extra fields


class ChatRequest(BaseModel):
    """聊天请求"""
    input: list[MessageItem]  # Message array
    session_id: str  # Session ID
    stream: bool | None = True  # Whether to stream response


# ==================== Email 相关模型 ====================

class SyncEmailRequest(BaseModel):
    """同步邮箱请求"""
    email_address: str
    password: str
    pop3_server: str = "pop.gmail.com"
    pop3_port: int = 995
    save_password: bool = False
    provider: str = "custom"


class EmailConfigRequest(BaseModel):
    """邮箱配置请求"""
    email_address: str
    password: str
    pop3_server: str = "pop.gmail.com"
    pop3_port: int = 995
    save_password: bool = False
    provider: str = "custom"


# ==================== Todo 相关模型 ====================

class CompleteTodoRequest(BaseModel):
    """标记待办完成请求"""
    completed: bool


class UpdateTodoRequest(BaseModel):
    """更新待办请求"""
    title: str | None = None
    description: str | None = None
    completed: bool | None = None
    due_date: str | None = None  # ISO format datetime string


class CreateTodoRequest(BaseModel):
    """手动创建待办请求"""
    title: str  # 标题（必填）
    description: str | None = None  # 描述（可选）
    due_date: str | None = None  # 截止日期，ISO 格式 datetime 字符串（可选）


# ==================== Settings 相关模型 ====================

class ZoomRequest(BaseModel):
    """缩放设置请求"""
    zoom: float


class LLMSettingsRequest(BaseModel):
    """LLM 设置请求"""
    model: str
    base_url: str
    api_key: str = ""
    temperature: float | None = None  # 可选，不填则使用API默认值
