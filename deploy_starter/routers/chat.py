"""
Chat/LLM 接口路由
"""
import json
import os
from typing import List, Optional
from pydantic import BaseModel

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from agentscope_runtime.engine.helpers.agent_api_builder import ResponseBuilder
from agentscope_runtime.engine.schemas.agent_schemas import Role

from deploy_starter.mcp_server import (
    call_mcp_tool,
    convert_mcp_tools_to_openai_format,
    list_mcp_tools,
)
from deploy_starter.schemas import ChatRequest
from deploy_starter.utils import read_config, get_config_dir, decrypt_password, get_db_path, log
from deploy_starter.database import Database

router = APIRouter(prefix="/api/chat", tags=["chat"])
config = read_config()


def get_llm_settings() -> dict:
    """获取LLM设置"""
    config_path = os.path.join(get_config_dir(), "llm_config.json")
    default_settings = {
        "model": config.get("DASHSCOPE_MODEL_NAME", "qwen-plus"),
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": ""
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                # 合并默认设置和保存的设置
                result = {**default_settings, **saved}
                # 解密 API Key
                if saved.get("api_key_encrypted"):
                    result["api_key"] = decrypt_password(saved["api_key_encrypted"])
                return result
        except Exception as e:
            print(f"读取LLM配置失败: {e}")
    return default_settings


@router.post("/process")
async def chat(request_data: ChatRequest):
    """
    Chat interface implementation, supports LLM calls and MCP tool calls

    Core workflow:
    1. Receive user message
    2. Get MCP tool list
    3. Call LLM (with function calling)
    4. If LLM needs to call tools, call MCP tools
    5. Return tool results to LLM
    6. Return final response (conforms to AgentScope ResponseBuilder format)
    """

    # Get LLM settings
    llm_settings = get_llm_settings()
    
    # Get API Key（允许留空，某些本地模型不需要）
    api_key = llm_settings.get("api_key", "")

    # Initialize OpenAI client with configured base_url
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=llm_settings.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        timeout=20.0
    )
    
    # Get model name from settings
    model_name = llm_settings.get("model", "qwen-flash")
    
    # Get temperature from settings (None means use API default)
    temperature = llm_settings.get("temperature")

    # Convert message format to OpenAI format
    messages = []
    for msg in request_data.input:
        # Process user messages
        if msg.role == "user":
            content_text = ""
            if msg.content:
                for content_item in msg.content:
                    if content_item.type == "text" and content_item.text:
                        content_text += content_item.text

            if content_text:
                messages.append({"role": "user", "content": content_text})

        # Process assistant's final answer (type="message")
        elif msg.role == "assistant" and msg.type == "message":
            content_text = ""
            if msg.content:
                for content_item in msg.content:
                    if content_item.type == "text" and content_item.text:
                        content_text += content_item.text

            if content_text:
                messages.append({"role": "assistant", "content": content_text})

    # Get MCP tool list
    try:
        mcp_tools = await list_mcp_tools()
        openai_tools = convert_mcp_tools_to_openai_format(mcp_tools)
    except Exception as e:
        print(f"Failed to get MCP tools: {e}")
        openai_tools = []

    async def generate_response():
        """Generate streaming response"""
        response_builder = ResponseBuilder(
            session_id=request_data.session_id,
            response_id=f"resp_{request_data.session_id}",
        )

        yield f"data: {response_builder.created().model_dump_json()}\n\n"
        yield f"data: {response_builder.in_progress().model_dump_json()}\n\n"

        try:
            # First phase: LLM initial response
            # Build common parameters
            common_params = {
                "model": model_name,
                "messages": messages,
                "stream": True,
            }
            if temperature is not None:
                common_params["temperature"] = temperature
            
            if openai_tools:
                response = await client.chat.completions.create(
                    **common_params,
                    tools=openai_tools,
                )
            else:
                response = await client.chat.completions.create(
                    **common_params,
                )

            # Collect LLM response content and tool calls
            llm_content = ""
            tool_calls = []
            current_tool_call = None

            async for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    choice = chunk.choices[0]
                    delta = choice.delta

                    if delta.content:
                        llm_content += delta.content

                    if delta.tool_calls:
                        for tool_call_chunk in delta.tool_calls:
                            if tool_call_chunk.index is not None:
                                if (
                                    current_tool_call is None
                                    or current_tool_call["index"] != tool_call_chunk.index
                                ):
                                    if current_tool_call:
                                        tool_calls.append(current_tool_call)
                                    current_tool_call = {
                                        "index": tool_call_chunk.index,
                                        "id": tool_call_chunk.id or "",
                                        "type": "function",
                                        "function": {
                                            "name": tool_call_chunk.function.name or "",
                                            "arguments": tool_call_chunk.function.arguments or "",
                                        },
                                    }
                                else:
                                    if tool_call_chunk.function.arguments:
                                        current_tool_call["function"]["arguments"] += tool_call_chunk.function.arguments

            if current_tool_call:
                tool_calls.append(current_tool_call)

            if tool_calls:
                # Has tool calls
                if llm_content.strip():
                    reasoning_msg_builder = response_builder.create_message_builder(
                        role=Role.ASSISTANT, message_type="reasoning"
                    )
                    yield f"data: {reasoning_msg_builder.get_message_data().model_dump_json()}\n\n"

                    reasoning_content_builder = reasoning_msg_builder.create_content_builder()
                    yield f"data: {reasoning_content_builder.add_text_delta(llm_content).model_dump_json()}\n\n"
                    yield f"data: {reasoning_content_builder.complete().model_dump_json()}\n\n"
                    yield f"data: {reasoning_msg_builder.complete().model_dump_json()}\n\n"

                messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls})

                # Process each tool call
                for tool_call in tool_calls:
                    tool_name = tool_call["function"]["name"]
                    tool_args = json.loads(tool_call["function"]["arguments"])

                    # Create plugin_call message
                    plugin_call_msg_builder = response_builder.create_message_builder(
                        role=Role.ASSISTANT, message_type="plugin_call"
                    )
                    yield f"data: {plugin_call_msg_builder.get_message_data().model_dump_json()}\n\n"

                    plugin_call_content_builder = plugin_call_msg_builder.create_content_builder(content_type="data")
                    tool_call_data = {
                        "name": tool_name,
                        "arguments": json.dumps(tool_args, ensure_ascii=False),
                    }
                    yield f"data: {plugin_call_content_builder.add_data_delta(tool_call_data).model_dump_json()}\n\n"
                    yield f"data: {plugin_call_content_builder.complete().model_dump_json()}\n\n"
                    yield f"data: {plugin_call_msg_builder.complete().model_dump_json()}\n\n"

                    # Call MCP tool
                    try:
                        tool_result = await call_mcp_tool(tool_name, tool_args)

                        plugin_output_msg_builder = response_builder.create_message_builder(
                            role=Role.ASSISTANT, message_type="plugin_call_output"
                        )
                        yield f"data: {plugin_output_msg_builder.get_message_data().model_dump_json()}\n\n"

                        plugin_output_content_builder = plugin_output_msg_builder.create_content_builder(content_type="data")
                        output_data = {
                            "name": tool_name,
                            "output": json.dumps(tool_result, ensure_ascii=False) if tool_result else "",
                        }
                        yield f"data: {plugin_output_content_builder.add_data_delta(output_data).model_dump_json()}\n\n"
                        yield f"data: {plugin_output_content_builder.complete().model_dump_json()}\n\n"
                        yield f"data: {plugin_output_msg_builder.complete().model_dump_json()}\n\n"

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": json.dumps(tool_result, ensure_ascii=False) if tool_result else "",
                        })
                    except Exception as e:
                        print(f"Tool call failed: {e}")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": f"Error: {str(e)}",
                        })

                # Call LLM again with tool results
                final_params = {
                    "model": model_name,
                    "messages": messages,
                    "stream": True,
                }
                if temperature is not None:
                    final_params["temperature"] = temperature
                final_response = await client.chat.completions.create(**final_params)

                final_msg_builder = response_builder.create_message_builder(
                    role=Role.ASSISTANT, message_type="message"
                )
                yield f"data: {final_msg_builder.get_message_data().model_dump_json()}\n\n"

                final_content_builder = final_msg_builder.create_content_builder()

                async for chunk in final_response:
                    if chunk.choices and len(chunk.choices) > 0:
                        choice = chunk.choices[0]
                        if choice.delta.content:
                            yield f"data: {final_content_builder.add_text_delta(choice.delta.content).model_dump_json()}\n\n"

                yield f"data: {final_content_builder.complete().model_dump_json()}\n\n"
                yield f"data: {final_msg_builder.complete().model_dump_json()}\n\n"

            else:
                # No tool calls
                msg_builder = response_builder.create_message_builder(
                    role=Role.ASSISTANT, message_type="message"
                )
                yield f"data: {msg_builder.get_message_data().model_dump_json()}\n\n"

                content_builder = msg_builder.create_content_builder()
                yield f"data: {content_builder.add_text_delta(llm_content).model_dump_json()}\n\n"
                yield f"data: {content_builder.complete().model_dump_json()}\n\n"
                yield f"data: {msg_builder.complete().model_dump_json()}\n\n"

            yield f"data: {response_builder.completed().model_dump_json()}\n\n"

        except Exception as e:
            print(f"Chat interface error: {e}")
            error_msg_builder = response_builder.create_message_builder(
                role=Role.ASSISTANT, message_type="error"
            )
            error_content_builder = error_msg_builder.create_content_builder()
            error_text = f"Error occurred: {str(e)}"
            yield f"data: {error_content_builder.add_text_delta(error_text).model_dump_json()}\n\n"
            yield f"data: {error_content_builder.complete().model_dump_json()}\n\n"
            yield f"data: {error_msg_builder.complete().model_dump_json()}\n\n"
            yield f"data: {response_builder.completed().model_dump_json()}\n\n"

    return StreamingResponse(generate_response(), media_type="text/event-stream")


