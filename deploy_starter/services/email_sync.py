"""
邮件同步业务逻辑
"""
import json
import os
import uuid
from datetime import datetime

from deploy_starter.database import Database
from deploy_starter.models import TodoItem
from deploy_starter.utils import (
    get_config_dir,
    get_db_path,
    encrypt_password,
    decrypt_password,
    log,
)
import base64
from deploy_starter.services.email_forward import process_forwarding_for_email, save_raw_email

# 初始化数据库
db = Database(get_db_path())

# 全局同步锁（防止并发同步）
_is_syncing = False


def _decode_payload(payload: bytes, charset: str = None) -> str:
    """
    尝试用多种编码解码邮件正文
    
    Args:
        payload: 邮件正文的原始字节
        charset: 邮件头中声明的字符编码
    
    Returns:
        解码后的字符串
    """
    if not payload:
        return ""
    
    # 尝试的编码列表（按优先级排序）
    encodings_to_try = []
    
    # 如果有声明的编码，优先尝试
    if charset:
        # 标准化编码名称
        charset_lower = charset.lower().replace('-', '').replace('_', '')
        # 常见的编码别名映射
        encoding_aliases = {
            'gb2312': 'gb18030',  # gb18030 是 gb2312 的超集
            'gbk': 'gb18030',     # gb18030 是 gbk 的超集
            'gb18030': 'gb18030',
        }
        normalized_charset = encoding_aliases.get(charset_lower, charset)
        encodings_to_try.append(normalized_charset)
    
    # 添加常见的中文编码和其他编码作为后备
    encodings_to_try.extend([
        'utf-8',
        'gb18030',   # 最完整的中文编码，兼容 gb2312 和 gbk
        'gbk',
        'gb2312',
        'big5',      # 繁体中文
        'iso-8859-1',
        'latin-1',
    ])
    
    # 去重但保持顺序
    seen = set()
    unique_encodings = []
    for enc in encodings_to_try:
        if enc and enc.lower() not in seen:
            seen.add(enc.lower())
            unique_encodings.append(enc)
    
    # 依次尝试各种编码
    for encoding in unique_encodings:
        try:
            return payload.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    
    # 所有编码都失败时，使用 utf-8 并忽略错误
    return payload.decode('utf-8', errors='replace')


