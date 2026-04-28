"""
文件选择组件
封装文件浏览逻辑，优先尝试使用系统原生对话框 (tkinter.filedialog)。
支持通过 initialdir 定位到上一次选择的目录。
正确处理同步或异步的 on_change 回调。
"""

import inspect
import os
from typing import Callable, List
from nicegui import ui


def file_selector(
    label: str,
    button_text: str,
    extensions: List[str],
    current_value: str,
    on_change: Callable[[str], None],
    placeholder: str = "",
    initialdir: str = "",
):
    """
    渲染文件选择控件（标签 + 只读输入框 + 浏览按钮）。

    Args:
        label: 标签文字。
        button_text: 浏览按钮文字。
        extensions: 允许的文件扩展名列表。
        current_value: 当前文件路径或名称。
        on_change: 路径发生变化时的回调（可以是 sync 或 async）。
        placeholder: 输入框占位提示文字。
        initialdir: 文件对话框默认打开的目录路径。
    """
    with ui.row().classes("w-full items-center gap-2"):
        ui.label(label).classes("font-medium whitespace-nowrap")

        # 只读输入框，仅用于显示选中的路径，不允许用户直接编辑
        path_input = ui.input(
            value=current_value or "",
            placeholder=placeholder,
        ).props("readonly").classes("flex-grow")

        async def browse() -> None:
            """尝试打开系统文件对话框，失败则提示用户手动输入。"""
            file_path = _open_native_dialog(label, extensions, initialdir)
            if file_path:
                path_input.set_value(file_path)
                # 安全调用 on_change：检测是否为协程函数，若是则 await
                if inspect.iscoroutinefunction(on_change):
                    await on_change(file_path)
                else:
                    on_change(file_path)
            else:
                try:
                    ui.notify("Can not open file dialog", type="warning")
                except Exception as e:
                    print(f"[File Selector] 无法显示通知: {e}")

        ui.button(button_text, on_click=browse).props("outline dense").classes("shrink-0")


def _open_native_dialog(title_prefix: str, extensions: List[str], initialdir: str = "") -> str:
    """
    使用 tkinter.filedialog 打开系统原生文件选择对话框。

    Args:
        title_prefix: 对话框标题前缀。
        extensions: 扩展名列表。
        initialdir: 对话框默认打开的目录。若为空或不存在则使用当前工作目录。

    Returns:
        选中的文件完整路径，若取消或失败则返回空字符串。
    """
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        root.attributes("-topmost", True)  # 确保对话框置顶

        # 构建文件类型过滤器
        # 多扩展名时合并为单一条目，避免右下角生成下拉过滤列表
        filetypes: list[tuple[str, str]] = []
        if len(extensions) == 1:
            ext = extensions[0].lstrip(".")
            filetypes.append((f"{ext.upper()} file", f"*.{ext}"))
        else:
            patterns = " ".join(f"*.{e.lstrip('.')}" for e in extensions)
            filetypes.append(("Supported files", patterns))
        filetypes.append(("All files", "*.*"))

        # 校验 initialdir 是否有效
        init_dir = initialdir
        if not init_dir or not os.path.isdir(init_dir):
            init_dir = os.getcwd()

        result = filedialog.askopenfilename(
            title=f"{title_prefix}",
            filetypes=filetypes,
            initialdir=init_dir,
        )
        root.destroy()
        return result if result else ""
    except Exception:
        return ""
