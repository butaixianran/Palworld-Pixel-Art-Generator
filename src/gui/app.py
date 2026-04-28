"""
主应用路由与页面管理器
======================
采用单页面容器切换方案：
- 所有页面内容渲染在同一个主容器中
- 通过 container.clear() + 重新渲染实现首页/设置页切换
- 语言切换时直接重新渲染当前页面

注意：不使用 ui.scroll_area()，直接让页面（body）自然滚动，
这是 Native 模式下最可靠的滚动方案，避免了 q-scroll-area
高度计算失效导致的窗口下半部分空白问题。
"""

from nicegui import ui
from i18n import translator
from config import config_manager

# 模块级变量：主容器和当前页面标识
_main_container = None
_current_page: str = "home"


def init_app() -> None:
    """
    初始化应用程序。

    在 @ui.page 注册之前注入强力全局 CSS，彻底消除所有层级的
    默认 padding 与 margin（包括 Quasar 的 q-page、body、#app 等）。
    """
    ui.add_head_html("""
    <style>
        /* 彻底消除所有层级的默认外边距与内边距 */
        html, body, #app, .q-page, .q-page-container {
            margin: 0 !important;
            padding: 0 !important;
        }
        /* 确保 body 占满整个窗口高度，使内容可以自然滚动 */
        html, body, #app {
            height: 100%;
        }
        /* Quasar 默认在 q-page 内部可能有 .column 等元素的默认 gap，一并消除 */
        .q-page > .column {
            padding: 0 !important;
        }
    </style>
    """, shared=True)

    @ui.page("/")
    def main_page() -> None:
        """根页面：创建主容器并渲染首页。"""
        global _main_container

        # 初始化语言（从配置文件读取）
        saved_lang = config_manager.get("language", "en")
        if saved_lang in translator.available_languages():
            translator.set_language(saved_lang)
        else:
            translator.set_language("en")
            config_manager.set("language", "en")

        # 创建主容器：宽度填满，高度由内容自然撑开
        # 不再使用 h-full / flex / flex-col，避免 flex 布局高度计算失效
        _main_container = ui.column().classes("w-full")

        # 注册语言切换监听器：当语言改变时，重新渲染当前页面
        translator.add_listener(_refresh_current_page)

        # 默认显示首页
        _show_home()


def _refresh_current_page() -> None:
    """语言切换监听器回调：重新渲染当前页面以更新所有文字。"""
    if _current_page == "home":
        _show_home()
    elif _current_page == "settings":
        _show_settings()


def _show_home() -> None:
    """切换到首页。"""
    global _current_page
    _current_page = "home"
    _main_container.clear()
    with _main_container:
        from gui.pages.home_page import render_home_page
        render_home_page(on_navigate_to_settings=_show_settings)


def _show_settings() -> None:
    """切换到设置页面。"""
    global _current_page
    _current_page = "settings"
    _main_container.clear()
    with _main_container:
        from gui.pages.settings_page import render_settings_page
        render_settings_page(on_navigate_back=_show_home)
