"""
FastMCP Server Development Template
主应用入口 - 负责应用初始化、生命周期管理和路由注册
"""
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

# Import MCP Server instance
from deploy_starter.mcp_server import mcp
from deploy_starter.utils import read_config

# Import routers
from deploy_starter.routers import (
    chat_router,
    todos_router,
    emails_router,
    settings_router,
    forwarding_router,
)

config = read_config()

# ==================== Create MCP ASGI Application ====================
mcp_asgi_app = mcp.streamable_http_app(path="/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    async with mcp_asgi_app.router.lifespan_context(app):
        # 后端不再负责自动同步，全部由前端定时触发（走 SSE 显示进度）
        yield


# ==================== Create FastAPI Application ====================
app = FastAPI(
    title=config.get("APP_NAME", "MCP Server with Chat"),
    debug=config.get("DEBUG", False),
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Mount Static Files ====================
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ==================== Mount MCP Server ====================
app.mount("/mcp", mcp_asgi_app)

# ==================== Register Routers ====================
app.include_router(chat_router)
app.include_router(todos_router)
app.include_router(emails_router)
app.include_router(settings_router)
app.include_router(forwarding_router)


# ==================== Basic Endpoints ====================
@app.get("/")
def read_root():
    return "<h1>hi, i'm running</h1>"


@app.get("/health")
def health_check():
    return "OK"


# ==================== Start Application ====================
def run_app():
    """Entry point for running the application via command line."""
    uvicorn.run(
        "deploy_starter.main:app",
        host=config.get("FC_START_HOST", "127.0.0.1"),
        port=config.get("PORT", 18080),
        reload=config.get("RELOAD", False),
    )


if __name__ == "__main__":
    run_app()
