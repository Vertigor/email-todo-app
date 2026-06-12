# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller打包配置文件
用于将应用打包成exe文件
"""
from PyInstaller.utils.hooks import copy_metadata, collect_data_files

block_cipher = None

# 收集需要元数据的包
datas = [
    ('deploy_starter/static', 'deploy_starter/static'),
    ('deploy_starter/config.yml', 'deploy_starter'),
]
datas += copy_metadata('fastmcp')
datas += copy_metadata('openai')
datas += copy_metadata('httpx')
datas += copy_metadata('pydantic')

a = Analysis(
    ['deploy_starter/launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'deploy_starter.main',
        'deploy_starter.mcp_server',
        'deploy_starter.database',
        'deploy_starter.models',
        'deploy_starter.launcher',
        'uvicorn',
        'fastapi',
        'fastmcp',
        'apscheduler',
        'PyQt5',
        'PyQt5.QtWebEngineWidgets',
        'email',
        'poplib',
        'sqlite3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # ===== AI/ML 框架（项目不使用）=====
        'torch', 'torchvision', 'torchaudio',
        'transformers', 'tensorflow', 'keras',
        
        # ===== 图像处理（项目不使用）=====
        'cv2', 'opencv', 'opencv-python',
        'PIL', 'pillow', 'Pillow',
        
        # ===== 数据科学（项目不使用）=====
        'matplotlib', 'pandas', 'scipy',
        'sklearn', 'scikit-learn',
        
        # ===== NLP（项目不使用）=====
        'nltk', 'spacy', 'huggingface_hub',
        
        # ===== 开发/测试工具（生产环境不需要）=====
        'jupyter', 'notebook', 'IPython',
        'sphinx', 'docutils',
        'pytest', 'unittest', 'nose',
        
        # ===== GUI 框架（项目用 PyQt5，不用这些）=====
        'tkinter', '_tkinter', 'Tkinter',
        'wx', 'wxPython',
        'PySide2', 'PySide6', 'PyQt6',
        
        # ===== 音频（项目不使用）=====
        'sounddevice', 'pyaudio', 'soundfile',
        
        # ===== 不需要的 PyQt5 硬件/开发模块 =====
        # 注意：QtQuick/QtQml/QtOpenGL 可能被 WebEngine 间接使用，保留它们
        'PyQt5.QtBluetooth',      # 蓝牙
        'PyQt5.QtNfc',            # NFC
        'PyQt5.QtSensors',        # 传感器
        'PyQt5.QtSerialPort',     # 串口
        'PyQt5.QtTest',           # 测试框架
        'PyQt5.QtDesigner',       # 设计器
        'PyQt5.QtHelp',           # 帮助系统
        'PyQt5.QtMultimedia',     # 多媒体
        'PyQt5.QtMultimediaWidgets',
        'PyQt5.QtSql',            # SQL（我们用标准库 sqlite3）
        
        # ===== 数据库驱动（项目只用 sqlite3 标准库）=====
        'MySQLdb', 'mysql', 'mysql.connector',
        'psycopg2', 'psycopg',
        'pysqlite2',
        'pymongo', 'redis',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='EmailTodoApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 临时开启控制台查看错误
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None  # 可以添加图标文件路径，例如: 'icon.ico'
)
