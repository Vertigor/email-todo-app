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

# ===== 致命错误记录：console=False 下崩溃完全无声，这里把错误写到日志文件并弹窗 =====
import traceback as _tb
def _log_fatal(msg):
    try:
        import tempfile
        p = os.path.join(tempfile.gettempdir(), "EmailTodoApp_launch_error.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

def _show_fatal(err_text):
    """把启动错误写到日志，并尽量用对话框告知用户（不再无声崩溃）"""
    _log_fatal(err_text)
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "启动失败", err_text)
    except Exception:
        pass

def _excepthook(et, ev, tb):
    _log_fatal("".join(_tb.format_exception(et, ev, tb)))

sys.excepthook = _excepthook

# 设置高 DPI 支持（必须在导入 Qt 之前）
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

try:
    from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile
    from PyQt5.QtCore import QUrl, Qt
    # PyQt5 需要在创建 QApplication 前设置属性
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    PYQT_VERSION = 5
    PYQT_AVAILABLE = True
except ImportError:
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox, QFileDialog
        from PyQt6.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile
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
    # 无界面模式（服务器模式）：用于无显示环境 / 自动化测试
    if os.environ.get("ET_NO_GUI") == "1":
        print("[launcher] ET_NO_GUI=1 -> 仅启动后台服务，不加载 GUI")
        run_server()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        return

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
        except Exception:
            if i < max_retries - 1:
                time.sleep(0.5)

    # 启动GUI（如果可用）—— 注意：必须在等待循环的【外面】，
    # 否则服务一就绪就 break 跳出循环，GUI 永远不会被创建，程序静默退出。
    if PYQT_AVAILABLE:
        app_qt = QApplication(sys.argv)

        # 设置应用程序属性
        app_qt.setApplicationName("邮箱待办助手")

        browser = QWebEngineView()
        browser.setWindowTitle("邮箱待办助手")
        browser.resize(1200, 800)

        # 处理下载（导出 CSV/JSON、下载 Word 报告）：
        # QtWebEngine 不会自动弹保存框，必须由宿主监听 downloadRequested。
        # 否则前端的 <a download>/blob 下载会被静默丢弃（表现为"点了没反应"）。
        #
        # 关键坑：downloadRequested 回调里的 download 对象只是局部参数，
        # 回调一返回若没有任何强引用，Python 会立即 GC 掉它，Qt 侧的下载随之被
        # 取消，结果"弹了保存框、选了路径，但磁盘上啥都没写"。
        # 解决：用一个管理器类把 download 对象强引用住，挂 finished 信号收尾。
        class DownloadManager:
            def __init__(self):
                # 强引用容器：防止 download 对象被 GC（只增不清，pending 数量很少）
                self._keepalive = []

            def handle(self, download):
                try:
                    suggested = download.downloadFileName() or "download"
                except Exception:
                    suggested = "download"
                path, _ = QFileDialog.getSaveFileName(
                    browser, "保存文件", suggested, "所有文件 (*.*)"
                )
                if not path:
                    download.cancel()
                    return
                # 允许覆盖已有文件
                try:
                    download.setOverwriteMode(True)
                except Exception:
                    pass
                download.setPath(path)
                # 强引用 + 收尾信号，二者缺一不可
                self._keepalive.append(download)
                try:
                    download.finished.connect(
                        lambda: self._on_finished(download, path)
                    )
                    download.stateChanged.connect(
                        lambda s: self._on_state(download, path, s)
                    )
                except Exception:
                    pass
                download.accept()

            def _on_finished(self, download, path):
                try:
                    state = getattr(download, "isFinished", lambda: True)()
                    err = None
                    try:
                        err = download.error() if hasattr(download, "error") else None
                    except Exception:
                        pass
                    if err:
                        _log_fatal(f"下载失败: {path} 错误码={err}")
                    else:
                        print(f"[download] 已完成: {path}")
                except Exception as e:
                    _log_fatal(f"下载收尾异常: {e}")

            def _on_state(self, download, path, state):
                # state==2 (DownloadCompleted) / 3 (DownloadCancelled) / 4 (DownloadInterrupted)
                if state in (3, 4):
                    try:
                        err = download.error() if hasattr(download, "error") else None
                    except Exception:
                        err = None
                    if state == 4 or err:
                        _log_fatal(f"下载中断/失败: {path} state={state} err={err}")

        dl_manager = DownloadManager()

        profile = QWebEngineProfile.defaultProfile()
        profile.downloadRequested.connect(dl_manager.handle)

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
    try:
        main()
    except Exception as e:
        _show_fatal(
            "程序启动失败：\n" + str(e)
            + "\n\n详细错误已记录到："
            + os.path.join(__import__("tempfile").gettempdir(), "EmailTodoApp_launch_error.log")
            + "\n\n请把该日志内容发给我以便排查。"
        )