# ==================== 待办助手聊天接口 ====================

class TodoAssistantMessage(BaseModel):
    """待办助手聊天消息"""
    role: str  # "user" 或 "assistant"
    content: str


class TodoAssistantRequest(BaseModel):
    """待办助手聊天请求"""
    messages: List[TodoAssistantMessage]


class ChatHistoryRequest(BaseModel):
    """保存聊天记录请求"""
    messages: List[TodoAssistantMessage]


def _get_chat_history_path() -> str:
    """获取聊天记录文件路径"""
    return os.path.join(get_config_dir(), "chat_history.json")


def _get_todos_for_prompt() -> str:
    """获取待办事项数据用于 system prompt"""
    db = Database(get_db_path())
    todos = db.get_todos(completed=None, deleted=False)  # 获取所有未删除的待办
    
    # 注入所有字段
    todos_data = []
    for todo in todos:
        todo_dict = {
            "title": todo.title,
            "description": todo.description,
            "due_date": todo.due_date.isoformat() if todo.due_date else None,
            "created_at": todo.created_at.isoformat() if todo.created_at else None,
            "completed": todo.completed,
            "source_email_subject": todo.source_email_subject,
            "source_email_from": todo.source_email_from,
            "source_email_to": todo.source_email_to,
            "source_email_cc": todo.source_email_cc,
            "source_email_date": todo.source_email_date.isoformat() if todo.source_email_date else None,
            "source_email_body": todo.source_email_body,
        }
        todos_data.append(todo_dict)
    
    return json.dumps(todos_data, ensure_ascii=False, indent=2)


