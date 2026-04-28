"""
自定义 Title Bar 组件
模拟应用顶部标题栏，包含 App 名称和右侧操作按钮（设置/返回）。
"""

from nicegui import ui
from i18n import t


def title_bar(
    show_settings_button: bool = True,
    show_back_button: bool = False,
    on_settings_click=None,
    on_back_click=None,
):
    """
    渲染自定义 Title Bar。

    Args:
        show_settings_button: 是否显示设置（齿轮）按钮。
        show_back_button: 是否显示返回按钮。
        on_settings_click: 设置按钮点击回调。
        on_back_click: 返回按钮点击回调。
    """
    with ui.row().classes("w-full items-center justify-between px-3 py-1 bg-gray-800 text-white shadow-md"):
        # 左侧：App 名称
        ui.label(t("app_name")).classes("text-lg font-bold")

        # 右侧：按钮区域
        with ui.row().classes("gap-2"):
            if show_settings_button and on_settings_click:
                ui.button(icon="settings", on_click=on_settings_click).props("flat round color=white").tooltip(t("settings"))
            if show_back_button and on_back_click:
                ui.button(icon="arrow_back", on_click=on_back_click).props("flat round color=white").tooltip(t("back"))
