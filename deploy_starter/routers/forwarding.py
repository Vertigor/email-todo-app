"""
Forwarding API 路由
邮件转发规则管理和SMTP配置
"""
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from deploy_starter.database import Database
from deploy_starter.schemas import LLMSettingsRequest
from deploy_starter.utils import get_db_path
from deploy_starter.services.email_forward import (
    get_smtp_config,
    get_effective_smtp_config,
    save_smtp_config,
    forward_email,
    load_raw_email,
)

router = APIRouter(prefix="/api", tags=["forwarding"])
db = Database(get_db_path())


# ==================== Pydantic Models ====================

class SmtpConfigRequest(BaseModel):
    """SMTP配置请求"""
    smtp_server: str
    smtp_port: int = 465
    smtp_ssl: bool = True
    email_address: str
    password: str = ""
    sender_name: str = "邮箱待办助手"


class ForwardRuleRequest(BaseModel):
    """转发规则请求"""
    description: str
    recipients: list[str]
    enabled: bool = True
    also_create_todo: bool = False


class ForwardRuleUpdateRequest(BaseModel):
    """转发规则更新请求"""
    description: str | None = None
    recipients: list[str] | None = None
    enabled: bool | None = None
    also_create_todo: bool | None = None


class ManualForwardRequest(BaseModel):
    """手动转发请求"""
    email_id: str
    rule_id: str


# ==================== SMTP 配置 ====================

@router.get("/settings/smtp")
async def get_smtp_config_endpoint():
    """获取SMTP配置（缺失时回退到收件邮箱推导）"""
    saved = get_smtp_config()
    effective = get_effective_smtp_config()
    has_explicit_smtp = bool(saved.get("smtp_server") and saved.get("email_address") and saved.get("password"))
    # 不返回密码明文
    return {
        "smtp_server": effective.get("smtp_server", ""),
        "smtp_port": effective.get("smtp_port", 465),
        "smtp_ssl": effective.get("smtp_ssl", True),
        "email_address": effective.get("email_address", ""),
        "sender_name": effective.get("sender_name", "邮箱待办助手"),
        "configured": bool(effective.get("smtp_server") and effective.get("email_address") and effective.get("password")),
        "has_password": bool(effective.get("password")),
        "from_receive_config": (not has_explicit_smtp) and bool(effective.get("smtp_server"))
    }


@router.post("/settings/smtp")
async def save_smtp_config_endpoint(request: SmtpConfigRequest):
    """保存SMTP配置"""
    if not request.smtp_server:
        raise HTTPException(status_code=400, detail="SMTP服务器不能为空")
    if not request.email_address:
        raise HTTPException(status_code=400, detail="发件邮箱地址不能为空")
    
    result = save_smtp_config(
        smtp_server=request.smtp_server,
        smtp_port=request.smtp_port,
        smtp_ssl=request.smtp_ssl,
        email_address=request.email_address,
        password=request.password,
        sender_name=request.sender_name
    )
    
    if result.get("success"):
        return {"success": True, "message": "SMTP配置已保存"}
    else:
        raise HTTPException(status_code=500, detail=result.get("error", "保存失败"))


# ==================== 转发规则 CRUD ====================

@router.get("/forward/rules")
async def get_forward_rules():
    """获取所有转发规则"""
    rules = db.get_forward_rules()
    return {"rules": rules}


@router.post("/forward/rules")
async def create_forward_rule(request: ForwardRuleRequest):
    """创建转发规则"""
    if not request.description:
        raise HTTPException(status_code=400, detail="规则描述不能为空")
    if not request.recipients:
        raise HTTPException(status_code=400, detail="收件人不能为空")
    
    # 验证邮箱格式
    for recipient in request.recipients:
        if "@" not in recipient:
            raise HTTPException(status_code=400, detail=f"无效的邮箱地址: {recipient}")
    
    rule_id = str(uuid.uuid4())
    success = db.add_forward_rule(
        rule_id=rule_id,
        description=request.description,
        recipients=request.recipients,
        enabled=request.enabled,
        also_create_todo=request.also_create_todo
    )
    
    if success:
        rule = db.get_forward_rule(rule_id)
        return {"success": True, "rule": rule}
    else:
        raise HTTPException(status_code=500, detail="创建转发规则失败")


@router.put("/forward/rules/{rule_id}")
async def update_forward_rule(rule_id: str, request: ForwardRuleUpdateRequest):
    """更新转发规则"""
    # 验证规则存在
    rule = db.get_forward_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="转发规则不存在")
    
    # 验证邮箱格式
    if request.recipients:
        for recipient in request.recipients:
            if "@" not in recipient:
                raise HTTPException(status_code=400, detail=f"无效的邮箱地址: {recipient}")
    
    success = db.update_forward_rule(
        rule_id=rule_id,
        description=request.description,
        recipients=request.recipients,
        enabled=request.enabled,
        also_create_todo=request.also_create_todo
    )
    
    if success:
        updated_rule = db.get_forward_rule(rule_id)
        return {"success": True, "rule": updated_rule}
    else:
        raise HTTPException(status_code=500, detail="更新转发规则失败")


