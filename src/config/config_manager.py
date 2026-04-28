"""
配置管理模块
负责读取、验证、保存用户配置到 JSON 文件。
应用启动时自动加载配置，用户修改后自动持久化。
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

# 配置文件路径：存放在用户主目录下的隐藏文件夹中
CONFIG_DIR = Path.home() / ".palworld_pixel_art"
CONFIG_FILE = CONFIG_DIR / "config.json"

# 默认值配置（与原始脚本中的默认值保持一致）
DEFAULT_CONFIG: Dict[str, Any] = {
    "language": "en",
    "last_save_dir": "",
    "last_image_dir": "",
    "max_width": 120,
    "max_height": 120,
    "foundation_style": "sf",
    "wall_style": "sf",
    "pillar_style": "glass",
    "pillar_position": "back",
    "pillar_height": 1,
    "wall_side": "left",
    "use_linear_colorspace": True,
    "brightness": 1.0,
    "saturation": 1.4,
    "contrast": 1.1,
}

# 建筑风格的内部键名映射（用于下拉列表）
VALID_FOUNDATION_STYLES = ["wooden", "stone", "metal", "glass", "sf", "japanese"]
VALID_WALL_STYLES = ["wooden", "stone", "metal", "glass", "sf"]  # 排除 japanese
VALID_PILLAR_STYLES = ["wooden", "stone", "metal", "glass", "sf", "japanese"]
VALID_PILLAR_POSITIONS = ["front", "back"]
VALID_WALL_SIDES = ["left", "right"]

# 滑块等 UI 元素的限制
MIN_IMAGE_SIZE = 10
MAX_IMAGE_SIZE = 500
MIN_SLIDER = 0.1
MAX_SLIDER = 2.0
SLIDER_STEP = 0.1
MIN_PILLAR_HEIGHT = 0
MAX_PILLAR_HEIGHT = 20


class ConfigManager:
    """
    配置管理器。

    在内存中维护当前配置字典，提供读取、设置、保存、验证功能。
    """

    def __init__(self):
        """初始化时自动创建配置目录，并加载已有配置（如果存在）。"""
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _ensure_dir(self) -> None:
        """确保配置目录存在。"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> None:
        """
        从配置文件加载配置。

        如果配置文件不存在，则使用默认配置并自动保存一份。
        """
        self._ensure_dir()
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                # 合并默认值与已保存的值（防止新增字段时缺失）
                self._config = {**DEFAULT_CONFIG, **loaded}
            except Exception as e:
                print(f"[ConfigManager] 配置文件读取失败: {e}，使用默认配置")
                self._config = DEFAULT_CONFIG.copy()
                self.save_config()
        else:
            self._config = DEFAULT_CONFIG.copy()
            self.save_config()

    def save_config(self) -> None:
        """将当前内存中的配置写入到 JSON 文件。"""
        self._ensure_dir()
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ConfigManager] 配置保存失败: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项。

        Args:
            key: 配置键名。
            default: 若键不存在则返回此默认值。

        Returns:
            配置值。
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        设置配置项（仅修改内存，不自动写入文件；如需持久化请调用 save_config）。

        Args:
            key: 配置键名。
            value: 配置值。
        """
        self._config[key] = value

    def set_multiple(self, updates: Dict[str, Any]) -> None:
        """
        批量更新配置项。

        Args:
            updates: 键值对字典。
        """
        self._config.update(updates)

    def get_all(self) -> Dict[str, Any]:
        """返回当前配置的完整副本。"""
        return self._config.copy()

    def validate_and_clamp(self) -> None:
        """
        验证并修正所有配置项，确保它们在合法范围内。

        此函数会在执行前调用，防止用户通过修改配置文件注入非法值。
        """
        # max_width / max_height
        for key in ("max_width", "max_height"):
            try:
                v = int(self._config.get(key, DEFAULT_CONFIG[key]))
                if v < MIN_IMAGE_SIZE:
                    v = MIN_IMAGE_SIZE
                elif v > MAX_IMAGE_SIZE:
                    v = MAX_IMAGE_SIZE
                self._config[key] = v
            except (ValueError, TypeError):
                self._config[key] = DEFAULT_CONFIG[key]

        # foundation_style
        fs = str(self._config.get("foundation_style", "sf")).strip().lower()
        if fs not in VALID_FOUNDATION_STYLES:
            fs = "sf"
        self._config["foundation_style"] = fs

        # wall_style (排除 japanese)
        ws = str(self._config.get("wall_style", "sf")).strip().lower()
        if ws not in VALID_WALL_STYLES:
            ws = "sf"
        self._config["wall_style"] = ws

        # pillar_style
        ps = str(self._config.get("pillar_style", "glass")).strip().lower()
        if ps not in VALID_PILLAR_STYLES:
            ps = "glass"
        self._config["pillar_style"] = ps

        # pillar_position
        pp = str(self._config.get("pillar_position", "back")).strip().lower()
        if pp not in VALID_PILLAR_POSITIONS:
            pp = "back"
        self._config["pillar_position"] = pp

        # wall_side
        ws_ = str(self._config.get("wall_side", "left")).strip().lower()
        if ws_ not in VALID_WALL_SIDES:
            ws_ = "left"
        self._config["wall_side"] = ws_

        # pillar_height
        try:
            ph = int(self._config.get("pillar_height", 1))
            if ph < MIN_PILLAR_HEIGHT:
                ph = MIN_PILLAR_HEIGHT
            elif ph > MAX_PILLAR_HEIGHT:
                ph = MAX_PILLAR_HEIGHT
            self._config["pillar_height"] = ph
        except (ValueError, TypeError):
            self._config["pillar_height"] = DEFAULT_CONFIG["pillar_height"]

        # sliders: brightness, saturation, contrast
        for key in ("brightness", "saturation", "contrast"):
            try:
                v = float(self._config.get(key, DEFAULT_CONFIG[key]))
                if v < MIN_SLIDER:
                    v = MIN_SLIDER
                elif v > MAX_SLIDER:
                    v = MAX_SLIDER
                self._config[key] = v
            except (ValueError, TypeError):
                self._config[key] = DEFAULT_CONFIG[key]

        # use_linear_colorspace
        ulc = self._config.get("use_linear_colorspace", True)
        self._config["use_linear_colorspace"] = bool(ulc)

        # directory paths (last_save_dir / last_image_dir) — no validation needed
        for key in ("last_save_dir", "last_image_dir"):
            path = self._config.get(key, "")
            if not isinstance(path, str):
                self._config[key] = ""


# 全局单例配置管理器实例
config_manager = ConfigManager()
