"""
邮件转发服务
通过SMTP发送/转发邮件
"""
import base64
import email as email_lib
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr, formatdate
from datetime import datetime

from deploy_starter.utils import (
    get_config_dir,
    encrypt_password,
    decrypt_password,
    log,
)


def _raw_email_dir() -> str:
    """原始邮件（.eml）存放目录"""
    d = os.path.join(get_config_dir(), "raw_emails")
    os.makedirs(d, exist_ok=True)
    return d


def _safe_email_filename(email_id: str) -> str:
    """把 email_id 转成安全的文件名"""
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in email_id)[:200]


def save_raw_email(email_id: str, raw_bytes: bytes) -> None:
    """保存原始邮件字节到磁盘，供后续（手动）转发原样重建"""
    if not email_id or not raw_bytes:
        return
    try:
        path = os.path.join(_raw_email_dir(), _safe_email_filename(email_id) + ".eml")
        with open(path, "wb") as f:
            f.write(raw_bytes)
    except Exception as e:
        log(f"保存原始邮件失败 {email_id}: {e}", "转发")


def load_raw_email(email_id: str) -> bytes:
    """读回原始邮件字节，无则返回 None"""
    if not email_id:
        return None
    try:
        path = os.path.join(_raw_email_dir(), _safe_email_filename(email_id) + ".eml")
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
    except Exception as e:
        log(f"读取原始邮件失败 {email_id}: {e}", "转发")
    return None