@router.delete("/forward/rules/{rule_id}")
async def delete_forward_rule(rule_id: str):
    """删除转发规则"""
    success = db.delete_forward_rule(rule_id)
    if success:
        return {"success": True, "message": "转发规则已删除"}
    else:
        raise HTTPException(status_code=404, detail="转发规则不存在")


# ==================== 手动转发 ====================

@router.post("/forward/manual")
async def manual_forward_email(request: ManualForwardRequest):
    """手动转发邮件（从待办详情中触发）"""
    rule = db.get_forward_rule(request.rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="转发规则不存在")
    
    # 获取待办事项对应的邮件信息
    todo = db.get_todo_by_id(request.email_id)
    if not todo:
        raise HTTPException(status_code=404, detail="待办事项不存在")
    
    # 检查是否已经转发过
    email_id = todo.source_email_id
    if db.is_email_forwarded(email_id, request.rule_id):
        raise HTTPException(status_code=400, detail="该邮件已转发过")
    
    # 取原始邮件字节，实现原样转发（含附件/HTML/内嵌图片）；旧待办无原文时回退纯文本
    original_raw = load_raw_email(email_id)

    result = forward_email(
        original_subject=todo.source_email_subject or "(无主题)",
        original_from=todo.source_email_from or "(未知)",
        original_date=todo.source_email_date.isoformat() if todo.source_email_date else "",
        original_body=todo.source_email_body or "",
        recipients=rule["recipients"],
        rule_description=rule["description"],
        original_raw=original_raw,
    )
    
    if result.get("success"):
        db.mark_email_forwarded(
            email_id=email_id,
            rule_id=request.rule_id,
            recipients=rule["recipients"],
            subject=todo.source_email_subject or "",
            from_addr=todo.source_email_from or "",
            original_date=todo.source_email_date.isoformat() if todo.source_email_date else "",
            body_preview=(todo.source_email_body or "")[:500],
            rule_description=rule["description"],
            reason="手动转发"
        )
        db.update_forward_rule_match(request.rule_id)
        return {"success": True, "message": result["message"]}
    else:
        raise HTTPException(status_code=500, detail=result.get("error", "转发失败"))


# ==================== 已转发邮件清单（知会流） ====================

@router.get("/forwarded")
async def list_forwarded_emails(only_unread: bool = False, limit: int = 200):
    """获取已转发邮件清单（用于「已转发」Tab 展示）"""
    items = db.get_forwarded_emails(only_unread=only_unread, limit=limit)
    return {
        "items": items,
        "unread_count": db.get_unread_forwarded_count(),
        "total": len(items),
    }


@router.get("/forwarded/unread-count")
async def get_forwarded_unread_count():
    """获取未读已转发邮件数量（用于 Tab 角标）"""
    return {"unread_count": db.get_unread_forwarded_count()}


class ForwardedReadRequest(BaseModel):
    email_id: str
    rule_id: str
    read: bool = True


@router.put("/forwarded/read")
async def mark_forwarded_read(request: ForwardedReadRequest):
    """标记单条已转发记录已读/未读"""
    ok = db.mark_forwarded_read(request.email_id, request.rule_id, request.read)
    return {"success": ok}


@router.put("/forwarded/read-all")
async def mark_all_forwarded_read():
    """全部标为已读"""
    n = db.mark_all_forwarded_read()
    return {"success": True, "updated": n}


# ==================== 测试SMTP连接 ====================

@router.post("/settings/smtp/test")
async def test_smtp_connection(request: SmtpConfigRequest):
    """测试SMTP连接"""
    import smtplib
    
    try:
        if request.smtp_ssl:
            server = smtplib.SMTP_SSL(request.smtp_server, request.smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(request.smtp_server, request.smtp_port, timeout=10)
            # 仅当服务器声明支持 STARTTLS 时才升级加密；纯明文服务器直接明文连接
            server.ehlo()
            if server.has_extn("STARTTLS"):
                server.starttls()
                server.ehlo()
        
        if request.password:
            server.login(request.email_address, request.password)
        
        server.quit()
        return {"success": True, "message": "SMTP连接测试成功"}
    except smtplib.SMTPAuthenticationError:
        return {"success": False, "error": "SMTP认证失败，请检查邮箱地址和密码"}
    except smtplib.SMTPConnectError:
        return {"success": False, "error": f"无法连接SMTP服务器 {request.smtp_server}:{request.smtp_port}"}
    except Exception as e:
        return {"success": False, "error": f"连接测试失败: {str(e)}"}
