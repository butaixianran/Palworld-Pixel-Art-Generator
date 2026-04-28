"""
首页 (Home Page)
===============
包含所有用户可调节选项的执行界面。
布局紧凑化，不使用 ui.scroll_area()，让页面自然滚动。

关键行为：
- 存档/图片路径输入框只读，仅通过文件对话框选择
- 选择存档后自动扫描模板和玩家列表，扫描结果直接更新 UI 引用
- config 仅保存目录路径（last_save_dir / last_image_dir）
"""

import os
from typing import Callable, Optional
from nicegui import ui, run

from i18n import t
from config import config_manager
from core import generate_pixel_art, remove_pixel_art, scan_save_file

from gui.components.title_bar import title_bar
from gui.components.file_selector import file_selector


# ------------------------------------------------------------------
# 模块级变量
# ------------------------------------------------------------------

_log_textarea = None
_log_lines: list[str] = []

# 当前选中的文件路径（内存中，不持久化到 config）
_current_save_path: str = ""
_current_image_path: str = ""

# 扫描结果状态（内存中）
_scan_results: dict = {}
_selected_player_index: int = 0

# UI 引用 — 扫描结果展示区（在 render_home_page 中初始化，在 _update_scan_ui 中更新）
_scan_status_row = None          # 模板检查状态行（包含图标+文本）
_player_select_row = None        # 玩家选择行（包含标签+下拉框）
_player_select_dropdown = None   # 玩家下拉框本身的引用


