"""
数据模型定义
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TodoItem(BaseModel):
    """待办事项模型"""
    id: str  # 唯一标识
    title: str  # 标题
    description: str  # 描述
    due_date: Optional[datetime] = None  # 截止时间（可选）
    created_at: datetime  # 创建时间
    source_email_id: str  # 来源邮件ID
    source_email_subject: str  # 来源邮件主题
    source_email_from: Optional[str] = None  # 来源邮件发信人
    source_email_to: Optional[str] = None  # 来源邮件收件人
    source_email_cc: Optional[str] = None  # 来源邮件抄送
    source_email_date: Optional[datetime] = None  # 来源邮件时间
    source_email_body: Optional[str] = None  # 来源邮件正文
    completed: bool = False  # 是否完成
    completed_at: Optional[datetime] = None  # 完成时间（可选）
    deleted: bool = False  # 是否已删除（软删除）
    deleted_at: Optional[datetime] = None  # 删除时间（可选）

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