def _build_todo_assistant_system_prompt() -> str:
    """构建待办助手的 system prompt"""
    todos_json = _get_todos_for_prompt()
    
    # 获取当前时间
    from datetime import datetime
    current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    current_weekday = weekday_names[datetime.now().weekday()]
    
    return f"""你是一个待办事项助手，帮助用户查询和了解他们的待办事项。

## 当前时间
现在是：{current_time} {current_weekday}

## 当前待办事项数据（最新）
以下是用户的所有待办事项，这是最新的数据，请根据这些数据回答用户的问题：

{todos_json}

## 回答规则
1. 这是最新的待办数据，请直接根据这些数据回答，不要说"我无法访问"之类的话
2. 可以帮用户统计、筛选、提醒截止日期、分析优先级等
3. 回答要简洁明了，使用中文
4. 如果用户问的内容与待办无关，可以友好地引导回待办相关话题
5. 日期格式友好显示，如"2024年1月15日"而不是 ISO 格式
6. 根据当前时间判断待办是否过期、今天到期、即将到期等"""


@router.post("/todo-assistant")
async def todo_assistant_chat(request: TodoAssistantRequest):
    """
    待办助手聊天接口
    - 将待办事项数据注入 system prompt
    - 支持流式返回
    """
    # 记录收到请求
    user_message = request.messages[-1].content if request.messages else "(空)"
    log(f"收到聊天请求: {user_message[:100]}{'...' if len(user_message) > 100 else ''}", "聊天助手")
    
    # 获取 LLM 设置
    llm_settings = get_llm_settings()
    api_key = llm_settings.get("api_key", "")
    
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=llm_settings.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        timeout=20.0
    )
    
    model_name = llm_settings.get("model", "qwen-flash")
    temperature = llm_settings.get("temperature")
    
    log(f"使用模型: {model_name}", "聊天助手")
    
    # 构建消息列表，包含 system prompt
    messages = [{"role": "system", "content": _build_todo_assistant_system_prompt()}]
    
    # 添加用户的聊天历史
    for msg in request.messages:
        messages.append({"role": msg.role, "content": msg.content})
    
    log(f"开始调用 LLM，消息数: {len(messages)}", "聊天助手")
    
    async def generate_response():
        """生成流式响应"""
        try:
            params = {
                "model": model_name,
                "messages": messages,
                "stream": True,
            }
            if temperature is not None:
                params["temperature"] = temperature
            
            response = await client.chat.completions.create(**params)
            log("LLM 响应开始流式返回", "聊天助手")
            
            async for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    choice = chunk.choices[0]
                    if choice.delta.content:
                        yield f"data: {json.dumps({'content': choice.delta.content}, ensure_ascii=False)}\n\n"
            
            yield f"data: {json.dumps({'done': True})}\n\n"
            log("LLM 响应完成", "聊天助手")
            
        except Exception as e:
            log(f"聊天错误: {e}", "聊天助手")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(generate_response(), media_type="text/event-stream")


@router.get("/history")
async def get_chat_history():
    """获取聊天记录"""
    history_path = _get_chat_history_path()
    
    if os.path.exists(history_path):
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {"messages": data.get("messages", [])}
        except Exception as e:
            print(f"读取聊天记录失败: {e}")
    
    return {"messages": []}


@router.post("/history")
async def save_chat_history(request: ChatHistoryRequest):
    """保存聊天记录"""
    history_path = _get_chat_history_path()
    
    try:
        data = {"messages": [{"role": m.role, "content": m.content} for m in request.messages]}
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"success": True}
    except Exception as e:
        print(f"保存聊天记录失败: {e}")
        return {"success": False, "error": str(e)}


@router.delete("/history")
async def clear_chat_history():
    """清除聊天记录"""
    history_path = _get_chat_history_path()
    
    try:
        if os.path.exists(history_path):
            os.remove(history_path)
        return {"success": True}
    except Exception as e:
        print(f"清除聊天记录失败: {e}")
        return {"success": False, "error": str(e)}