def render_home_page(on_navigate_to_settings: Callable[[], None]) -> None:
    global _scan_status_row, _player_select_row, _player_select_dropdown, _log_textarea

    cfg = config_manager.get_all()

    # 顶部 Title Bar
    title_bar(
        show_settings_button=True,
        show_back_button=False,
        on_settings_click=on_navigate_to_settings,
    )

    # 主内容：页面级自然滚动
    with ui.column().classes("w-full px-2 py-1 gap-2"):

        # 文件选择卡片
        with ui.card().classes("w-full p-2"):
            ui.label(t("save_file")).classes("text-h6 font-bold mb-1")

            file_selector(
                label=t("save_file"),
                button_text=t("browse"),
                extensions=["sav"],
                current_value=_current_save_path,
                on_change=_on_save_file_selected,
                placeholder="Level.sav",
                initialdir=cfg.get("last_save_dir", ""),
            )
            ui.label(t("save_file_desc")).classes("text-caption text-gray-500 mt-0")

            # 扫描结果展示区 — 创建占位 UI 引用
            # 模板状态行（初始显示占位文本）
            _scan_status_row = ui.row().classes("w-full items-center gap-2 mt-1")
            with _scan_status_row:
                ui.label(t("please_select_save_first")).classes("text-caption text-gray-400")

            # 玩家选择行（初始为空，扫描完成后动态填充）
            _player_select_row = ui.row().classes("w-full items-center gap-2 mt-1")
            # 初始为空，扫描后由 _update_scan_ui 填充

            ui.separator().classes("my-2")

            file_selector(
                label=t("image"),
                button_text=t("browse"),
                extensions=["png", "jpg", "jpeg", "bmp", "gif", "webp"],
                current_value=_current_image_path,
                on_change=_on_image_file_selected,
                placeholder="image path",
                initialdir=cfg.get("last_image_dir", ""),
            )
            ui.label(t("image_desc")).classes("text-caption text-gray-500 mt-0")

            ui.separator().classes("my-2")

        # 尺寸限制卡片
        with ui.card().classes("w-full p-2"):
            ui.label(t("max_width")).classes("text-h6 font-bold mb-1")
            with ui.row().classes("w-full items-center gap-4"):
                ui.number(
                    label=t("max_width"),
                    value=cfg.get("max_width", 120),
                    min=10, max=500, precision=0,
                    on_change=lambda e: config_manager.set("max_width", int(e.value or 10)),
                ).classes("w-32")
                ui.label(t("pixel")).classes("text-gray-500")
            ui.label(t("max_width_desc")).classes("text-caption text-gray-500 mt-0")

            ui.separator().classes("my-2")

            ui.label(t("max_height")).classes("text-h6 font-bold mb-1")
            with ui.row().classes("w-full items-center gap-4"):
                ui.number(
                    label=t("max_height"),
                    value=cfg.get("max_height", 120),
                    min=10, max=500, precision=0,
                    on_change=lambda e: config_manager.set("max_height", int(e.value or 10)),
                ).classes("w-32")
                ui.label(t("pixel")).classes("text-gray-500")
            ui.label(t("max_height_desc")).classes("text-caption text-gray-500 mt-0")


        # 建筑风格卡片
        with ui.card().classes("w-full p-2"):
            ui.label(t("foundation_style")).classes("text-h6 font-bold mb-1")
            ui.select(
                label=t("foundation_style"),
                options={
                    "wooden": t("style_wooden"),
                    "stone": t("style_stone"),
                    "metal": t("style_metal"),
                    "glass": t("style_glass"),
                    "sf": t("style_sf"),
                    "japanese": t("style_japanese"),
                },
                value=cfg.get("foundation_style", "sf"),
                on_change=lambda e: config_manager.set("foundation_style", e.value),
            ).classes("w-full")
            ui.label(t("foundation_style_desc")).classes("text-caption text-gray-500 mt-0")

            ui.separator().classes("my-2")

            ui.label(t("pillar_style")).classes("text-h6 font-bold mb-1")
            ui.select(
                label=t("pillar_style"),
                options={
                    "wooden": t("style_wooden"),
                    "stone": t("style_stone"),
                    "metal": t("style_metal"),
                    "glass": t("style_glass"),
                    "sf": t("style_sf"),
                    "japanese": t("style_japanese"),
                },
                value=cfg.get("pillar_style", "glass"),
                on_change=lambda e: config_manager.set("pillar_style", e.value),
            ).classes("w-full")
            ui.label(t("pillar_style_desc")).classes("text-caption text-gray-500 mt-0")

            ui.separator().classes("my-2")

            ui.label(t("wall_style")).classes("text-h6 font-bold mb-1")
            ui.select(
                label=t("wall_style"),
                options={
                    "wooden": t("style_wooden"),
                    "stone": t("style_stone"),
                    "metal": t("style_metal"),
                    "glass": t("style_glass"),
                    "sf": t("style_sf"),
                },
                value=cfg.get("wall_style", "sf"),
                on_change=lambda e: config_manager.set("wall_style", e.value),
            ).classes("w-full")
            ui.label(t("wall_style_desc")).classes("text-caption text-gray-500 mt-0")

        # 立柱与墙壁位置卡片
        with ui.card().classes("w-full p-2"):
            ui.label(t("pillar_position")).classes("text-h6 font-bold mb-1")
            ui.select(
                label=t("pillar_position"),
                options={"front": t("pos_front"), "back": t("pos_back")},
                value=cfg.get("pillar_position", "back"),
                on_change=lambda e: config_manager.set("pillar_position", e.value),
            ).classes("w-full")
            ui.label(t("pillar_position_desc")).classes("text-caption text-gray-500 mt-0")

            ui.separator().classes("my-2")

            ui.label(t("pillar_height")).classes("text-h6 font-bold mb-1")
            with ui.row().classes("w-full items-center gap-4"):
                ui.number(
                    label=t("pillar_height"),
                    value=cfg.get("pillar_height", 1),
                    min=0, max=20, precision=0,
                    on_change=lambda e: config_manager.set("pillar_height", int(e.value or 0)),
                ).classes("w-32")
                ui.label(t("layer")).classes("text-gray-500")
            ui.label(t("pillar_height_desc")).classes("text-caption text-gray-500 mt-0")

            ui.separator().classes("my-2")

            ui.label(t("wall_side")).classes("text-h6 font-bold mb-1")
            ui.select(
                label=t("wall_side"),
                options={"left": t("side_left"), "right": t("side_right")},
                value=cfg.get("wall_side", "left"),
                on_change=lambda e: config_manager.set("wall_side", e.value),
            ).classes("w-full")
            ui.label(t("wall_side_desc")).classes("text-caption text-gray-500 mt-0")

        # 图片调节卡片
        with ui.card().classes("w-full p-2"):
            ui.checkbox(
                text=t("use_linear"),
                value=cfg.get("use_linear_colorspace", True),
                on_change=lambda e: config_manager.set("use_linear_colorspace", e.value),
            ).classes("mb-1")
            ui.label(t("use_linear_desc")).classes("text-caption text-gray-500 mb-2")

            ui.separator().classes("my-2")

            def _slider_card(label_key: str, desc_key: str, config_key: str, default: float):
                with ui.row().classes("w-full items-center gap-4"):
                    ui.label(t(label_key)).classes("font-medium w-24")
                    val_label = ui.label(f"{cfg.get(config_key, default):.1f}").classes("w-12 text-center")
                    ui.slider(
                        min=0.1, max=2.0, step=0.1,
                        value=cfg.get(config_key, default),
                        on_change=lambda e, ck=config_key, vl=val_label: (
                            config_manager.set(ck, round(float(e.value), 1)),
                            vl.set_text(f"{round(float(e.value), 1):.1f}"),
                        ),
                    ).classes("flex-grow")
                ui.label(t(desc_key)).classes("text-caption text-gray-500 mt-0")

            _slider_card("brightness", "brightness_desc", "brightness", 0.8)
            ui.separator().classes("my-2")
            _slider_card("saturation", "saturation_desc", "saturation", 1.2)
            ui.separator().classes("my-2")
            _slider_card("contrast", "contrast_desc", "contrast", 1.2)

        # 删除范围
        # 一个新的卡片范围输入，包含一个标签和一个数值输入框，默认值20000
        # 一个label和数值输入框，默认值20000
        # 然后下面是一个字体小一些的文字说明，说明这个数值是以玩家为中心的水平半径，单位是厘米，用于清理玩家周围的像素照片墙
        with ui.card().classes("w-full p-2"):
            ui.label(t("remove_radius")).classes("text-h6 font-bold mb-1")
            remove_radius_input = ui.number(
                label="",
                value=config_manager.get("remove_radius", 20000),
                min=0, max=100000, precision=0,
                on_change=lambda e: config_manager.set("remove_radius", int(e.value or 0)),
            ).classes("w-32")
            ui.label(t("remove_radius_desc")).classes("text-caption text-gray-500 mt-0")

        # 执行按钮
        with ui.row().classes("w-full justify-around my-2"):
            ui.button(t("generate"), on_click=_on_execute).props("size=lg color=primary").classes("px-8 py-2 text-lg")
            ui.button(t("remove"), on_click=_on_remove).props("size=lg color=accent").classes("px-8 py-2 text-lg")

        # 日志区域
        with ui.card().classes("w-full p-2"):
            ui.label(t("execution_log")).classes("text-h6 font-bold mb-1")
            _log_textarea = ui.textarea(
                value="",
                placeholder="Log:",
            ).props("readonly rows=8").classes("w-full font-mono text-sm")

    ui.timer(0.2, _flush_log_to_textarea)


