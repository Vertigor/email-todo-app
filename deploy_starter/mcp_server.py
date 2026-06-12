"""
FastMCP Server Development Template
This is an MCP Server starter template based on the fastMcp framework, allowing developers to quickly develop their own MCP Server and deploy it to Alibaba Cloud Bailian high-code platform

Core features:
1. Use @mcp.tool() decorator to quickly define tools
2. Built-in health check interface
3. Support for HTTP SSE, streamable connection methods
4. Provide complete MCP protocol support (list tools, call tool, etc.)

Developers only need to focus on writing their own tool functions.
"""

import json
import os
import poplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
from typing import Annotated, Any

from agentscope_runtime.tools import ModelstudioSearchLite
from agentscope_runtime.tools.searches import SearchLiteInput, SearchLiteOutput
from fastmcp import Client, FastMCP
from pydantic import Field
from deploy_starter.utils import log

# ==================== Configuration Reading ====================


def read_config():
    """Read config.yml file"""
    config_path = os.path.join(os.path.dirname(__file__), "config.yml")
    config = {}
    with open(config_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip().strip("\"'")
                    if value.lower() == "true":
                        value = True
                    elif value.lower() == "false":
                        value = False
                    elif value.isdigit():
                        value = int(value)
                    config[key] = value
    return config


config = read_config()

# ==================== Initialize FastMCP ====================

# Create MCP server instance, define MCP name and version
mcp = FastMCP(name=config.get("MCP_SERVER_NAME", "my-mcp-server"), version="1.0.0")

# ==================== Tool Definition Examples ====================
# Developers can define their own tools here, using @mcp.tool() decorator


# Example tool1, simple addition tool, simple call with average IO performance
@mcp.tool(
    name="add Tool",  # Custom tool name for the LLM
    description="A simple addition tool example for calculating the sum of two integers",  # Custom description
)
def add_numbers(
    a: Annotated[int, Field(description="add a")],
    b: Annotated[int, Field(description="add b")],
) -> int:
    return a + b


# Example tool2, Alibaba Cloud Bailian search, asynchronous call with high IO performance
@mcp.tool(
    name="Alibaba Cloud Bailian search",  # Custom tool name for the LLM
    description="Search MCP wrapper by calling Alibaba Cloud Bailian search API, requires dashScope api key in environment variables",  # Custom description
)
async def search_by_modelStudio(
    query: Annotated[str, Field(description="Search query statement")],
    count: Annotated[int, Field(description="Number of search results returned")] = 5,
) -> SearchLiteOutput:
    input_data = SearchLiteInput(query=query, count=count)
    search_component = ModelstudioSearchLite()
    result = await search_component.arun(input_data)
    print(result)
    return result


# ==================== 邮箱待办工具 ====================

# 内部实现函数（可直接调用）
async def _read_emails_via_pop3_impl(
    email_address: str,
    password: str,
    pop3_server: str = "pop.gmail.com",
    pop3_port: int = 995,
    days: int = 7,
) -> dict:
    """
    通过POP3读取邮箱邮件
    """
    try:
        # 连接POP3服务器（根据端口选择 SSL 或非 SSL），设置30秒超时
        print(f"[POP3] 正在连接服务器 {pop3_server}:{pop3_port}...")
        if pop3_port == 995:
            mail = poplib.POP3_SSL(pop3_server, pop3_port, timeout=30)
        else:
            mail = poplib.POP3(pop3_server, pop3_port, timeout=30)
        print(f"[POP3] 连接成功，正在认证用户 {email_address}...")
        
        mail.user(email_address)
        print(f"[POP3] 用户名已发送，正在验证密码...")
        mail.pass_(password)
        print(f"[POP3] 认证成功！")

        # 获取邮件列表
        print(f"[POP3] 正在获取邮件列表...")
        num_messages = len(mail.list()[1])
        print(f"[POP3] 邮箱共有 {num_messages} 封邮件")

        emails = []
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # 计算要下载的邮件范围
        start_idx = num_messages
        end_idx = max(0, num_messages - 500)
        total_to_download = start_idx - end_idx
        print(f"[POP3] 准备下载最近 {total_to_download} 封邮件（筛选 {days} 天内）...")

        # 读取邮件（从最新到最旧，最多读取500封）
        downloaded = 0
        for i in range(num_messages, max(0, num_messages - 500), -1):
            try:
                downloaded += 1
                print(f"[POP3] 下载邮件 {downloaded}/{total_to_download} (索引 {i})...")
                # 使用 TOP 命令只下载头部+前200行，跳过附件
                raw_email = b'\n'.join(mail.top(i, 200)[1])
                email_message = email.message_from_bytes(raw_email)

                # 解析日期
                date_str = email_message['Date']
                email_date = None
                if date_str:
                    try:
                        email_date = parsedate_to_datetime(date_str)
                        # 转换为本地时间（去掉时区信息）
                        if email_date.tzinfo:
                            email_date = email_date.replace(tzinfo=None)
                        if email_date < cutoff_date:
                            continue
                    except Exception as e:
                        print(f"Error parsing date: {e}")
                        email_date = datetime.now()

                if not email_date:
                    email_date = datetime.now()

                # 解析主题
                subject, encoding = decode_header(email_message['Subject'])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else 'utf-8', errors='ignore')
                else:
                    subject = str(subject)

                # 解析发件人
                from_header = email_message['From']
                if isinstance(from_header, bytes):
                    from_header = from_header.decode('utf-8', errors='ignore')

                # 获取 Message-ID 作为唯一标识
                message_id = email_message.get('Message-ID', '')
                if message_id:
                    # 去掉尖括号
                    email_id = message_id.strip().strip('<>')
                else:
                    # 回退：用内容哈希生成唯一ID
                    import hashlib
                    hash_content = f"{subject}|{email_date.isoformat()}|{from_header}"
                    email_id = hashlib.md5(hash_content.encode()).hexdigest()

                # 解析正文
                body = ""
                if email_message.is_multipart():
                    for part in email_message.walk():
                        content_type = part.get_content_type()
                        if content_type == "text/plain":
                            try:
                                body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                break
                            except Exception as e:
                                print(f"Error decoding part: {e}")
                                pass
                else:
                    try:
                        body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except Exception as e:
                        print(f"Error decoding body: {e}")
                        body = str(email_message.get_payload())

                emails.append({
                    "id": email_id,
                    "subject": subject,
                    "body": body[:2000],  # 限制长度
                    "date": email_date.isoformat(),
                    "from": from_header or ""
                })
            except Exception as e:
                print(f"[POP3] 处理邮件 {i} 出错: {e}")
                continue

        print(f"[POP3] 下载完成，共获取 {len(emails)} 封有效邮件（{days}天内）")
        mail.quit()
        print(f"[POP3] 连接已关闭")

        return {
            "status": "success",
            "count": len(emails),
            "emails": emails
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


# MCP工具注册（包装内部函数）
@mcp.tool(
    name="读取邮箱邮件",
    description="通过POP3连接邮箱，读取指定天数内的邮件。返回邮件列表，包含id、subject、body、date、from等字段。"
)
async def read_emails_via_pop3(
    email_address: Annotated[str, Field(description="邮箱地址，例如: user@example.com")],
    password: Annotated[str, Field(description="邮箱密码或应用专用密码")],
    pop3_server: Annotated[str, Field(description="POP3服务器地址，例如: pop.gmail.com")] = "pop.gmail.com",
    pop3_port: Annotated[int, Field(description="POP3端口，默认995（SSL）")] = 995,
    days: Annotated[int, Field(description="读取最近几天的邮件，默认7天")] = 7,
) -> dict:
    """MCP工具：读取邮箱邮件"""
    return await _read_emails_via_pop3_impl(email_address, password, pop3_server, pop3_port, days)


def _get_llm_settings_for_mcp() -> dict:
    """获取LLM设置（独立函数，避免循环导入）"""
    import os
    import sys
    import json
    # 使用 %APPDATA%/EmailTodoApp 目录
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        config_dir = os.path.join(appdata, 'EmailTodoApp')
    else:
        config_dir = os.path.join(os.path.expanduser('~'), '.config', 'EmailTodoApp')
    config_path = os.path.join(config_dir, "llm_config.json")
    default_settings = {
        "model": "qwen-flash",  # 邮件分析使用较快的模型
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": ""
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                # 解密API Key
                if saved.get("api_key_encrypted"):
                    import base64
                    import platform
                    from cryptography.fernet import Fernet
                    from cryptography.hazmat.primitives import hashes
                    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
                    
                    machine_id = f"{platform.node()}-{platform.system()}-email-todo-app"
                    salt = b'email_todo_salt_v1'
                    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
                    key = base64.urlsafe_b64encode(kdf.derive(machine_id.encode()))
                    f_cipher = Fernet(key)
                    encrypted_bytes = base64.urlsafe_b64decode(saved["api_key_encrypted"].encode())
                    saved["api_key"] = f_cipher.decrypt(encrypted_bytes).decode()
                
                return {**default_settings, **saved}
        except Exception as e:
            print(f"读取LLM配置失败: {e}")
    return default_settings


def _get_user_info_for_mcp() -> dict:
    """获取用户信息设置（独立函数，避免循环导入）"""
    import os
    import sys
    import json
    # 使用 %APPDATA%/EmailTodoApp 目录
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        config_dir = os.path.join(appdata, 'EmailTodoApp')
    else:
        config_dir = os.path.join(os.path.expanduser('~'), '.config', 'EmailTodoApp')
    config_path = os.path.join(config_dir, "user_info.json")
    default_settings = {
        "nicknames": ""
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                return {**default_settings, **saved}
        except Exception as e:
            print(f"读取用户信息失败: {e}")
    return default_settings


def _get_email_config_for_mcp() -> dict:
    """获取邮箱配置（独立函数，获取用户邮箱地址）"""
    import os
    import sys
    import json
    # 使用 %APPDATA%/EmailTodoApp 目录
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        config_dir = os.path.join(appdata, 'EmailTodoApp')
    else:
        config_dir = os.path.join(os.path.expanduser('~'), '.config', 'EmailTodoApp')
    config_path = os.path.join(config_dir, "email_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"读取邮箱配置失败: {e}")
    return {}


# 内部实现函数（可直接调用）
async def _analyze_emails_to_todos_impl(emails: str) -> dict:
    """
    使用LLM分析邮件生成待办事项
    """
    import os
    from openai import AsyncOpenAI

    # 获取LLM设置
    llm_settings = _get_llm_settings_for_mcp()
    
    # 获取API Key（允许留空，某些本地模型不需要）
    api_key = llm_settings.get("api_key", "")

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=llm_settings.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        timeout=20.0
    )
    
    # 邮件分析使用配置的模型，但优先使用快速模型
    email_model = llm_settings.get("model", "qwen-flash")
    
    # Get temperature from settings (None means use API default)
    temperature = llm_settings.get("temperature")
    
    # 获取用户信息
    user_info = _get_user_info_for_mcp()
    email_config = _get_email_config_for_mcp()
    user_email = email_config.get("email_address", "")
    user_nicknames = user_info.get("nicknames", "")
    
    # 构建用户信息部分
    user_info_section = ""
    if user_email or user_nicknames:
        user_info_section = "\n## 用户信息\n"
        if user_email:
            user_info_section += f"- 用户邮箱地址: {user_email}\n"
        if user_nicknames:
            user_info_section += f"- 用户可能的称呼: {user_nicknames}\n"

    # System Prompt - 定义角色和规则
    system_prompt = f"""你是一个邮件分析助手，负责从邮件中提取用户需要处理的待办事项。
{user_info_section}
## 输入说明
邮件数据为JSON格式，每封邮件包含以下字段：
- id: 邮件唯一标识
- subject: 邮件主题
- body: 邮件正文
- date: 邮件发送时间（ISO格式）
- from: 发件人
- to: 收件人
- cc: 抄送

## 判断是否为用户的待办
只提取用户本人需要处理的待办事项。主要根据正文内容判断，收件人/抄送仅作辅助参考。

1. 正文内容判断（主要依据）：
   - 正文中是否提到用户的称呼
   - 正文中是否有需要用户做的事情（如"来拿钱"、"请回复"、"提交材料"等）
   - 只要正文暗示用户需要做某事，就应该生成待办

2. 收件人/抄送（辅助参考）：
   - 用户在 to（收件人）中 → 更可能是需要处理的事项
   - 用户在 cc（抄送）中 → 更可能不是用户的待办事项，但仍需根据正文判断是否与用户相关

3. 综合判断：
   - 如果能明确推断这件事不是用户需要处理的 → 不生成待办
   - 不确定时，生成待办（宁可多提醒，不要漏掉）

## 截止日期分析规则
截止时间（due_date）表示用户最晚需要在什么时候完成这件事。

1. 利用邮件的 date 字段理解相对时间表述（如"明天"、"下周一"、"3天后"）
2. 只有以下情况才填写 due_date：
   - 邮件中明确写了事件需要什么时候完成（如"1月30日前"、"明天下午3点"、"下周一"、"现在"）
   - 根据邮件内容可以明确推断出截止时间
3. 如果邮件没有写截止时间，也无法推断，due_date 必须填 null
4. 时间格式处理：
   - 有具体时间 → 使用该时间（如"下午3点"→15:00:00）
   - 只有日期没有具体时间 → 使用 23:59:00

## 待办拆分规则
1. 默认原则：一封邮件只生成一个待办事项
2. 唯一允许拆分的情况：邮件中明确包含多个截止时间不同的独立事项
3. 如果涉及多个方面但截止时间相同，必须合并为一个待办
4. 合并时，title 概括主要任务，description 包含所有相关细节

## 输出格式
严格返回JSON格式：
{{
    "analysis": "分析：1) 用户是收件人还是抄送 2) 正文是否指向用户 3) 生成哪些待办事项，原因是什么 4) 截止日期",
    "todos": [
        {{
            "title": "简洁的待办标题",
            "description": "包含关键信息的详细描述，指示用户要做什么",
            "due_date": "YYYY-MM-DDTHH:mm:ss 或 null"
        }}
    ]
}}"""

    # User Prompt - 提供邮件数据
    user_prompt = f"""请分析以下邮件，提取待办事项（每封邮件可能有0到多个）。
如果没有明确的待办事项，返回空数组。

邮件数据：
{emails}"""

    try:
        # Build API call parameters
        api_params = {
            "model": email_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"}
        }
        if temperature is not None:
            api_params["temperature"] = temperature
        
        response = await client.chat.completions.create(**api_params)

        result = json.loads(response.choices[0].message.content)
        
        # 记录 LLM 返回结果
        log("", "")
        log("========== LLM 返回 ==========", "LLM返回")
        if result.get("analysis"):
            log(f"分析: {result['analysis']}", "LLM返回")
        todos = result.get("todos", [])
        log(f"待办数量: {len(todos)}", "LLM返回")
        for i, todo in enumerate(todos, 1):
            log(f"  [{i}] {todo.get('title', '无标题')}", "LLM返回")
            log(f"      描述: {todo.get('description', '无')}", "LLM返回")
            log(f"      截止: {todo.get('due_date', 'null')}", "LLM返回")
        log("==============================", "LLM返回")
        log("", "")
        
        return result
    except Exception as e:
        log(f"{str(e)}", "LLM错误")
        return {"error": f"LLM分析失败: {str(e)}"}


# MCP工具注册（包装内部函数）
@mcp.tool(
    name="LLM分析邮件生成待办",
    description="使用LLM分析邮件内容，提取待办事项。返回JSON格式的待办列表，每个待办包含title、description、due_date字段。"
)
async def analyze_emails_to_todos(
    emails: Annotated[str, Field(description="邮件内容JSON字符串，包含邮件列表")],
) -> dict:
    """MCP工具：LLM分析邮件生成待办"""
    return await _analyze_emails_to_todos_impl(emails)


# ==================== 邮件转发工具 ====================

async def _check_forward_rules_impl(emails: str) -> dict:
    """
    使用LLM判断邮件是否匹配转发规则
    """
    import os
    from openai import AsyncOpenAI

    # 获取LLM设置
    llm_settings = _get_llm_settings_for_mcp()
    api_key = llm_settings.get("api_key", "")

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=llm_settings.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        timeout=20.0
    )

    email_model = llm_settings.get("model", "qwen-flash")
    temperature = llm_settings.get("temperature")

    # 获取转发规则（只取启用的）
    from deploy_starter.database import Database
    from deploy_starter.utils import get_db_path
    db = Database(get_db_path())
    rules = db.get_forward_rules(enabled_only=True)

    if not rules:
        return {"matched_rules": [], "message": "没有启用的转发规则"}

    # 构建规则描述列表
    rules_desc = []
    for i, rule in enumerate(rules):
        rules_desc.append(f"规则{i+1} [ID: {rule['id']}]: {rule['description']} → 转发给 {', '.join(rule['recipients'])}")

    rules_text = '\n'.join(rules_desc)

    system_prompt = f"""你是一个邮件转发判断助手。你需要根据用户定义的转发规则，判断邮件是否匹配某条规则。

## 转发规则
{rules_text}

## 判断逻辑
对于每封邮件，逐一检查它是否满足某条转发规则的描述。
- 规则描述是用自然语言书写的，你需要理解其含义
- 如果邮件内容（包括主题、正文、发件人等）满足规则的描述，则认为该邮件匹配该规则
- 一封邮件可以匹配多条规则
- 如果邮件不匹配任何规则，返回空数组

## 输出格式
严格返回JSON格式：
{{
    "analysis": "简要分析每封邮件与规则的匹配情况",
    "matches": [
        {{
            "email_id": "邮件的id字段",
            "rule_id": "匹配的规则ID",
            "reason": "匹配原因"
        }}
    ]
}}"""

    user_prompt = f"""请判断以下邮件是否匹配任何转发规则。

邮件数据：
{emails}"""

    try:
        api_params = {
            "model": email_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"}
        }
        if temperature is not None:
            api_params["temperature"] = temperature

        response = await client.chat.completions.create(**api_params)
        result = json.loads(response.choices[0].message.content)

        log("", "")
        log("========== 转发规则匹配 ==========", "LLM返回")
        if result.get("analysis"):
            log(f"分析: {result['analysis']}", "LLM返回")
        matches = result.get("matches", [])
        log(f"匹配数量: {len(matches)}", "LLM返回")
        for m in matches:
            log(f"  邮件ID: {m.get('email_id')} → 规则ID: {m.get('rule_id')}, 原因: {m.get('reason')}", "LLM返回")
        log("==================================", "LLM返回")
        log("", "")

        return result
    except Exception as e:
        log(f"转发规则匹配失败: {str(e)}", "LLM错误")
        return {"error": f"转发规则匹配失败: {str(e)}"}


# MCP工具注册（包装内部函数）
@mcp.tool(
    name="检查邮件转发规则",
    description="使用LLM判断邮件是否匹配转发规则。返回匹配的规则列表，每个匹配包含email_id、rule_id、reason字段。"
)
async def check_forward_rules(
    emails: Annotated[str, Field(description="邮件内容JSON字符串，包含邮件列表")],
) -> dict:
    """MCP工具：检查邮件转发规则"""
    return await _check_forward_rules_impl(emails)


# ==================== MCP Tool Call Helper Functions ====================
# Use FastMCP Client standard API for tool listing and calling


async def list_mcp_tools() -> list[dict[str, Any]]:
    """
    Get MCP tool list using FastMCP Client via StreamableHttpTransport

    Connect to MCP Server via HTTP URL, using standard Streamable HTTP transport protocol.
    This approach is more suitable for production environments and easier to debug and monitor.
    """
    mcp_base_url = (
        f"http://{config.get('HOST', '127.0.0.1')}:{config.get('PORT', 8080)}"
    )

    print(f"\n{'=' * 60}")
    print("📋 [MCP Call] Get tool list")
    print(f"{'=' * 60}")
    print(f"Connection URL: {mcp_base_url}/mcp/")
    print("Transport method: StreamableHttpTransport")

    try:
        # Create FastMCP Client, pass HTTP URL
        # Client will automatically infer to use HTTP transport
        client = Client(f"{mcp_base_url}/mcp/")

        async with client:
            # Use standard list_tools() method
            tools = await client.list_tools()

            # Convert to dictionary format for subsequent processing
            tools_list = []
            for tool in tools:
                tool_dict = {
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.inputSchema,
                }
                tools_list.append(tool_dict)

            print(f"✅ Successfully retrieved {len(tools_list)} tools")
            for i, tool in enumerate(tools_list, 1):
                print(f"  {i}. {tool['name']} - {tool['description']}")
            print(f"{'=' * 60}\n")

            return tools_list

    except Exception as e:
        print(f"❌ Failed to get tool list: {e}")
        print(f"{'=' * 60}\n")
        return []


async def call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """
    Call MCP tool using FastMCP Client via StreamableHttpTransport

    Connect to MCP Server via HTTP URL, using standard Streamable HTTP transport protocol.
    This approach is more suitable for production environments and easier to debug and monitor.
    """
    mcp_base_url = (
        f"http://{config.get('HOST', '127.0.0.1')}:{config.get('PORT', 8080)}"
    )

    print(f"\n{'=' * 60}")
    print("🔧 [MCP Call] Execute tool")
    print(f"{'=' * 60}")
    print(f"Connection URL: {mcp_base_url}/mcp/")
    print("Transport method: StreamableHttpTransport")
    print(f"Tool name: {tool_name}")
    print(f"Tool arguments: {json.dumps(arguments, indent=2, ensure_ascii=False)}")

    try:
        # Create FastMCP Client, pass HTTP URL
        # Client will automatically infer to use HTTP transport
        client = Client(f"{mcp_base_url}/mcp/")

        async with client:
            # Use standard call_tool() method
            result = await client.call_tool(tool_name, arguments)

            # Process result
            # result.content is a list containing the content returned by the tool
            result_data = None
            if result.content:
                # Extract text content
                for content_item in result.content:
                    if hasattr(content_item, "text"):
                        result_data = content_item.text
                        break
                    elif hasattr(content_item, "data"):
                        result_data = content_item.data
                        break

            print("✅ Tool execution successful")
            print(f"Result: {result_data}")
            print(f"{'=' * 60}\n")

            return result_data

    except Exception as e:
        print(f"❌ Tool execution failed: {e}")
        print(f"{'=' * 60}\n")
        return None


def convert_mcp_tools_to_openai_format(
    mcp_tools: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Convert MCP tool format to OpenAI function calling format
    """
    openai_tools = []

    for tool in mcp_tools:
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get(
                    "inputSchema", {"type": "object", "properties": {}, "required": []}
                ),
            },
        }
        openai_tools.append(openai_tool)

    return openai_tools
