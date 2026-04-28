"""
核心模块入口
导出 Pixel Art 生成引擎的主函数和异常类。
"""

from .pixel_art_engine import (
    generate_pixel_art,
    remove_pixel_art,
    scan_save_file,
    PixelArtError,
    MissingTemplateError,
    NoPlayerError,
    FileNotFound,
)

__all__ = [
    "generate_pixel_art",
    "remove_pixel_art",
    "scan_save_file",
    "PixelArtError",
    "MissingTemplateError",
    "NoPlayerError",
    "FileNotFound",
]
