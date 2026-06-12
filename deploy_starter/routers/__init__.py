"""
FastAPI 路由模块
"""
from .chat import router as chat_router
from .todos import router as todos_router
from .emails import router as emails_router
from .settings import router as settings_router
from .forwarding import router as forwarding_router

__all__ = ["chat_router", "todos_router", "emails_router", "settings_router", "forwarding_router"]
