"""
Settings API 路由
"""
import json
import os
import subprocess
import sys

from fastapi import APIRouter, HTTPException

from deploy_starter.database import Database
from deploy_starter.schemas import ZoomRequest, LLMSettingsRequest
from deploy_starter.utils import (
    read_config,
    get_config_dir,
    get_db_path,
    encrypt_password,
    decrypt_password,
)

router = APIRouter(prefix="/api", tags=["settings"])
config = read_config()
db = Database(get_db_path())


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
                return {**default_settings, **saved}
        except Exception as e:
            print(f"读取LLM配置失败: {e}")
    return default_settings


def save_llm_settings(model: str, base_url: str, api_key: str = "", temperature: float | None = None):
    """保存LLM设置"""
    config_path = os.path.join(get_config_dir(), "llm_config.json")
    settings = {
        "model": model,
        "base_url": base_url
    }
    if api_key:
        settings["api_key_encrypted"] = encrypt_password(api_key)
    if temperature is not None:
        settings["temperature"] = temperature
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


@router.get("/settings/llm")
async def get_llm_settings_endpoint():
    """获取LLM设置"""
    settings = get_llm_settings()
    config_path = os.path.join(get_config_dir(), "llm_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                if saved.get("api_key_encrypted"):
                    settings["api_key"] = decrypt_password(saved["api_key_encrypted"])
        except:
            pass
    return settings


@router.post("/settings/llm")
async def save_llm_settings_endpoint(request: LLMSettingsRequest):
    """保存LLM设置"""
    save_llm_settings(request.model, request.base_url, request.api_key, request.temperature)
    return {"success": True, "message": "LLM设置已保存"}


@router.post("/settings/zoom")
async def save_zoom_setting(request: ZoomRequest):
    """保存缩放级别"""
    config_path = os.path.join(get_config_dir(), "zoom_config.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump({"zoom": request.zoom}, f)
    return {"success": True}


@router.get("/settings/zoom")
async def get_zoom_setting():
    """获取缩放级别"""
    config_path = os.path.join(get_config_dir(), "zoom_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"zoom": 1.0}


@router.get("/settings/sync")
async def get_sync_settings():
    """获取同步设置"""
    config_path = os.path.join(get_config_dir(), "sync_config.json")
    default_settings = {
        "only_recent_7days": False,  # 默认不开启
        "max_emails_per_sync": 100   # 每次扫描最多邮件数
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                return {**default_settings, **saved}
        except:
            pass
    return default_settings


@router.post("/settings/sync")
async def save_sync_settings(request: dict):
    """保存同步设置"""
    config_path = os.path.join(get_config_dir(), "sync_config.json")
    # 读取现有设置
    existing = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except:
            pass
    # 合并新设置
    existing.update(request)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    return {"success": True}


@router.get("/settings/user-info")
async def get_user_info():
    """获取用户信息设置"""
    config_path = os.path.join(get_config_dir(), "user_info.json")
    default_settings = {
        "nicknames": ""
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                return {**default_settings, **saved}
        except:
            pass
    return default_settings


@router.post("/settings/user-info")
async def save_user_info(request: dict):
    """保存用户信息设置"""
    config_path = os.path.join(get_config_dir(), "user_info.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(request, f, ensure_ascii=False, indent=2)
    return {"success": True}


@router.get("/settings/data-dir")
async def get_data_dir():
    """获取数据目录路径"""
    data_dir = get_config_dir()
    return {"data_dir": data_dir}


@router.post("/settings/data-dir/open")
async def open_data_dir():
    """打开数据目录"""
    data_dir = get_config_dir()
    
    try:
        if sys.platform == 'win32':
            subprocess.Popen(['explorer', data_dir])
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', data_dir])
        else:
            subprocess.Popen(['xdg-open', data_dir])
        return {"success": True, "message": "已打开目录"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.delete("/data/clear")
async def clear_all_data():
    """清空所有数据（待办事项和已处理邮件记录，不包括邮箱配置）"""
    try:
        db.clear_all_data()
        return {"success": True, "message": "所有数据已清空"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空数据失败: {str(e)}")