# ------------------------------------------------------------------
# 扫描结果 UI 更新
# ------------------------------------------------------------------

def _update_scan_ui() -> None:
    """
    根据全局 _scan_results 状态更新扫描结果展示区。
    直接操作 UI 引用，不依赖页面重新渲染。
    """
    global _scan_status_row, _player_select_row, _player_select_dropdown, _selected_player_index

    # 更新模板状态行
    if _scan_status_row is not None:
        _scan_status_row.clear()
        with _scan_status_row:
            if not _scan_results:
                # 尚未扫描
                ui.label(t("please_select_save_first")).classes("text-caption text-gray-400")
            elif _scan_results.get("templates_missing"):
                # 缺少模板 — 用 t() 翻译每个模板ID
                missing_ids = _scan_results.get("templates_missing", [])
                missing_display = [t(f"template_{tid}", default=tid) for tid in missing_ids]
                ui.icon("error", color="red").classes("text-red-500 text-lg")
                ui.label(f"{t('template_missing')}: {', '.join(missing_display)}").classes("text-red-500 font-medium text-sm")
            elif not _scan_results.get("players"):
                # 模板齐全但没有玩家
                ui.icon("error", color="red").classes("text-red-500 text-lg")
                ui.label(t("player_not_found")).classes("text-red-500 font-medium text-sm")
            else:
                # 全部就绪
                ui.icon("check_circle", color="green").classes("text-green-500 text-lg")
                ui.label(t("template_all_found")).classes("text-green-500 font-medium text-sm")

    # 更新玩家选择行
    if _player_select_row is not None:
        _player_select_row.clear()
        _player_select_dropdown = None
        with _player_select_row:
            # 玩家列表，每个元素为 (index, playerUId, nickname)。
            players = _scan_results.get("players", [])
            if players:
                ui.label(t("select_player")).classes("font-medium whitespace-nowrap text-sm")
                options = {str(idx): (name or f"Player {idx}") for idx, _, name in players}
                default_val = str(_selected_player_index) if str(_selected_player_index) in options else str(list(options.keys())[0])
                _player_select_dropdown = ui.select(
                    label="",
                    options=options,
                    value=default_val,
                    on_change=lambda e: _on_player_selected(int(e.value) if e.value else 0),
                ).classes("flex-grow")
            else:
                # 无玩家时显示空或占位
                pass