def get_sync_settings() -> dict:
    """读取同步设置"""
    config_path = os.path.join(get_config_dir(), "sync_config.json")
    default_settings = {
        "only_recent_7days": False,
        "max_emails_per_sync": 100
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                return {**default_settings, **saved}
        except:
            pass
    return default_settings


def get_email_config() -> dict:
    """从配置文件读取邮箱配置"""
    config_path = os.path.join(get_config_dir(), "email_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                # 解密密码
                if config_data.get("password_encrypted"):
                    config_data["password"] = decrypt_password(config_data["password_encrypted"])
                return config_data
        except Exception as e:
            log(f"读取邮箱配置失败: {e}", "配置")
            return {}
    return {}


def save_email_config(
    email_address: str,
    password: str,
    pop3_server: str,
    pop3_port: int,
    save_password: bool = False,
    provider: str = "custom"
):
    """保存邮箱配置到文件（根据选项决定是否加密存储密码）"""
    config_path = os.path.join(get_config_dir(), "email_config.json")
    config_data = {
        "email_address": email_address,
        "pop3_server": pop3_server,
        "pop3_port": pop3_port,
        "save_password": save_password,
        "provider": provider
    }
    # 只有当用户选择保存密码时才存储加密密码
    if save_password and password:
        config_data["password_encrypted"] = encrypt_password(password)
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)


async def sync_emails_internal(
    email_address: str,
    password: str,
    pop3_server: str,
    pop3_port: int
) -> dict:
    """内部同步邮箱函数 - 复用 sync_emails_with_progress 的逻辑"""
    final_result = None
    
    # 消费 sync_emails_with_progress 的所有 yield，只取最终结果
    async for progress_data in sync_emails_with_progress(
        email_address, password, pop3_server, pop3_port, 7
    ):
        # 打印进度到控制台
        if progress_data.get("stage") == "complete":
            final_result = progress_data.get("result", {})
        elif progress_data.get("message"):
            log(f"{progress_data.get('progress', 0)}% - {progress_data['message']}", "同步进度")
    
    if final_result is None:
        return {"error": "同步过程异常终止"}
    
    return final_result


async def sync_emails_with_progress(
    email_address: str,
    password: str,
    pop3_server: str,
    pop3_port: int,
    days_limit: int = 7
):
    """带进度回调的同步邮箱生成器函数"""
    global _is_syncing
    
    # 检查是否有其他同步任务正在进行
    if _is_syncing:
        yield {"stage": "error", "progress": 100, "message": "已有同步任务正在进行中，请稍后再试", "error": True}
        return
    
    _is_syncing = True  # 加锁
    
    try:
        async for data in _sync_emails_impl(email_address, password, pop3_server, pop3_port, days_limit):
            yield data
    finally:
        _is_syncing = False  # 解锁


async def _sync_emails_impl(
    email_address: str,
    password: str,
    pop3_server: str,
    pop3_port: int,
    days_limit: int = 7
):
    """实际的同步实现（内部函数）"""
    import poplib
    import email as email_lib
    from email.header import decode_header
    from email.utils import parsedate_to_datetime
    from datetime import timedelta
    import hashlib
    import asyncio
    
    from deploy_starter.mcp_server import _analyze_emails_to_todos_impl
    
    # 阶段1: 连接服务器 (0-2%)
    yield {"stage": "connecting", "progress": 0, "message": "正在连接邮箱服务器..."}
    await asyncio.sleep(0)  # 让事件循环发送 SSE 数据
    
    try:
        # 连接 POP3 服务器
        if pop3_port == 995:
            mail = poplib.POP3_SSL(pop3_server, pop3_port, timeout=30)
        else:
            mail = poplib.POP3(pop3_server, pop3_port, timeout=30)
        
        yield {"stage": "connecting", "progress": 1, "message": "正在验证账号..."}
        await asyncio.sleep(0)
        mail.user(email_address)
        mail.pass_(password)
        
        yield {"stage": "connecting", "progress": 2, "message": "登录成功，获取邮件列表..."}
        await asyncio.sleep(0)
        
        # 获取邮件数量
        num_messages = len(mail.list()[1])
        yield {"stage": "reading", "progress": 3, "message": f"邮箱共有 {num_messages} 封邮件"}
        
        # 读取同步设置
        sync_settings = get_sync_settings()
        max_emails = sync_settings.get("max_emails_per_sync", 100)
        
        # 计算要扫描的数量
        total_to_scan = min(max_emails, num_messages)
        days = days_limit if days_limit > 0 else 365
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # ========== 阶段2a: 扫描邮件头部，找出需要下载的邮件 (3-20%) ==========
        emails_to_download = []  # 存储需要下载的邮件信息 [(index, email_id, subject, email_date, from_header), ...]
        skipped_count = 0
        
        for idx, i in enumerate(range(num_messages, max(0, num_messages - max_emails), -1)):
            # 每封邮件更新进度
            # 计算扫描进度: 3% + (idx / total) * 17%
            scan_progress = 3 + int(((idx + 1) / total_to_scan) * 17)
            
            log(f"扫描邮件头部 ({idx + 1}/{total_to_scan})...", "POP3")
            yield {
                "stage": "scanning", 
                "progress": scan_progress, 
                "message": f"扫描邮件头部 ({idx + 1}/{total_to_scan})...",
                "current": idx + 1,
                "total": total_to_scan
            }
            await asyncio.sleep(0)  # 让事件循环发送 SSE 数据
            
            try:
                # 只下载头部（TOP 0），快速获取 Message-ID
                raw_header = b'\n'.join(mail.top(i, 0)[1])
                header_message = email_lib.message_from_bytes(raw_header)
                
                # 解析日期，检查是否在时间范围内
                date_str = header_message['Date']
                email_date = None
                if date_str:
                    try:
                        email_date = parsedate_to_datetime(date_str)
                        if email_date.tzinfo:
                            email_date = email_date.replace(tzinfo=None)
                        if email_date < cutoff_date:
                            log(f"跳过旧邮件 (日期: {email_date.strftime('%Y-%m-%d')})", "POP3")
                            continue  # 超出日期范围，跳过
                    except Exception as date_err:
                        log(f"日期解析失败: {date_str}, 错误: {date_err}", "POP3")
                        # 日期解析失败，跳过这封邮件（保守策略）
                        continue
                else:
                    # 没有日期头，跳过这封邮件
                    log(f"邮件无日期头，跳过", "POP3")
                    continue
                
                # 解析主题
                subject_raw = header_message['Subject']
                if subject_raw:
                    subject, encoding = decode_header(subject_raw)[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else 'utf-8', errors='ignore')
                    else:
                        subject = str(subject)
                else:
                    subject = "(无主题)"
                
                # 解析发件人（需要解码 MIME 编码）
                from_raw = header_message['From']
                if from_raw:
                    # decode_header 返回 [(decoded_bytes/str, charset), ...] 列表
                    decoded_parts = decode_header(from_raw)
                    from_parts = []
                    for part, charset in decoded_parts:
                        if isinstance(part, bytes):
                            from_parts.append(part.decode(charset if charset else 'utf-8', errors='ignore'))
                        else:
                            from_parts.append(str(part))
                    from_header = ''.join(from_parts)
                else:
                    from_header = ""
                
                # 解析收件人
                to_raw = header_message['To']
                if to_raw:
                    decoded_parts = decode_header(to_raw)
                    to_parts = []
                    for part, charset in decoded_parts:
                        if isinstance(part, bytes):
                            to_parts.append(part.decode(charset if charset else 'utf-8', errors='ignore'))
                        else:
                            to_parts.append(str(part))
                    to_header = ''.join(to_parts)
                else:
                    to_header = ""
                
                # 解析抄送
                cc_raw = header_message['Cc']
                if cc_raw:
                    decoded_parts = decode_header(cc_raw)
                    cc_parts = []
                    for part, charset in decoded_parts:
                        if isinstance(part, bytes):
                            cc_parts.append(part.decode(charset if charset else 'utf-8', errors='ignore'))
                        else:
                            cc_parts.append(str(part))
                    cc_header = ''.join(cc_parts)
                else:
                    cc_header = ""
                
                # 获取唯一 ID
                message_id = header_message.get('Message-ID', '')
                if message_id:
                    email_id = message_id.strip().strip('<>')
                else:
                    hash_content = f"{subject}|{email_date.isoformat()}|{from_header}"
                    email_id = hashlib.md5(hash_content.encode()).hexdigest()
                
                # 检查是否已处理
                if db.is_email_processed(email_id):
                    skipped_count += 1
                    log(f"跳过已处理邮件 ({email_date.strftime('%m-%d')}): {subject[:50]}", "POP3")
                    continue
                
                # 记录需要下载的邮件
                emails_to_download.append((i, email_id, subject, email_date, from_header, to_header, cc_header))
                
            except Exception as e:
                log(f"扫描邮件 {i} 出错: {e}", "POP3")
                continue
        
        log(f"扫描完成: 需下载 {len(emails_to_download)} 封, 已跳过 {skipped_count} 封", "POP3")
        yield {
            "stage": "scanning", 
            "progress": 20, 
            "message": f"扫描完成，需下载 {len(emails_to_download)} 封，已跳过 {skipped_count} 封"
        }
        
        # ========== 阶段2b: 下载需要的邮件正文 (20-43%) ==========
        emails = []
        total_to_download = len(emails_to_download)
        
        for idx, (mail_idx, email_id, subject, email_date, from_header, to_header, cc_header) in enumerate(emails_to_download):
            # 计算下载进度: 20% + (idx / total) * 23%
            if total_to_download > 0:
                download_progress = 20 + int(((idx + 1) / total_to_download) * 23)
            else:
                download_progress = 43
            
            log(f"下载邮件 ({idx + 1}/{total_to_download}) ({email_date.strftime('%m-%d')}): {subject[:50]}", "POP3")
            yield {
                "stage": "downloading", 
                "progress": download_progress, 
                "message": f"下载邮件 ({idx + 1}/{total_to_download})：{subject[:30]}...",
                "current": idx + 1,
                "total": total_to_download
            }
            await asyncio.sleep(0)  # 让事件循环发送 SSE 数据
            
            try:
                # 下载完整邮件（含附件），用于原样转发；RETR 取全文而非 TOP 截断
                raw_email = b'\n'.join(mail.retr(mail_idx)[1])
                email_message = email_lib.message_from_bytes(raw_email)

                # 原始字节落盘，供后续手动转发原样重建
                save_raw_email(email_id, raw_email)

                # 解析正文
                body = ""
                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/plain":
                            try:
                                payload = part.get_payload(decode=True)
                                if payload:
                                    # 获取正确的字符编码
                                    charset = part.get_content_charset() or part.get_param('charset')
                                    body = _decode_payload(payload, charset)
                                    if body:
                                        break
                            except:
                                pass
                else:
                    try:
                        payload = email_message.get_payload(decode=True)
                        if payload:
                            charset = email_message.get_content_charset() or email_message.get_param('charset')
                            body = _decode_payload(payload, charset)
                    except:
                        body = str(email_message.get_payload())

                emails.append({
                    "id": email_id,
                    "subject": subject,
                    "body": body[:2000],
                    "date": email_date.isoformat(),
                    "from": from_header or "",
                    "to": to_header or "",
                    "cc": cc_header or "",
                    # 随邮件带上原始字节（base64），供同步内联的自动转发直接原样重建
                    "raw_b64": base64.b64encode(raw_email).decode("ascii"),
                })
            except Exception as e:
                log(f"下载邮件 {mail_idx} 出错: {e}", "POP3")
                continue
        
        mail.quit()
        
        emails_result = {"status": "success", "count": len(emails), "emails": emails}
        
    except Exception as e:
        yield {"stage": "error", "progress": 100, "message": f"读取邮件失败: {str(e)}", "error": True}
        return

    log(f"下载完成: {len(emails)} 封新邮件", "POP3")
    yield {"stage": "reading", "progress": 43, "message": f"下载完成，{len(emails)} 封新邮件"}

    if not isinstance(emails_result, dict):
        yield {"stage": "error", "progress": 100, "message": "邮件读取结果格式错误", "error": True}
        return

    if emails_result.get("status") != "success":
        yield {"stage": "error", "progress": 100, "message": emails_result.get("message", "读取邮件失败"), "error": True}
        return

    # 阶段3: 准备分析 (43-48%)
    # 注意：扫描阶段已经只下载了未处理的邮件，这里不需要再过滤
    new_emails = emails_result.get("emails", [])
    yield {"stage": "filtering", "progress": 48, "message": f"准备分析 {len(new_emails)} 封新邮件"}

    if not new_emails:
        yield {
            "stage": "complete", 
            "progress": 100, 
            "message": "没有新邮件需要处理",
            "result": {"message": "没有新邮件", "todos_count": 0, "emails_processed": 0}
        }
        return

    # 阶段4: 分析邮件 (20-90%)
    todos_created = []
    total_emails = len(new_emails)
    failed_emails = 0
    last_error = None
    
    for idx, email_item in enumerate(new_emails):
        # 计算当前进度: 48% + (idx / total) * 47%
        current_progress = 48 + int((idx / total_emails) * 47)
        yield {
            "stage": "analyzing",
            "progress": current_progress,
            "message": f"正在分析第 {idx + 1}/{total_emails} 封邮件...",
            "current": idx + 1,
            "total": total_emails
        }
        await asyncio.sleep(0)  # 让事件循环发送 SSE 数据

        # ========== 先做转发判定 ==========
        # 如果命中"不再生成待办"的规则，跳过 LLM 分析，避免在自己的待办列表里
        # 重复挂出已经委派/知会出去的事项。
        skip_todo_creation = False
        try:
            forward_outcome = await process_forwarding_for_email(email_item)
            forward_results = forward_outcome.get("results", [])
            skip_todo_creation = forward_outcome.get("skip_todo_creation", False)
            for fr in forward_results:
                if fr.get('status') == 'success':
                    log(f"邮件已转发: {email_item.get('subject', '')[:30]} → {', '.join(fr.get('recipients', []))}", "转发")
                else:
                    log(f"邮件转发失败: {fr.get('error', '未知错误')}", "转发")
        except Exception as e:
            log(f"转发检查异常: {e}", "转发")

        if skip_todo_creation:
            log(f"邮件已转发为知会/委派，跳过自处理待办生成: {email_item.get('subject', '')[:30]}", "LLM")
            db.mark_email_processed(email_item["id"])
            continue

        # 在发送给 LLM 之前，记录邮件信息
        body_text = email_item.get('body', '')
        body_preview = body_text[:500] + ('...' if len(body_text) > 500 else '')
        log("", "")
        log(f"========== 分析邮件 ({idx + 1}/{total_emails}) ==========", "LLM")
        log(f"标题: {email_item.get('subject', '(无标题)')}", "LLM")
        log(f"发件人: {email_item.get('from', '(未知)')}", "LLM")
        log(f"收件人: {email_item.get('to', '(未知)')}", "LLM")
        log(f"抄送: {email_item.get('cc', '(无)')}", "LLM")
        log(f"日期: {email_item.get('date', '(未知)')}", "LLM")
        log(f"正文:\n{body_preview}", "LLM")

        # 送给 LLM 前剔除原始字节（raw_b64），避免撑爆 prompt
        email_for_llm = {k: v for k, v in email_item.items() if k != "raw_b64"}
        single_email_json = json.dumps([email_for_llm], ensure_ascii=False)
        try:
            analysis_result = await _analyze_emails_to_todos_impl(single_email_json)
        except Exception as e:
            log(f"分析邮件失败: {e}", "LLM")
            failed_emails += 1
            last_error = f"LLM调用异常: {e}"
            continue

        if not isinstance(analysis_result, dict) or "error" in analysis_result:
            error_msg = analysis_result.get("error", str(analysis_result)) if isinstance(analysis_result, dict) else str(analysis_result)
            log(f"分析结果错误: {error_msg}", "LLM")
            failed_emails += 1
            last_error = error_msg
            continue

        # 保存待办事项
        for todo_data in analysis_result.get("todos", []):
            try:
                due_date = None
                if todo_data.get("due_date"):
                    try:
                        due_date = datetime.fromisoformat(todo_data["due_date"].replace("Z", "+00:00"))
                        if due_date.tzinfo:
                            due_date = due_date.replace(tzinfo=None)
                    except:
                        pass

                # 解析邮件时间
                email_date = None
                if email_item.get("date"):
                    try:
                        email_date = datetime.fromisoformat(email_item["date"])
                    except:
                        pass

                todo = TodoItem(
                    id=str(uuid.uuid4()),
                    title=todo_data.get("title", "未命名待办"),
                    description=todo_data.get("description", ""),
                    due_date=due_date,
                    created_at=datetime.now(),
                    source_email_id=email_item["id"],
                    source_email_subject=email_item["subject"],
                    source_email_from=email_item.get("from", ""),
                    source_email_to=email_item.get("to", ""),
                    source_email_cc=email_item.get("cc", ""),
                    source_email_date=email_date,
                    source_email_body=email_item.get("body", ""),
                    completed=False
                )
                db.add_todo(todo)
                todos_created.append(todo.dict())
            except Exception as e:
                log(f"创建待办失败: {e}", "数据库")
                continue

        db.mark_email_processed(email_item["id"])

    # 阶段5: 保存数据 (90-95%)
    yield {"stage": "saving", "progress": 95, "message": "正在保存数据..."}

    # 阶段6: 完成 (100%)
    success_emails = total_emails - failed_emails
    
    if failed_emails == total_emails:
        yield {
            "stage": "error", 
            "progress": 100, 
            "message": f"分析失败！{failed_emails} 封邮件全部分析失败",
            "result": {
                "success": False,
                "error": last_error or "LLM分析失败",
                "emails_processed": 0,
                "emails_failed": failed_emails,
                "todos_created": 0
            }
        }
    elif failed_emails > 0:
        yield {
            "stage": "complete", 
            "progress": 100, 
            "message": f"同步完成（部分成功）！成功 {success_emails} 封，失败 {failed_emails} 封，生成了 {len(todos_created)} 个待办事项",
            "result": {
                "success": True,
                "partial_failure": True,
                "emails_processed": success_emails,
                "emails_failed": failed_emails,
                "todos_created": len(todos_created),
                "todos": todos_created,
                "last_error": last_error
            }
        }
    else:
        yield {
            "stage": "complete", 
            "progress": 100, 
            "message": f"同步完成！处理了 {total_emails} 封邮件，生成了 {len(todos_created)} 个待办事项",
            "result": {
                "success": True,
                "emails_processed": total_emails,
                "todos_created": len(todos_created),
                "todos": todos_created
            }
        }
