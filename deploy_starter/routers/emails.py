"""
Email API 路由
"""
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from deploy_starter.schemas import SyncEmailRequest, EmailConfigRequest
from deploy_starter.services.email_sync import (
    sync_emails_internal,
    sync_emails_with_progress,
    get_email_config,
    save_email_config,
)

router = APIRouter(prefix="/api", tags=["emails"])


@router.post("/emails/sync")
async def sync_emails(request: SyncEmailRequest):
    """同步邮箱并生成待办"""
    result = await sync_emails_internal(
        request.email_address,
        request.password,
        request.pop3_server,
        request.pop3_port
    )
    
    # 保存邮箱配置（用于自动同步）
    if "error" not in result:
        save_email_config(
            request.email_address,
            request.password,
            request.pop3_server,
            request.pop3_port,
            request.save_password,
            request.provider
        )
    
    return result


@router.get("/emails/sync-stream")
async def sync_emails_stream(
    email_address: str,
    password: str,
    pop3_server: str = "pop.gmail.com",
    pop3_port: int = 995,
    save_password: bool = False,
    days_limit: int = 7,
    provider: str = "custom"
):
    """SSE 流式同步邮箱端点，实时推送进度"""
    
    # 点击同步就立即保存邮箱配置
    save_email_config(
        email_address,
        password,
        pop3_server,
        pop3_port,
        save_password,
        provider
    )
    
    async def event_generator():
        async for progress_data in sync_emails_with_progress(
            email_address, password, pop3_server, pop3_port, days_limit
        ):
            # 发送 SSE 事件
            yield f"data: {json.dumps(progress_data, ensure_ascii=False, default=str)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/email/config")
async def save_email_config_endpoint(request: EmailConfigRequest):
    """保存邮箱配置"""
    save_email_config(
        request.email_address,
        request.password,
        request.pop3_server,
        request.pop3_port,
        request.save_password,
        request.provider
    )
    return {"success": True, "message": "配置已保存"}


@router.get("/email/config")
async def get_email_config_endpoint():
    """获取邮箱配置"""
    config = get_email_config()
    if config:
        result = {
            "email_address": config.get("email_address"),
            "pop3_server": config.get("pop3_server"),
            "pop3_port": config.get("pop3_port"),
            "save_password": config.get("save_password", False),
            "provider": config.get("provider", "custom"),
            "configured": True
        }
        # 如果用户选择了保存密码，则返回密码
        if config.get("save_password") and config.get("password"):
            result["password"] = config.get("password")
        return result
    return {"configured": False}