# ------------------------------------------------------------------
# 回调函数
# ------------------------------------------------------------------

async def _on_save_file_selected(file_path: str) -> None:
    """用户通过文件对话框选择了存档文件后调用（async，支持 await 协程）。"""
    global _current_save_path, _scan_results, _selected_player_index

    if not file_path:
        return

    _current_save_path = file_path
    _scan_results = {}
    _selected_player_index = 0

    # 保存目录路径到 config（不是文件路径）
    save_dir = os.path.dirname(file_path)
    if save_dir and os.path.isdir(save_dir):
        config_manager.set("last_save_dir", save_dir)
        config_manager.save_config()

    # 立即更新 UI 为扫描中状态
    if _scan_status_row is not None:
        _scan_status_row.clear()
        with _scan_status_row:
            ui.spinner(size="20px").classes("mr-2")
            ui.label(t("scanning_save")).classes("text-caption text-blue-500")

    # 触发异步扫描
    await _async_scan_save(file_path)
    # 立即更新UI为扫描结果状态
    if _scan_status_row is not None:
        _scan_status_row.clear()
    


def _on_image_file_selected(file_path: str) -> None:
    """用户通过文件对话框选择了图片文件后调用。"""
    global _current_image_path

    if not file_path:
        return

    _current_image_path = file_path

    image_dir = os.path.dirname(file_path)
    if image_dir and os.path.isdir(image_dir):
        config_manager.set("last_image_dir", image_dir)
        config_manager.save_config()


def _on_player_selected(index: int) -> None:
    """用户在下拉列表中选择了玩家后调用。"""
    global _selected_player_index
    _selected_player_index = index


async def _async_scan_save(file_path: str) -> None:
    """异步扫描存档，不阻塞 UI 主线程。扫描完成后直接更新 UI 引用。"""
    global _scan_results
    try:
        _scan_results = await run.io_bound(scan_save_file, file_path)

        if _scan_results.get("success"):
            ui.notify(_scan_results.get("message", ""), type="positive")
        else:
            ui.notify(_scan_results.get("message", t("error")), type="negative")

        # 关键：直接调用 _update_scan_ui() 刷新界面，而不是 ui.navigate("/")
        _update_scan_ui()

    except Exception as e:
        _scan_results = {"success": False, "message": str(e), "templates_missing": [], "players": []}
        print(f"[i18n notify] 忽略通知错误: {e}")
        _update_scan_ui()


# ------------------------------------------------------------------
# 日志与执行
# ------------------------------------------------------------------

def _flush_log_to_textarea() -> None:
    global _log_textarea
    if _log_textarea is None or not _log_lines:
        return
    try:
        text = "\n".join(_log_lines)
        if hasattr(_log_textarea, "set_value"):
            _log_textarea.set_value(text)
        else:
            _log_textarea.value = text
    except Exception:
        pass


def _log_callback(msg: str) -> None:
    _log_lines.append(msg)


