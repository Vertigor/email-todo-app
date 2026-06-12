"""
启动器：启动后台FastAPI服务和GUI界面
"""
import sys
import os
import threading
import time
import multiprocessing
from pathlib import Path

# ===== Windows 打包必需：freeze_support =====
# 必须在最开始调用，否则无控制台模式下 multiprocessing 会出问题
if __name__ == "__main__":
    multiprocessing.freeze_support()

# ===== 修复无控制台模式下 stdout/stderr 为 None 的问题 =====
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

# 设置高 DPI 支持（必须在导入 Qt 之前）
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

try:
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    from PyQt5.QtCore import QUrl, Qt
    # PyQt5 需要在创建 QApplication 前设置属性
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    PYQT_VERSION = 5
    PYQT_AVAILABLE = True
except ImportError:
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtCore import QUrl
        # PyQt6 默认启用高 DPI，不需要额外设置
        PYQT_VERSION = 6
        PYQT_AVAILABLE = True
    except ImportError:
        PYQT_AVAILABLE = False
        PYQT_VERSION = 0

import uvicorn
from deploy_starter.main import app


def run_server():
    """在后台线程运行FastAPI服务"""
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=18080,
        log_level="error"  # 减少日志输出
    )


def main():
    """主函数"""
    # 启动后台服务器
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # 等待服务启动
    import requests
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get("http://localhost:18080/health", timeout=1)
            if response.status_code == 200:
                break
        except:
            if i < max_retries - 1:
                time.sleep(0.5)
    
    # 启动GUI（如果可用）
    if PYQT_AVAILABLE:
        app_qt = QApplication(sys.argv)
        
        # 设置应用程序属性
        app_qt.setApplicationName("邮箱待办助手")
        
        browser = QWebEngineView()
        browser.setWindowTitle("邮箱待办助手")
        browser.resize(1200, 800)
        
        # 加载前端页面
        url = QUrl("http://localhost:18080/static/index.html")
        browser.load(url)
        browser.show()
        
        # PyQt5 使用 exec_(), PyQt6 使用 exec()
        if PYQT_VERSION == 5:
            sys.exit(app_qt.exec_())
        else:
            sys.exit(app_qt.exec())
    else:
        # 如果没有GUI，只运行服务器（不会到这里，因为打包时一定有 PyQt5）
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
