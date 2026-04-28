"""
设置页面 (Settings Page)
=========================
紧凑化布局版本：消除外层巨大留白，控件间距收紧。
不使用 ui.scroll_area()，直接让页面（body）自然滚动。
"""

from nicegui import ui
from i18n import t, translator, LANGUAGE_OPTIONS
from config import config_manager


def render_settings_page(on_navigate_back: callable) -> None:
    from gui.components.title_bar import title_bar

    # 顶部 Title Bar（带返回按钮，无设置按钮）
    title_bar(
        show_settings_button=False,
        show_back_button=True,
        on_back_click=on_navigate_back,
    )

    # 主内容：直接让页面自然滚动
    with ui.column().classes("w-full px-2 py-1 gap-2"):

        with ui.card().classes("w-full p-2"):
            ui.label(t("language")).classes("text-h6 font-bold mb-1")

            # 当前语言显示
            current_lang_code = translator.get_current_language()
            ui.label(t("current_lang", lang=t(LANGUAGE_OPTIONS.get(current_lang_code, "lang_en")))) \
                .classes("text-body1 mb-2")

            # 语言下拉列表
            ui.select(
                label=t("language"),
                options={code: t(label_key) for code, label_key in LANGUAGE_OPTIONS.items()},
                value=current_lang_code,
                on_change=lambda e: _on_language_change(e.value),
            ).classes("w-full")

            ui.label("Language changes apply instantly / 语言切换后立即生效 / 言語を変更すると即座に反映されます") \
                .classes("text-caption text-gray-500 mt-0")

            ui.separator().classes("my-2")

            # 确定按钮
            ui.button(
                t("ok"),
                on_click=lambda: _on_ok_click(on_navigate_back),
            ).props("color=primary").classes("self-start px-6")


def _on_language_change(lang_code: str) -> None:
    if not lang_code:
        return
    if lang_code not in translator.available_languages():
        return
    translator.set_language(lang_code)
    config_manager.set("language", lang_code)


def _on_ok_click(navigate_back: callable) -> None:
    config_manager.save_config()
    try:
        ui.notify(t("config_saved"), type="positive")
    except Exception as e:
        print(f"[Settings Page] 无法显示通知: {e}")

    navigate_back()