def get_smtp_config() -> dict:
    """读取SMTP配置"""
    config_path = os.path.join(get_config_dir(), "smtp_config.json")
    default_settings = {
        "smtp_server": "",
        "smtp_port": 465,
        "smtp_ssl": True,
        "email_address": "",
        "password": "",
        "sender_name": "邮箱待办助手"
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                # 解密密码
                if saved.get("password_encrypted"):
                    saved["password"] = decrypt_password(saved["password_encrypted"])
                return {**default_settings, **saved}
        except Exception as e:
            log(f"读取SMTP配置失败: {e}", "配置")
    return default_settings


# provider → SMTP 映射（与前端 config.js 的 emailServers 对应）
_PROVIDER_SMTP_MAP = {
    "firefox": {"smtp_server": "smtp.fastmail.com",   "smtp_port": 465, "smtp_ssl": True},
    "163":     {"smtp_server": "smtp.163.com",        "smtp_port": 465, "smtp_ssl": True},
    "qq":      {"smtp_server": "smtp.qq.com",         "smtp_port": 465, "smtp_ssl": True},
    "gmail":   {"smtp_server": "smtp.gmail.com",      "smtp_port": 465, "smtp_ssl": True},
    "outlook": {"smtp_server": "smtp.office365.com",  "smtp_port": 587, "smtp_ssl": False},
}


def derive_smtp_from_email_config() -> dict:
    """
    从已保存的收件邮箱配置（email_config.json）推导 SMTP 发件配置。
    用同一邮箱、同一密码（QQ 等服务商的授权码 POP3 / SMTP 通用）。
    无法推导时返回空字段。
    """
    email_cfg_path = os.path.join(get_config_dir(), "email_config.json")
    if not os.path.exists(email_cfg_path):
        return {}
    try:
        with open(email_cfg_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except Exception as e:
        log(f"读取邮箱配置失败: {e}", "配置")
        return {}

    email_address = cfg.get("email_address", "")
    password = ""
    if cfg.get("password_encrypted"):
        password = decrypt_password(cfg["password_encrypted"])

    provider = cfg.get("provider", "custom")
    smtp_meta = _PROVIDER_SMTP_MAP.get(provider)

    if not smtp_meta:
        # custom 或未知：尝试用 pop3_server 反推（pop/pop3 → smtp）
        pop3_server = cfg.get("pop3_server", "") or ""
        if pop3_server.startswith("pop3."):
            smtp_server = "smtp." + pop3_server[len("pop3."):]
        elif pop3_server.startswith("pop."):
            smtp_server = "smtp." + pop3_server[len("pop."):]
        else:
            smtp_server = ""
        smtp_meta = {"smtp_server": smtp_server, "smtp_port": 465, "smtp_ssl": True}

    return {
        "smtp_server": smtp_meta["smtp_server"],
        "smtp_port": smtp_meta["smtp_port"],
        "smtp_ssl": smtp_meta["smtp_ssl"],
        "email_address": email_address,
        "password": password,
        "sender_name": "邮箱待办助手",
    }


def get_effective_smtp_config() -> dict:
    """
    获取最终生效的 SMTP 配置：优先用户单独保存的 SMTP，缺失时回退到收件邮箱推导。
    """
    smtp = get_smtp_config()
    if smtp.get("smtp_server") and smtp.get("email_address") and smtp.get("password"):
        return smtp

    derived = derive_smtp_from_email_config()
    if not derived:
        return smtp  # 全空，原样返回让上层报错

    # 用 derived 填补 smtp 中的空字段
    return {
        "smtp_server": smtp.get("smtp_server") or derived.get("smtp_server", ""),
        "smtp_port": smtp.get("smtp_port") or derived.get("smtp_port", 465),
        "smtp_ssl": smtp.get("smtp_ssl") if smtp.get("smtp_server") else derived.get("smtp_ssl", True),
        "email_address": smtp.get("email_address") or derived.get("email_address", ""),
        "password": smtp.get("password") or derived.get("password", ""),
        "sender_name": smtp.get("sender_name") or derived.get("sender_name", "邮箱待办助手"),
    }


def save_smtp_config(
    smtp_server: str,
    smtp_port: int,
    smtp_ssl: bool,
    email_address: str,
    password: str,
    sender_name: str = "邮箱待办助手"
) -> dict:
    """保存SMTP配置"""
    config_path = os.path.join(get_config_dir(), "smtp_config.json")
    config_data = {
        "smtp_server": smtp_server,
        "smtp_port": smtp_port,
        "smtp_ssl": smtp_ssl,
        "email_address": email_address,
        "sender_name": sender_name
    }
    if password:
        config_data["password_encrypted"] = encrypt_password(password)
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)
    
    return {"success": True, "message": "SMTP配置已保存"}


def _build_forward_note(original_from, original_date, original_subject, rule_description) -> str:
    """构建转发说明文本（放在转发邮件最前面）"""
    note = f"""---------- 转发的邮件 ----------\r
发件人: {original_from}\r
日期: {original_date}\r
主题: {original_subject}\r
"""
    if rule_description:
        note += f"转发原因: 匹配规则「{rule_description}」\r\n"
    note += "---------- 以下为原邮件内容 ----------"
    return note


def _attach_original_parts(msg: MIMEMultipart, original_raw: bytes) -> bool:
    """
    解析原始邮件并把其内容原样挂到转发邮件上，保留正文/HTML/内嵌图片/附件不变。

    返回 True 表示成功挂载了原邮件内容，False 表示解析失败（调用方回退纯文本）。
    """
    try:
        original = email_lib.message_from_bytes(original_raw)
    except Exception as e:
        log(f"解析原始邮件失败，回退纯文本转发: {e}", "转发")
        return False

    # 原样复制原邮件的各顶层部分：
    # - multipart：逐个复制顶层子部件（如 multipart/related 整体保留，内嵌图片 cid 关系不变）
    # - 单一部件：整体作为一个部分挂上
    if original.is_multipart():
        for part in original.get_payload():
            msg.attach(part)
    else:
        msg.attach(original)
    return True


def forward_email(
    original_subject: str,
    original_from: str,
    original_date: str,
    original_body: str,
    recipients: list,
    rule_description: str = "",
    original_raw: bytes = None,
) -> dict:
    """
    转发邮件给指定收件人

    Args:
        original_subject: 原邮件主题
        original_from: 原邮件发件人
        original_date: 原邮件日期
        original_body: 原邮件正文（仅在无原始字节时作为纯文本回退）
        recipients: 转发收件人列表
        rule_description: 匹配的规则描述
        original_raw: 原始邮件字节。提供时原样保留正文/HTML/内嵌图片/附件；
                      为空时回退到纯文本转发（兼容改动前生成的旧待办）

    Returns:
        结果字典
    """
    smtp_config = get_effective_smtp_config()

    # 验证配置
    if not smtp_config.get("smtp_server"):
        return {"success": False, "error": "SMTP服务器未配置（也未检测到可用的收件邮箱配置）"}
    if not smtp_config.get("email_address"):
        return {"success": False, "error": "发件邮箱地址未配置"}
    if not smtp_config.get("password"):
        return {"success": False, "error": "SMTP密码未配置（请先同步收件邮箱并保存密码，或单独配置SMTP）"}

    sender_email = smtp_config["email_address"]
    sender_name = smtp_config.get("sender_name", "邮箱待办助手")
    smtp_server = smtp_config["smtp_server"]
    smtp_port = smtp_config["smtp_port"]
    use_ssl = smtp_config.get("smtp_ssl", True)
    password = smtp_config["password"]

    # 构建转发邮件外层
    msg = MIMEMultipart('mixed')
    msg['From'] = formataddr((sender_name, sender_email))
    msg['To'] = ', '.join(recipients)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = Header(f"Fwd: {original_subject}", 'utf-8')

    note = _build_forward_note(original_from, original_date, original_subject, rule_description)

    # 有原始字节则原样重建（保留附件/HTML/内嵌图片），否则回退纯文本
    rebuilt = False
    if original_raw:
        msg.attach(MIMEText(note + "\r\n", 'plain', 'utf-8'))
        rebuilt = _attach_original_parts(msg, original_raw)

    if not rebuilt:
        # 回退：仅纯文本（清空可能已挂上的 note，避免重复）
        msg = MIMEMultipart('mixed')
        msg['From'] = formataddr((sender_name, sender_email))
        msg['To'] = ', '.join(recipients)
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = Header(f"Fwd: {original_subject}", 'utf-8')
        forward_body = note + f"\r\n\r\n{original_body}\r\n---------- 转发邮件结束 ----------"
        msg.attach(MIMEText(forward_body, 'plain', 'utf-8'))

    try:
        # 连接SMTP服务器并发送
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
            # 仅当服务器声明支持 STARTTLS 时才升级加密；
            # 纯明文服务器（如内网测试）不支持该扩展，直接明文发送（与 Foxmail 行为一致）
            server.ehlo()
            if server.has_extn("STARTTLS"):
                server.starttls()
                server.ehlo()
        
        server.login(sender_email, password)
        server.sendmail(sender_email, recipients, msg.as_string())
        server.quit()
        
        log(f"邮件转发成功: {original_subject[:50]} → {', '.join(recipients)}", "转发")
        return {
            "success": True,
            "message": f"已转发给 {', '.join(recipients)}"
        }
    except smtplib.SMTPAuthenticationError:
        return {"success": False, "error": "SMTP认证失败，请检查邮箱地址和密码"}
    except smtplib.SMTPConnectError:
        return {"success": False, "error": f"无法连接SMTP服务器 {smtp_server}:{smtp_port}"}
    except Exception as e:
        log(f"邮件转发失败: {e}", "转发错误")
        return {"success": False, "error": f"转发失败: {str(e)}"}


async def process_forwarding_for_email(email_item: dict) -> dict:
    """
    处理单封邮件的转发逻辑

    Args:
        email_item: 邮件数据字典

    Returns:
        {
            "results": [...],            # 每条规则的转发结果（成功/失败）
            "skip_todo_creation": bool,  # 是否命中过 also_create_todo=False 的规则，
                                         # True 表示这封邮件已视为"知会/委派"，不再生成自处理待办
        }
    """
    from deploy_starter.database import Database
    from deploy_starter.utils import get_db_path
    from deploy_starter.mcp_server import _check_forward_rules_impl

    db = Database(get_db_path())
    results = []
    skip_todo_creation = False

    rules = db.get_forward_rules(enabled_only=True)
    if not rules:
        return {"results": results, "skip_todo_creation": False}

    # 送给 LLM 规则匹配前剔除原始字节（raw_b64），避免撑爆 prompt
    email_for_llm = {k: v for k, v in email_item.items() if k != "raw_b64"}
    single_email_json = json.dumps([email_for_llm], ensure_ascii=False)
    try:
        match_result = await _check_forward_rules_impl(single_email_json)
    except Exception as e:
        log(f"转发规则检查失败: {e}", "转发")
        return {"results": results, "skip_todo_creation": False}

    if not isinstance(match_result, dict) or "error" in match_result:
        log(f"转发规则检查返回错误: {match_result}", "转发")
        return {"results": results, "skip_todo_creation": False}

    matches = match_result.get("matches", [])

    for match in matches:
        email_id = match.get("email_id", "")
        rule_id = match.get("rule_id", "")
        reason = match.get("reason", "")

        if email_id != email_item.get("id", ""):
            continue

        rule = db.get_forward_rule(rule_id)
        if not rule:
            log(f"转发规则不存在: {rule_id}", "转发")
            continue

        # 命中"不再生成待办"的规则即视为已委派
        if not rule.get("also_create_todo", False):
            skip_todo_creation = True

        if db.is_email_forwarded(email_id, rule_id):
            log(f"邮件已转发过，跳过: {email_id} → 规则 {rule_id}", "转发")
            continue

        # 取原始邮件字节：优先用同步时随 email_item 带来的 base64，其次从磁盘读回
        original_raw = None
        raw_b64 = email_item.get("raw_b64")
        if raw_b64:
            try:
                original_raw = base64.b64decode(raw_b64)
            except Exception:
                original_raw = None
        if original_raw is None:
            original_raw = load_raw_email(email_id)

        forward_result = forward_email(
            original_subject=email_item.get("subject", "(无主题)"),
            original_from=email_item.get("from", "(未知)"),
            original_date=email_item.get("date", ""),
            original_body=email_item.get("body", ""),
            recipients=rule["recipients"],
            rule_description=rule["description"],
            original_raw=original_raw,
        )

        if forward_result.get("success"):
            db.mark_email_forwarded(
                email_id=email_id,
                rule_id=rule_id,
                recipients=rule["recipients"],
                subject=email_item.get("subject", ""),
                from_addr=email_item.get("from", ""),
                original_date=email_item.get("date", ""),
                body_preview=(email_item.get("body", "") or "")[:500],
                rule_description=rule["description"],
                reason=reason,
            )
            db.update_forward_rule_match(rule_id)
            results.append({
                "rule_id": rule_id,
                "rule_description": rule["description"],
                "recipients": rule["recipients"],
                "reason": reason,
                "status": "success"
            })
        else:
            results.append({
                "rule_id": rule_id,
                "rule_description": rule["description"],
                "recipients": rule["recipients"],
                "reason": reason,
                "status": "failed",
                "error": forward_result.get("error", "未知错误")
            })

    return {"results": results, "skip_todo_creation": skip_todo_creation}