async def _on_execute() -> None:
    _log_lines.clear()
    _log_callback("=" * 60)
    _log_callback(t("starting_execution"))
    _log_callback("=" * 60)

    config_manager.validate_and_clamp()

    # 验证路径
    try:
        if not _current_save_path or not os.path.exists(_current_save_path):
            ui.notify(t("file_not_found", path=_current_save_path or t("please_select_sav")), type="negative")
            return
        if not _current_image_path or not os.path.exists(_current_image_path):
            ui.notify(t("file_not_found", path=_current_image_path or t("please_select_image")), type="negative")
            return
        if not _current_save_path.lower().endswith(".sav"):
            ui.notify(t("please_select_sav"), type="negative")
            return

        # 验证扫描结果
        if not _scan_results or not _scan_results.get("success"):
            ui.notify(_scan_results.get("message", t("please_select_save_first")), type="negative")
            return
    except Exception as e:
        print(f"[i18n notify] 忽略通知错误: {e}")
        return

    output_path = _current_save_path.replace(".sav", "_pixel_art.sav")
    config_manager.save_config()

    try:
        result = await run.io_bound(
            generate_pixel_art,
            save_file_path=_current_save_path,
            image_path=_current_image_path,
            max_width=config_manager.get("max_width", 120),
            max_height=config_manager.get("max_height", 120),
            foundation_style=config_manager.get("foundation_style", "sf"),
            wall_style=config_manager.get("wall_style", "sf"),
            pillar_style=config_manager.get("pillar_style", "glass"),
            pillar_position=config_manager.get("pillar_position", "back"),
            pillar_height=config_manager.get("pillar_height", 1),
            wall_side=config_manager.get("wall_side", "left"),
            use_linear_colorspace=config_manager.get("use_linear_colorspace", True),
            brightness=config_manager.get("brightness", 0.8),
            saturation=config_manager.get("saturation", 1.2),
            contrast=config_manager.get("contrast", 1.2),
            player_index=_selected_player_index,
            log_callback=_log_callback,
        )

        stats = result.get("stats", {})
        ui.notify(
            t("generated_stats",
              foundations=stats.get("foundations", 0),
              walls=stats.get("walls", 0),
              glass=stats.get("glass_walls", 0),
              pillars=stats.get("pillars", 0)),
            type="positive",
        )
        _log_callback(t("execution_completed"))

    except Exception as e:
        _log_callback(f"[{t('error')}] {e}")
        print(f"[i18n notify] 忽略通知错误: {e}")



async def _on_remove() -> None:
    _log_lines.clear()
    _log_callback("=" * 60)
    _log_callback(t("starting_remove"))
    _log_callback("=" * 60)

    config_manager.validate_and_clamp()

    # 验证路径
    try:    
        if not _current_save_path or not os.path.exists(_current_save_path):
            ui.notify(t("file_not_found", path=_current_save_path or t("please_select_sav")), type="negative")
            return
        if not _current_image_path or not os.path.exists(_current_image_path):
            ui.notify(t("file_not_found", path=_current_image_path or t("please_select_image")), type="negative")
            return
        if not _current_save_path.lower().endswith(".sav"):
            ui.notify(t("please_select_sav"), type="negative")
            return

        # 验证扫描结果
        if not _scan_results or not _scan_results.get("success"):
            ui.notify(_scan_results.get("message", t("please_select_save_first")), type="negative")
            return
    except Exception as e:
        print(f"[i18n notify] 忽略通知错误: {e}")
        return

    output_path = _current_save_path.replace(".sav", "_pixel_art_removed.sav")
    config_manager.save_config()

    try:
        result = await run.io_bound(
            remove_pixel_art,
            save_file_path=_current_save_path,
            foundation_style=config_manager.get("foundation_style", "sf"),
            wall_style=config_manager.get("wall_style", "sf"),
            pillar_style=config_manager.get("pillar_style", "glass"),
            remove_radius=config_manager.get("remove_radius", 20000),
            player_index=_selected_player_index,
            log_callback=_log_callback,
        )

        stats = result.get("stats", {})
        ui.notify(
            t("removed_stats",
              original=stats.get("original", 0),
              deleted=stats.get("deleted", 0),
              remaining=stats.get("remaining", 0)),
            type="positive",
        )
        _log_callback(t("remove_completed"))

    except Exception as e:
        _log_callback(f"[{t('error')}] {e}")
        ui.notify(f"{t('error')}: {e}", type="negative")
