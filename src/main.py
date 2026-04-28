"""
幻兽帕鲁 Pixel Art 生成器 —— 应用入口
======================================
使用 NiceGUI Native 模式启动桌面应用。

启动方式:
    python main.py

Native 模式会在本地打开一个独立窗口（基于 pywebview），
不依赖外部浏览器，适合作为桌面小工具分发。
"""
import sys
import asyncio
import io
import locale
import os

# 在pyinstaller打包之后，环境会变成gbk,然后碰到gbk不能处理的制服就出错了，因此要强行指定utf8
os.environ["PYTHONUTF8"] = "1"

# Windows 的 ProactorEventLoop 在关闭时可能留下内部的 self-reading future，导致 asyncio 在取消任务/关闭循环时断言失败。
# SelectorEventLoop 避开了这个交互，能稳定关闭。
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


from nicegui import ui, app
from gui.app import init_app


def main() -> None:
    """初始化并启动 Native 模式 GUI 应用。"""
    init_app()

    ui.run(
        title="Palworld Pixel Art Generator",
        native=True,               # 启用 Native 桌面窗口模式
        window_size=(960, 800),    # 窗口初始尺寸 (宽, 高)
        fullscreen=False,
        reload=False,              # 禁用热重载，避免开发模式干扰
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
