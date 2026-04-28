"""
Palworld Pixel Art 生成引擎 (pixel_art_engine.py)
====================================================
基于原 pixel_art_generator_v4.py 重构的模块化版本。

所有配置通过函数参数传入，不再依赖全局变量。
日志通过回调函数 log_callback 输出，便于 GUI 实时展示。
返回结果字典供调用方判断执行状态。

依赖:
    Pillow (PIL)
    palworld-save-tools (oMaN-Rod fork)
    Python 标准库: uuid, copy, math, struct, base64, colorsys, os, typing
"""

import copy
import math
import os
import struct
import base64
import colorsys
import uuid
from typing import Callable, Optional, Tuple, Dict, Any, List

try:
    from PIL import Image
except ImportError as exc:
    raise RuntimeError("需要安装 Pillow: pip install Pillow") from exc

try:
    from palworld_save_tools.palsav import decompress_sav_to_gvas, compress_gvas_to_sav
    from palworld_save_tools.gvas import GvasFile
    from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES
except ImportError as exc:
    raise RuntimeError(f"无法导入 palworld-save-tools: {exc}") from exc


# ========== 建筑尺寸常量 ==========
FOUNDATION_SIZE = 400       # 地基间距（游戏内单位）
FOUNDATION_HALF_SIZE = 200  # 地基半边长
WALL_OFFSET = 200           # 墙壁到地基中心的偏移距离
WALL_HEIGHT_UNIT = 325      # 单格墙壁的高度（游戏内 Z 轴单位）

# ========== 建筑风格映射表 ==========
BUILDING_STYLES = {
    "wooden":   {
        "foundation": "Wooden_foundation",
        "wall": "Wooden_wall",
        "pillar": "Wooden_pillar"
    },
    "stone":    {
        "foundation": "Stone_Foundation",
        "wall": "Stone_wall",
        "pillar": "Stone_pillar"
    },
    "metal":    {
        "foundation": "Metal_Foundation",
        "wall": "Metal_wall",
        "pillar": "Metal_pillars"
    },
    "glass":    {
        "foundation": "Glass_foundation",
        "wall": "Glass_wall",
        "pillar": "Glass_pillars"
    },
    "sf":       {
        "foundation": "SF_foundation",
        "wall": "SF_wall",
        "pillar": "SF_Pillars"
    },
    "japanese": {
        "foundation": "JapaneseStyle_foundation",
        "wall": "JapaneseStyle_wall_01",
        "pillar": "JapaneseStyle_Pillar"
    },
}

# ========== 自定义异常 ==========
class PixelArtError(Exception):
    """生成器基础异常。"""
    pass

class MissingTemplateError(PixelArtError):
    """存档中缺少必要的建筑模板时抛出。"""
    pass

class NoPlayerError(PixelArtError):
    """存档中未找到玩家时抛出。"""
    pass

class FileNotFound(PixelArtError):
    """输入文件不存在时抛出。"""
    pass



# ============================================================================
# 工具函数
# ============================================================================

# 原.sav文件改名为.bak.sav，如果存在，就在.bak后面加编号，直到找到一个不存在的文件名为止，确保不会覆盖原始存档。
def _backup_original_save(save_file_path: str, log: Callable[[str], None]) -> str:
    """备份原始存档文件，返回备份文件路径。"""
    if not os.path.exists(save_file_path):
        raise FileNotFound(f"存档文件不存在: {save_file_path}")

    base_dir = os.path.dirname(save_file_path)
    base_name = os.path.basename(save_file_path)
    name_without_ext, ext = os.path.splitext(base_name)

    backup_name = f"{name_without_ext}.bak{ext}"
    backup_path = os.path.join(base_dir, backup_name)

    counter = 1
    while os.path.exists(backup_path):
        backup_name = f"{name_without_ext}.bak{counter}{ext}"
        backup_path = os.path.join(base_dir, backup_name)
        counter += 1

    try:
        # 直接改名，不需要复制
        os.rename(save_file_path, backup_path)
        log(f"Save file backed up to: {backup_path}")
        return backup_path
    except Exception as e:
        raise PixelArtError(f"Rename save file error: {e}") from e



def _extract_str_value(prop: Any) -> str:
    """递归提取属性中的字符串值，兼容多种嵌套格式。"""
    if isinstance(prop, str):
        return prop
    if isinstance(prop, dict):
        for key in ("value", "Str", "str"):
            if key in prop:
                return _extract_str_value(prop[key])
    return str(prop) if prop else ""


def _make_paint_b64(r: float, g: float, b: float, a: float = 1.0) -> str:
    """
    将 RGBA 颜色（0.0-1.0 浮点）转换为游戏 Paint 属性的 base64 格式。

    游戏内格式: FLinearColor (4x float32 小端) + int64 flag=1。
    """
    binary = struct.pack("<ffff", r, g, b, a) + struct.pack("<q", 1)
    return base64.b64encode(binary).decode("ascii")


def _srgb_to_linear(c: float) -> float:
    """
    sRGB 非线性颜色分量 → 线性颜色分量。

    Args:
        c: 0-255 范围的 sRGB 分量值。

    Returns:
        0.0-1.0 范围的线性分量值。
    """
    c = c / 255.0
    if c <= 0.04045:
        return c / 12.92
    return pow((c + 0.055) / 1.055, 2.4)


def _apply_color_adjustment(
    r: int, g: int, b: int,
    brightness: float,
    saturation: float,
    contrast: float,
    use_linear_colorspace: bool
) -> Tuple[float, float, float]:
    """
    对单个像素的 RGB 值应用亮度、饱和度、对比度调节，以及可选的 sRGB→Linear 转换。

    Args:
        r, g, b: 0-255 的 sRGB 分量。
        brightness: 亮度倍数。
        saturation: 饱和度倍数。
        contrast: 对比度倍数。
        use_linear_colorspace: 是否启用 sRGB→Linear 转换。

    Returns:
        调节后的 (r, g, b) 浮点值（0.0-1.0）。
    """
    # 归一化到 0-1
    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0

    # 1. HSV 调节亮度和饱和度
    h, s, v = colorsys.rgb_to_hsv(r_norm, g_norm, b_norm)
    v = max(0.0, min(1.0, v * brightness))
    s = max(0.0, min(1.0, s * saturation))
    r_norm, g_norm, b_norm = colorsys.hsv_to_rgb(h, s, v)

    # 2. RGB 调节对比度
    r_norm = (r_norm - 0.5) * contrast + 0.5
    g_norm = (g_norm - 0.5) * contrast + 0.5
    b_norm = (b_norm - 0.5) * contrast + 0.5

    # clamp 到 [0, 1]
    r_norm = max(0.0, min(1.0, r_norm))
    g_norm = max(0.0, min(1.0, g_norm))
    b_norm = max(0.0, min(1.0, b_norm))

    # 3. 颜色空间转换
    if use_linear_colorspace:
        r_out = _srgb_to_linear(r_norm * 255)
        g_out = _srgb_to_linear(g_norm * 255)
        b_out = _srgb_to_linear(b_norm * 255)
    else:
        r_out = r_norm
        g_out = g_norm
        b_out = b_norm

    return r_out, g_out, b_out


# ============================================================================
# 存档模板查找与克隆
# ============================================================================

def _find_template(data: Dict[str, Any], object_id: str) -> Optional[Dict[str, Any]]:
    """
    在存档的 MapObjectSaveData 中查找指定 ID 的建筑模板。

    Args:
        data: 已解析的存档字典。
        object_id: 建筑类型 ID，如 "SF_foundation"。

    Returns:
        找到的建筑对象字典，若不存在则返回 None。
    """
    map_objects = data["properties"]["worldSaveData"]["value"]["MapObjectSaveData"]["value"]["values"]
    for obj in map_objects:
        if obj.get("MapObjectId", {}).get("value") == object_id:
            return obj
    return None


def _clone_foundation(template: Dict[str, Any], px: float, py: float, pz: float, qz: float, qw: float) -> Dict[str, Any]:
    """克隆地基模板并设置位置、旋转和生命值。"""
    new_obj = copy.deepcopy(template)
    raw_data = new_obj["Model"]["value"]["RawData"]["value"]
    raw_data["instance_id"] = str(uuid.uuid4())
    
    # 还要设置 base_camp_id_belong_to 和 group_id_belong_to 为全0，确保不会被误判为玩家基地的一部分
    raw_data["base_camp_id_belong_to"] = "00000000-0000-0000-0000-000000000000"
    raw_data["group_id_belong_to"] = "00000000-0000-0000-0000-000000000000"

    raw_data["initital_transform_cache"]["translation"]["x"] = float(px)
    raw_data["initital_transform_cache"]["translation"]["y"] = float(py)
    raw_data["initital_transform_cache"]["translation"]["z"] = float(pz)
    raw_data["initital_transform_cache"]["rotation"]["x"] = 0.0
    raw_data["initital_transform_cache"]["rotation"]["y"] = 0.0
    raw_data["initital_transform_cache"]["rotation"]["z"] = float(qz)
    raw_data["initital_transform_cache"]["rotation"]["w"] = float(qw)
    raw_data["hp"]["current"] = 500
    raw_data["hp"]["max"] = 500
    raw_data["deterioration_damage"] = 0.0
    raw_data["repair_work_id"] = "00000000-0000-0000-0000-000000000000"
    return new_obj


def _clone_wall(template: Dict[str, Any], wx: float, wy: float, wz: float, qz: float, qw: float, paint_b64: Optional[str] = None) -> Dict[str, Any]:
    """克隆墙壁模板并设置位置、旋转、生命值和喷涂颜色。"""
    new_obj = copy.deepcopy(template)
    raw_data = new_obj["Model"]["value"]["RawData"]["value"]
    raw_data["instance_id"] = str(uuid.uuid4())

    # 还要设置 base_camp_id_belong_to 和 group_id_belong_to 为全0，确保不会被误判为玩家基地的一部分
    raw_data["base_camp_id_belong_to"] = "00000000-0000-0000-0000-000000000000"
    raw_data["group_id_belong_to"] = "00000000-0000-0000-0000-000000000000"

    raw_data["initital_transform_cache"]["translation"]["x"] = float(wx)
    raw_data["initital_transform_cache"]["translation"]["y"] = float(wy)
    raw_data["initital_transform_cache"]["translation"]["z"] = float(wz)
    raw_data["initital_transform_cache"]["rotation"]["x"] = 0.0
    raw_data["initital_transform_cache"]["rotation"]["y"] = 0.0
    raw_data["initital_transform_cache"]["rotation"]["z"] = float(qz)
    raw_data["initital_transform_cache"]["rotation"]["w"] = float(qw)
    raw_data["hp"]["current"] = 500
    raw_data["hp"]["max"] = 500
    raw_data["deterioration_damage"] = 0.0
    raw_data["repair_work_id"] = "00000000-0000-0000-0000-000000000000"

    if paint_b64 is not None:
        try:
            paint_raw = new_obj["Model"]["value"]["Paint"]["value"]["RawData"]["value"]
            paint_raw["values"] = paint_b64
            paint_custom = new_obj["Model"]["value"]["Paint"]["value"]["CustomVersionData"]["value"]
            if "values" in paint_custom:
                paint_custom["values"] = "AQAAADgLAN5JSdfOl98tmcDBw2kBAAAA"
        except (KeyError, TypeError):
            pass  # 部分墙壁可能无 Paint 属性，静默跳过
    return new_obj


def _clone_pillar(template: Dict[str, Any], px: float, py: float, pz: float, qz: float, qw: float) -> Dict[str, Any]:
    """克隆立柱模板并设置位置、旋转和生命值。立柱不上色。"""
    new_obj = copy.deepcopy(template)
    raw_data = new_obj["Model"]["value"]["RawData"]["value"]
    raw_data["instance_id"] = str(uuid.uuid4())

    # 还要设置 base_camp_id_belong_to 和 group_id_belong_to 为全0，确保不会被误判为玩家基地的一部分
    raw_data["base_camp_id_belong_to"] = "00000000-0000-0000-0000-000000000000"
    raw_data["group_id_belong_to"] = "00000000-0000-0000-0000-000000000000"

    raw_data["initital_transform_cache"]["translation"]["x"] = float(px)
    raw_data["initital_transform_cache"]["translation"]["y"] = float(py)
    raw_data["initital_transform_cache"]["translation"]["z"] = float(pz)
    raw_data["initital_transform_cache"]["rotation"]["x"] = 0.0
    raw_data["initital_transform_cache"]["rotation"]["y"] = 0.0
    raw_data["initital_transform_cache"]["rotation"]["z"] = float(qz)
    raw_data["initital_transform_cache"]["rotation"]["w"] = float(qw)
    raw_data["hp"]["current"] = 500
    raw_data["hp"]["max"] = 500
    raw_data["deterioration_damage"] = 0.0
    raw_data["repair_work_id"] = "00000000-0000-0000-0000-000000000000"
    return new_obj


# ============================================================================
# 玩家查找与朝向计算
# ============================================================================

def _find_all_players(data: Dict[str, Any]) -> List[Tuple[int, str, str, float, float, float, Dict[str, Any]]]:
    """
    在存档中查找所有 IsPlayer=True 的玩家角色。

    Args:
        data: 已解析的存档字典。

    Returns:
        玩家列表，每个元素为 (index, playerUId, nickname, x, y, z, save_param)。
        index 是玩家在列表中的顺序编号（0-based），用于 UI 下拉框选择。
    """
    players: List[Tuple[int, str, str, float, float, float, Dict[str, Any]]] = []
    char_map = data["properties"]["worldSaveData"]["value"]["CharacterSaveParameterMap"]["value"]
    for entry in char_map:
        try:
            # 从entry["key"]里面获得PlayerUId
            # entry["key"]的结构参考：
            #   "key": {
            #     "PlayerUId": {
            #       "struct_type": "Guid",
            #       "struct_id": "00000000-0000-0000-0000-000000000000",
            #       "id": null,
            #       "value": "00000000-0000-0000-0000-000000000001",
            #       "type": "StructProperty"
            #     },
            #     "InstanceId": {
            #       "struct_type": "Guid",
            #       "struct_id": "00000000-0000-0000-0000-000000000000",
            #       "id": null,
            #       "value": "2784e5b0-4a38-d8b1-0ffe-4fb41d31e6ca",
            #       "type": "StructProperty"
            #     },
            #     "DebugName": {
            #       "id": null,
            #       "value": "",
            #       "type": "StrProperty"
            #     }
            #   },
            playerUId = entry["key"].get("PlayerUId", {}).get("value", "")
            # 凡是无法取到id肯定不是玩家，直接跳过
            if not playerUId:
                continue

            raw = entry["value"]["RawData"]["value"]
            save_param = raw["object"]["SaveParameter"]["value"]

            # 严格检查 IsPlayer
            is_player = False
            if "IsPlayer" in save_param:
                is_player_prop = save_param["IsPlayer"]
                if isinstance(is_player_prop, dict):
                    val = is_player_prop.get("value", False)
                    is_player = val if isinstance(val, bool) else (val == 1)

            if not is_player:
                continue

            if "LastJumpedLocation" not in save_param:
                continue

            loc = save_param["LastJumpedLocation"]["value"]
            x = float(loc["x"])
            y = float(loc["y"])
            z = float(loc["z"])
            name = ""
            if "NickName" in save_param:
                name = _extract_str_value(save_param["NickName"])
            players.append((len(players), playerUId, name, x, y, z, save_param))
        except Exception:
            continue
    return players


# 根据playerUId获取这个玩家的Transform
# 游戏的存档文件，实际上分为多个文件。Level.sav里面是不包含玩家的位置和旋转的，但是有玩家的playerUId和玩家昵称。
# 在Level.sav的所在目录下，还有个Players子目录
# Players目录下的每个文件都是以玩家的playerUId去掉了`-`连字符命名的，里面包含了这个玩家的详细数据，包括位置和旋转等。
# 比如：playerUId:00000000-0000-0000-0000-000000000001,对应的文件名是：00000000000000000000000000000001.sav
# 所以我们需要根据玩家的playerUId去Players目录下找到对应的文件，读取这个文件，解析出玩家的Transform数据。
# 因此这个方法需要2个参数，一个是playerUId，另一个是Level.sav所在的目录路径（因为我们需要从这个目录下的Players子目录去找对应的玩家文件）。
# 然后，返回一个rotaion和location的元组，rotation是一个字典，包含x,y,z,w四个键，location也是一个字典，包含x,y,z三个键。如果读取失败或者数据不完整，就返回None。
def _get_player_transform(playerUId: str, level_sav_dir: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    根据玩家的 playerUId 和 Level.sav 所在目录，读取对应玩家文件并提取 Transform 数据。

    Args:
        playerUId: 玩家唯一标识符。
        level_sav_dir: Level.sav 所在目录路径。
    Returns:
        返回一个rotaion和location的元组，rotation是一个字典，包含x,y,z,w四个键，location也是一个字典，包含x,y,z三个键。如果读取失败或者数据不完整，就返回None。
    """
    try:
        # playerUId 是个 UUID对象，不是字符串，所以我们需要把它转换成字符串，并去掉连字符，然后加上.sav后缀，才能得到玩家文件的名字。
        player_file_name = str(playerUId).replace("-", "") + ".sav"
        player_file_path = os.path.join(level_sav_dir, "Players", player_file_name)
        print(f"Looking for player file: {player_file_name} in {player_file_path}")

        if not os.path.exists(player_file_path):
            return None

        with open(player_file_path, "rb") as f:
            sav_data = f.read()

        # 解压 .sav 为 GVAS 格式数据
        gvas_data, _ = decompress_sav_to_gvas(sav_data)
        # 解析 GVAS 文件
        gvas_file = GvasFile.read(gvas_data, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
        # 转换为字典格式
        data = gvas_file.dump()

        # 首先，要取SaveData
        SaveData = data["properties"]["SaveData"]["value"]
        # 然后，验证我们传入的参数playerUId和SaveData里面的玩家列表是否匹配
        id_in_sav = SaveData.get("PlayerUId", {}).get("value", "")
        if id_in_sav != playerUId:
            return None
        
        # 接着获取玩家的LastTransform
        lastTransform = SaveData.get("LastTransform", {}).get("value", None)
        # 然后，根据这个transfrom获取Translation和Rotation
        # transform的结构：
        # "LastTransform": {
        #   "struct_type": "Transform",
        #   "struct_id": "00000000-0000-0000-0000-000000000000",
        #   "id": null,
        #   "value": {
        #     "Rotation": {
        #       "struct_type": "Quat",
        #       "struct_id": "00000000-0000-0000-0000-000000000000",
        #       "id": null,
        #       "value": {
        #         "x": -0.0,
        #         "y": 0.0,
        #         "z": -0.9988009383122595,
        #         "w": 0.04895595598647846
        #       },
        #       "type": "StructProperty"
        #     },
        #     "Translation": {
        #       "struct_type": "Vector",
        #       "struct_id": "00000000-0000-0000-0000-000000000000",
        #       "id": null,
        #       "value": {
        #         "x": -127457.88411633775,
        #         "y": -96120.70417360144,
        #         "z": -1952.8285997471578
        #       },
        #       "type": "StructProperty"
        #     }
        #   },
        #   "type": "StructProperty"
        # }
        rotation = lastTransform.get("Rotation", {}).get("value", None)
        location = lastTransform.get("Translation", {}).get("value", None)

        return rotation, location

    except Exception as e:
        print(f"Error reading player transform: {e}")
        return None

def _get_player_yaw(save_param: Dict[str, Any]) -> float:
    """
    从玩家的 RootTransform.rotation 提取水平面朝角度（Yaw），返回弧度。

    Args:
        save_param: 玩家的 SaveParameter 字典。

    Returns:
        面朝方向的弧度值。若缺失则返回 0.0。
    """
    if "RootTransform" not in save_param:
        return 0.0
    transform = save_param["RootTransform"]["value"]
    if "rotation" not in transform:
        return 0.0
    rot = transform["rotation"]
    x = float(rot.get("x", 0))
    y = float(rot.get("y", 0))
    z = float(rot.get("z", 0))
    w = float(rot.get("w", 1))
    yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    return yaw


# ============================================================================
# 存档扫描功能
# ============================================================================

REQUIRED_TEMPLATES = {
    "SF_foundation": "SF_foundation",
    "SF_wall": "SF_wall",
    "Glass_pillars": "Glass_pillars",
    "Glass_wall": "Glass_wall",
}


def scan_save_file(save_file_path: str) -> Dict[str, Any]:
    """
    扫描存档文件，检查必需模板是否存在，并提取所有玩家列表。

    Args:
        save_file_path: 存档文件路径。

    Returns:
        结果字典：
        {
            "success": bool,
            "templates_found": {template_id: bool, ...},
            "templates_missing": [template_id, ...],
            "players": [(index, nickname), ...],
            "message": str,
        }
    """
    result: Dict[str, Any] = {
        "success": False,
        "templates_found": {},
        "templates_missing": [],
        "players": [],
        "message": "",
    }

    try:
        if not os.path.exists(save_file_path):
            result["message"] = f"存档文件不存在: {save_file_path}"
            return result

        with open(save_file_path, "rb") as f:
            sav_data = f.read()

        gvas_data, _ = decompress_sav_to_gvas(sav_data)
        gvas_file = GvasFile.read(gvas_data, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
        data = gvas_file.dump()

        # 检查模板
        for template_id, display_name in REQUIRED_TEMPLATES.items():
            found = _find_template(data, template_id) is not None
            result["templates_found"][template_id] = found
            if not found:
                result["templates_missing"].append(display_name)

        # 提取玩家列表
        # 玩家列表，每个元素为 (index, playerUId, nickname, x, y, z, save_param)。
        all_players = _find_all_players(data)
        result["players"] = [(idx, playerUId, name) for idx, playerUId, name, _, _, _, _ in all_players]

        # 判断状态
        if result["templates_missing"]:
            result["success"] = False
            result["message"] = f"Missing templates: {', '.join(result['templates_missing'])}"
        elif not result["players"]:
            result["success"] = False
            result["message"] = "No player found in save file"
        else:
            result["success"] = True
            result["message"] = f"Found {len(result['players'])} players, all templates ready"

    except Exception as e:
        result["message"] = f"Error scanning save: {e}"

    return result


# ============================================================================
# 核心执行引擎
# ============================================================================

def generate_pixel_art(
    save_file_path: str,
    image_path: str,
    max_width: int = 120,
    max_height: int = 120,
    foundation_style: str = "sf",
    wall_style: str = "sf",
    pillar_style: str = "glass",
    pillar_position: str = "back",
    pillar_height: int = 1,
    wall_side: str = "left",
    use_linear_colorspace: bool = True,
    brightness: float = 0.8,
    saturation: float = 1.2,
    contrast: float = 1.2,
    player_index: int = 0,
    log_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    执行 Pixel Art 广告牌生成流程。

    这是本模块的主入口函数。所有参数与原始脚本的配置变量一一对应。
    执行过程中通过 log_callback 输出日志，不直接打印到控制台。

    Args:
        save_file_path: 输入存档文件路径。
        image_path: 输入图片路径。
        max_width: 图片最大宽度限制。
        max_height: 图片最大高度限制。
        foundation_style: 地基风格键名。
        wall_style: 墙壁风格键名（不允许 japanese）。
        pillar_style: 立柱风格键名。
        pillar_position: "front" 或 "back"。
        pillar_height: 立柱层数（0 表示直接从地基开始）。
        wall_side: "left" 或 "right"。
        use_linear_colorspace: 是否启用 sRGB→Linear 转换。
        brightness: 亮度倍数。
        saturation: 饱和度倍数。
        contrast: 对比度倍数。
        player_index: 要生成广告牌的目标玩家索引（0-based）。
        log_callback: 可选的日志回调函数，接收单行字符串。

    Returns:
        结果字典，包含 success (bool)、message (str)、stats (dict) 等字段。

    Raises:
        FileNotFound: 输入文件不存在。
        NoPlayerError: 存档中未找到玩家。
        MissingTemplateError: 缺少必要的建筑模板。
    """

    def log(msg: str) -> None:
        """内部日志辅助函数，优先使用回调，否则回退到 print。"""
        if log_callback:
            log_callback(msg)
        else:
            print(msg, flush=True)

    log("=" * 60)
    log("Palworld Pixel Art Generator")
    log("=" * 60)

    # ------------------------------------------------------------------
    # 1. 验证输入文件
    # ------------------------------------------------------------------
    if not os.path.exists(save_file_path):
        raise FileNotFound(f"Save file not found: {save_file_path}")
    if not os.path.exists(image_path):
        raise FileNotFound(f"Image file not found: {image_path}")

    # ------------------------------------------------------------------
    # 2. 读取并缩放图片
    # ------------------------------------------------------------------
    log(f"[0/6] Loading image: {image_path}")
    img = Image.open(image_path)
    orig_width, orig_height = img.size
    log(f"  Original size: {orig_width} x {orig_height}")

    img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    img_width, img_height = img.size
    if img_width != orig_width or img_height != orig_height:
        log(f"  Resized: {img_width} x {img_height} (limit {max_width}x{max_height})")
    else:
        log(f"  No resize needed (within limits)")

    img_rgba = img.convert("RGBA")
    pixels = img_rgba.load()

    # 统计透明/不透明像素
    opaque_count = 0
    transparent_count = 0
    for y in range(img_height):
        for x in range(img_width):
            _, _, _, a = pixels[x, y]
            if a > 128:
                opaque_count += 1
            else:
                transparent_count += 1
    log(f"  Opaque pixels: {opaque_count}")
    log(f"  Transparent pixels: {transparent_count} (will use black-coated glass walls)")

    foundation_count = img_width
    wall_height = img_height

    # ------------------------------------------------------------------
    # 3. 打印生成参数摘要
    # ------------------------------------------------------------------
    log("")
    log(f"{'='*60}")
    log("Configuration:")
    log(f"{'='*60}")
    log(f"Input save: {save_file_path}")
    log(f"Image: {image_path}")
    log(f"Original size: {orig_width} x {orig_height}")
    log(f"Scaled size: {img_width} x {img_height}")
    log(f"Foundations: {foundation_count} (determined by image width)")
    log(f"Wall height: {wall_height} rows (determined by image height)")
    log(f"Wall side: {wall_side}")
    log(f"Foundation style: {foundation_style} ({BUILDING_STYLES[foundation_style]['foundation']})")
    log(f"Wall style: {wall_style} ({BUILDING_STYLES[wall_style]['wall']})")
    log(f"Add pillars: {'Yes' if pillar_height > 0 else 'No'}")
    if pillar_height > 0:
        log(f"Pillar style: {pillar_style} ({BUILDING_STYLES[pillar_style]['pillar']})")
        log(f"Pillar position: {pillar_position}")
        log(f"Pillar height: {pillar_height} layers")
    log(f"Color adjustment: Brightness={brightness}, Saturation={saturation}, Contrast={contrast}")
    log(f"Colorspace: {'sRGB -> Linear' if use_linear_colorspace else 'sRGB direct'}")
    log(f"Transparent pixels: Use black-coated Glass_wall")
    log("")

    # ------------------------------------------------------------------
    # 4. 读取并解析存档
    # ------------------------------------------------------------------
    log("[1/6] Reading save file...")
    with open(save_file_path, "rb") as f:
        sav_data = f.read()

    log("[2/6] Decompressing save...")
    gvas_data, save_type = decompress_sav_to_gvas(sav_data)

    log("[3/6] Parsing GVAS data...")
    gvas_file = GvasFile.read(gvas_data, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
    data = gvas_file.dump()

    # ------------------------------------------------------------------
    # 5. 查找玩家（支持按索引选择）
    # ------------------------------------------------------------------
    log("[4/6] Looking up player...")
    # 玩家列表，每个元素为 (index, playerUId, nickname, x, y, z, save_param)。
    all_players = _find_all_players(data)
    if not all_players:
        raise NoPlayerError("No player with IsPlayer=True found in save file")

    # 优先使用指定的 player_index
    selected_player = None
    fallback_name = ""
    if 0 <= player_index < len(all_players):
        selected_player = all_players[player_index]
    else:
        selected_player = all_players[0]
        fallback_name = selected_player[1]
        log(f"  [WARN] Player index {player_index} not found, falling back to first player: {fallback_name}")

    _, playerUId, name, px, py, pz, save_param = selected_player
    log(f"  Using player: {name} (index {player_index if 0 <= player_index < len(all_players) else 0})")
    log(f"  Player UId: {playerUId}")


    # 获取玩家的精确位置和旋转
    player_yaw = 0.0
    log(f"  Attempting to load player transform from Players folder using playerUId...")
    transform = _get_player_transform(playerUId, os.path.dirname(save_file_path))
    if transform:
        rotation, location = transform
        if location:
            px = float(location.get("x", px))
            py = float(location.get("y", py))
            pz = float(location.get("z", pz))
        if rotation:
            player_yaw = math.atan2(2.0 * (rotation["w"] * rotation["z"] + rotation["x"] * rotation["y"]), 1.0 - 2.0 * (rotation["y"] * rotation["y"] + rotation["z"] * rotation["z"]))
            log(f"  [INFO] Player transform loaded from file: X={px:.2f}, Y={py:.2f}, Z={pz:.2f}, Yaw={player_yaw * 180.0 / math.pi:.1f}°")
        else:
            log(f"  [WARN] Player rotation not found in player file under players folder, using SaveParameter RootTransform.rotation")
            player_yaw = _get_player_yaw(save_param)
            log(f"  Facing: Yaw={player_yaw * 180.0 / math.pi:.1f}°")
    else:
        log(f"  [WARN] Player transform not found in player file under players folder, using SaveParameter RootTransform")
        log(f"  Position: X={px:.2f}, Y={py:.2f}, Z={pz:.2f}")
        player_yaw = _get_player_yaw(save_param)
        log(f"  Facing: Yaw={player_yaw * 180.0 / math.pi:.1f}°")

    # ------------------------------------------------------------------
    # 6. 计算旋转和偏移角度
    # ------------------------------------------------------------------
    foundation_angle = player_yaw
    qz_f = math.sin(foundation_angle / 2)
    qw_f = math.cos(foundation_angle / 2)

    wall_rotation_angle = foundation_angle + math.pi / 2
    qz_w = math.sin(wall_rotation_angle / 2)
    qw_w = math.cos(wall_rotation_angle / 2)

    if wall_side == "left":
        wall_offset_angle = player_yaw - math.pi / 2
    else:
        wall_offset_angle = player_yaw + math.pi / 2

    log(f"  Foundation direction: {foundation_angle * 180 / math.pi:.1f}°")
    log(f"  Wall rotation: {wall_rotation_angle * 180 / math.pi:.1f}° (perpendicular to foundations)")
    log(f"  Wall offset: {wall_offset_angle * 180 / math.pi:.1f}° ({wall_side})")

    # ------------------------------------------------------------------
    # 7. 查找建筑模板
    # ------------------------------------------------------------------
    foundation_template = _find_template(data, BUILDING_STYLES[foundation_style]["foundation"])
    wall_template = _find_template(data, BUILDING_STYLES[wall_style]["wall"])
    glass_wall_template = _find_template(data, BUILDING_STYLES["glass"]["wall"])
    pillar_template = _find_template(data, BUILDING_STYLES[pillar_style]["pillar"]) if pillar_height > 0 else None

    if not foundation_template:
        raise MissingTemplateError(f"Foundation template not found: {BUILDING_STYLES[foundation_style]['foundation']}")
    if not wall_template:
        raise MissingTemplateError(f"Wall template not found: {BUILDING_STYLES[wall_style]['wall']}")
    if not glass_wall_template:
        raise MissingTemplateError("Glass_wall template not found, please build one glass wall first")
    if pillar_height > 0 and not pillar_template:
        log("  [WARN] Pillar template not found, skipping pillars")
        pillar_height = 0

    # ------------------------------------------------------------------
    # 8. 生成建筑
    # ------------------------------------------------------------------
    map_objects = data["properties"]["worldSaveData"]["value"]["MapObjectSaveData"]["value"]["values"]
    old_count = len(map_objects)

    total_walls = 0
    total_glass_walls = 0
    total_pillars = foundation_count * pillar_height if pillar_height > 0 else 0

    log(f"  Generating {foundation_count} {BUILDING_STYLES[foundation_style]['foundation']} foundations")
    if pillar_height > 0:
        log(f"  Generating {total_pillars} {BUILDING_STYLES[pillar_style]['pillar']} pillars ({pillar_height} layers x {foundation_count} cols, {pillar_position} corner)")
    log(f"  Generating wall pixel art ({img_width} cols x {img_height} rows)...")
    log("")

    # 预计算黑色玻璃墙的 paint_b64
    black_paint_b64 = _make_paint_b64(0.0, 0.0, 0.0, 1.0)

    for col in range(foundation_count):
        # 地基位置（沿玩家面朝方向）
        fi_x = px + col * FOUNDATION_SIZE * math.cos(foundation_angle)
        fi_y = py + col * FOUNDATION_SIZE * math.sin(foundation_angle)
        fi_z = pz

        if col == 0 or col == foundation_count - 1:
            log(f"  Col {col+1}/{foundation_count}: ({fi_x:.2f}, {fi_y:.2f})")

        # 创建地基
        foundation = _clone_foundation(foundation_template, fi_x, fi_y, fi_z, qz_f, qw_f)
        map_objects.append(foundation)

        # 生成立柱堆叠
        if pillar_height > 0 and pillar_template:
            direction_sign = 1.0 if pillar_position == "front" else -1.0
            left_x = FOUNDATION_HALF_SIZE * math.cos(wall_offset_angle)
            left_y = FOUNDATION_HALF_SIZE * math.sin(wall_offset_angle)
            front_x = direction_sign * FOUNDATION_HALF_SIZE * math.cos(foundation_angle)
            front_y = direction_sign * FOUNDATION_HALF_SIZE * math.sin(foundation_angle)
            pi_x = fi_x + left_x + front_x
            pi_y = fi_y + left_y + front_y

            for h in range(pillar_height):
                pi_z = fi_z + h * WALL_HEIGHT_UNIT
                pillar = _clone_pillar(pillar_template, pi_x, pi_y, pi_z, qz_f, qw_f)
                map_objects.append(pillar)

        # 墙壁从立柱顶端（或地基）开始
        wall_base_z = fi_z + pillar_height * WALL_HEIGHT_UNIT

        for row in range(wall_height):
            # 图片坐标映射：row=0 对应底层（图片底部），row=最大 对应顶层（图片顶部）
            pixel_y = img_height - 1 - row
            pixel_x = col
            r, g, b, a = pixels[pixel_x, pixel_y]

            # 计算墙壁位置
            wi_x = fi_x + WALL_OFFSET * math.cos(wall_offset_angle)
            wi_y = fi_y + WALL_OFFSET * math.sin(wall_offset_angle)
            wi_z = wall_base_z + row * WALL_HEIGHT_UNIT

            if a <= 128:
                # 透明像素：黑色涂层玻璃墙
                wall = _clone_wall(glass_wall_template, wi_x, wi_y, wi_z, qz_w, qw_w, black_paint_b64)
                map_objects.append(wall)
                total_glass_walls += 1
            else:
                # 不透明像素：调节颜色后写入
                paint_r, paint_g, paint_b = _apply_color_adjustment(
                    r, g, b, brightness, saturation, contrast, use_linear_colorspace
                )
                paint_b64 = _make_paint_b64(paint_r, paint_g, paint_b)
                wall = _clone_wall(wall_template, wi_x, wi_y, wi_z, qz_w, qw_w, paint_b64)
                map_objects.append(wall)
                total_walls += 1

    added_count = foundation_count + total_walls + total_glass_walls + total_pillars
    log(f"  Map objects: {old_count} -> {len(map_objects)} (+{added_count})")
    log(f"    - {BUILDING_STYLES[foundation_style]['foundation']} foundations: +{foundation_count}")
    log(f"    - {BUILDING_STYLES[wall_style]['wall']} walls: +{total_walls} (opaque pixels)")
    log(f"    - Glass_wall glass walls: +{total_glass_walls} (transparent pixels, black coat)")
    if pillar_height > 0:
        log(f"    - {BUILDING_STYLES[pillar_style]['pillar']} pillars: +{total_pillars} ({pillar_height} layers support)")

    # ------------------------------------------------------------------
    # 9. 保存修改后的存档
    # ------------------------------------------------------------------
    log("[5/6] Saving save file...")
    gvas_loaded = GvasFile.load(data)
    output_gvas = gvas_loaded.write(PALWORLD_CUSTOM_PROPERTIES)
    output_sav = compress_gvas_to_sav(output_gvas, save_type)

    # 重命名原文件，避免覆盖
    try:
        original_file_path = _backup_original_save(save_file_path, log)
    except Exception as e:
        raise PixelArtError(f"Failed to backup original save file: {e}") from e


    # 使用原文件的路径作为输出路径，因为原文件已经改名了
    with open(save_file_path, "wb") as f:
        f.write(output_sav)

    log("")
    log("=" * 60)
    log("Summary:")
    log("=" * 60)
    log(f"Pixel Art billboard generated:")
    log(f"  - Original image: {orig_width} x {orig_height}")
    log(f"  - Scaled: {img_width} x {img_height}")
    log(f"  - Foundations: {foundation_count} cols, along player's facing direction")
    log(f"  - Pillars: {pillar_height} layers, elevating the billboard")
    log(f"  - Normal walls: {total_walls} (opaque pixels, color adjusted)")
    log(f"  - Glass walls: {total_glass_walls} (transparent pixels, black coat, structural support)")
    log(f"  - Image upright (top pixels at the top)")
    log(f"  - Walls on player's {wall_side} side")
    log(f"  - Color processing: Brightness={brightness}, Saturation={saturation}, Contrast={contrast}")
    log(f"  - Colorspace: {'sRGB->Linear' if use_linear_colorspace else 'sRGB direct'}")
    log("")
    log(f"Original file backed up to: {original_file_path}")
    log(f"Output file: {save_file_path}")
    log("Done!")
    log("=" * 60)

    return {
        "success": True,
        "message": "Pixel Art billboard generated successfully",
        "stats": {
            "original_width": orig_width,
            "original_height": orig_height,
            "scaled_width": img_width,
            "scaled_height": img_height,
            "foundations": foundation_count,
            "walls": total_walls,
            "glass_walls": total_glass_walls,
            "pillars": total_pillars,
            "pillar_height": pillar_height,
        },
    }



def remove_pixel_art(
    save_file_path: str,
    foundation_style: str = "sf",
    wall_style: str = "sf",
    pillar_style: str = "glass",
    remove_radius: float = 20000.0,
    player_index: int = 0,
    log_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    删除玩家附近指定半径范围内的 Pixel Art 广告牌。

    所有参数与原始脚本的配置变量一一对应。
    执行过程中通过 log_callback 输出日志，不直接打印到控制台。

    Args:
        save_file_path: 输入存档文件路径。
        foundation_style: 地基风格键名。
        wall_style: 墙壁风格键名（不允许 japanese）。
        pillar_style: 立柱风格键名。
        remove_radius: 删除半径，单位与游戏坐标相同（厘米）。
        player_index: 要生成广告牌的目标玩家索引（0-based）。
        log_callback: 可选的日志回调函数，接收单行字符串。

    Returns:
        结果字典，包含 success (bool)、message (str)、stats (dict) 等字段。

    Raises:
        FileNotFound: 输入文件不存在。
        NoPlayerError: 存档中未找到玩家。
    """

    def log(msg: str) -> None:
        """内部日志辅助函数，优先使用回调，否则回退到 print。"""
        if log_callback:
            log_callback(msg)
        else:
            print(msg, flush=True)

    def calculate_distance_xy(x1, y1, x2, y2):
        """内部日志辅助函数，计算XY平面水平距离（忽略Z轴高度）"""
        return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)

    log("=" * 60)
    log("Palworld Pixel Art Generator: Remove Mode")
    log("=" * 60)

    result: Dict[str, Any] = {
        "success": False,
        "message": "",
        "stats": {},
    }

    # ------------------------------------------------------------------
    # 1. 验证输入文件
    # ------------------------------------------------------------------
    if not os.path.exists(save_file_path):
        raise FileNotFound(f"Save file not found: {save_file_path}")


    # ------------------------------------------------------------------
    # 3. 打印生成参数摘要
    # ------------------------------------------------------------------
    log("")
    log(f"{'='*60}")
    log("Configuration:")
    log(f"{'='*60}")
    log(f"Input save: {save_file_path}")
    log(f"Foundation style: {foundation_style} ({BUILDING_STYLES[foundation_style]['foundation']})")
    log(f"Wall style: {wall_style} ({BUILDING_STYLES[wall_style]['wall']})")
    log(f"Pillar style: {pillar_style} ({BUILDING_STYLES[pillar_style]['pillar']})")
    log(f"Remove radius: {remove_radius} cm")
    log("")

    # ------------------------------------------------------------------
    # 4. 读取并解析存档
    # ------------------------------------------------------------------
    log("[1/6] Reading save file...")
    with open(save_file_path, "rb") as f:
        sav_data = f.read()

    log("[2/6] Decompressing save...")
    gvas_data, save_type = decompress_sav_to_gvas(sav_data)

    log("[3/6] Parsing GVAS data...")
    gvas_file = GvasFile.read(gvas_data, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
    data = gvas_file.dump()

    # ------------------------------------------------------------------
    # 5. 查找玩家（支持按索引选择）
    # ------------------------------------------------------------------
    log("[4/6] Looking up player...")
    # 玩家列表，每个元素为 (index, playerUId, nickname, x, y, z, save_param)。
    all_players = _find_all_players(data)
    if not all_players:
        raise NoPlayerError("No player with IsPlayer=True found in save file")

    # 优先使用指定的 player_index
    selected_player = None
    fallback_name = ""
    if 0 <= player_index < len(all_players):
        selected_player = all_players[player_index]
    else:
        selected_player = all_players[0]
        fallback_name = selected_player[1]
        log(f"  [WARN] Player index {player_index} not found, falling back to first player: {fallback_name}")

    _, playerUId, name, px, py, pz, _ = selected_player
    log(f"  Using player: {name} (index {player_index if 0 <= player_index < len(all_players) else 0})")
    log(f"  Player UId: {playerUId}")


    # 获取玩家的精确位置
    log(f"  Attempting to load player transform from Players folder using playerUId...")
    transform = _get_player_transform(playerUId, os.path.dirname(save_file_path))
    if transform:
        rotation, location = transform
        if location:
            px = float(location.get("x", px))
            py = float(location.get("y", py))
            pz = float(location.get("z", pz))
    else:
        # 删除模式，必须要有准确的玩家位置。位置获取失败时无法判断哪些建筑需要被删除，因此直接报错而不是继续执行。
        log(f"  [ERROR] Player transform not found in player file under players folder, cannot determine player position for removal")
        raise NoPlayerError("Player transform not found in player file under players folder")
        
    # ------------------------------------------------------------------
    # 6. 遍历 MapObjectSaveData，删除匹配的建筑
    # ------------------------------------------------------------------
    # 需要删除的 MapObjectId 列表（严格匹配大小写）
    TARGET_MAP_OBJECT_IDS = {
        BUILDING_STYLES["glass"]['wall'],      # 玻璃墙
        BUILDING_STYLES[wall_style]['wall'],  # 墙壁（根据选择的风格）
        BUILDING_STYLES[pillar_style]['pillar'],  # 立柱（根据选择的风格）
        BUILDING_STYLES[foundation_style]['foundation'],  # 地基（根据选择的风格）
    }

    try:
        map_objects = data["properties"]["worldSaveData"]["value"]["MapObjectSaveData"]["value"]["values"]
    except KeyError as e:
        log(f"Error: Can not find MapObjectSaveData: {e}")
        result["message"] = "MapObjectSaveData not found in save file"
        return result

    original_count = len(map_objects)
    log(f"\nScanning {original_count} map objects...")

    new_map_objects = []
    deleted_stats = {}
    deleted_total = 0

    for i, obj in enumerate(map_objects):
        map_object_id = obj.get("MapObjectId", {}).get("value", "")

        # 检查是否在目标列表中
        if map_object_id not in TARGET_MAP_OBJECT_IDS:
            new_map_objects.append(obj)
            continue

        # 提取建筑位置
        try:
            raw_data = obj["Model"]["value"]["RawData"]["value"]
            translation = raw_data["initital_transform_cache"]["translation"]
            bx = float(translation["x"])
            by = float(translation["y"])
            bz = float(translation["z"])
        except (KeyError, TypeError, ValueError):
            # 无法读取位置，保留
            new_map_objects.append(obj)
            continue

        # 计算距离
        distance = calculate_distance_xy(px, py, bx, by)

        # 判断是否在删除范围内
        if distance <= remove_radius:
            deleted_stats[map_object_id] = deleted_stats.get(map_object_id, 0) + 1
            deleted_total += 1
            # if deleted_total <= 10 or deleted_total % 500 == 0:
            #     log(f"  Remove [{i}] {map_object_id} Distance={distance:.2f} Location=({bx:.2f}, {by:.2f}, Z={bz:.2f})")
        else:
            new_map_objects.append(obj)

    log(f"\nRemove Stats:")
    log(f"  Original Count: {original_count}")
    log(f"  Deleted Count: {deleted_total}")
    log(f"  Remaining Count: {len(new_map_objects)}")
    for obj_id, count in sorted(deleted_stats.items()):
        log(f"  - {obj_id}: {count}")

    if new_map_objects is not None:
        # 更新数据
        data["properties"]["worldSaveData"]["value"]["MapObjectSaveData"]["value"]["values"] = new_map_objects
    else:
        log("Error: map objects is None after removing, cannot update MapObjectSaveData")
        result["message"] = "Internal error: new_map_objects is None"
        return result

    # ------------------------------------------------------------------
    # 9. 保存修改后的存档
    # ------------------------------------------------------------------
    log("[5/6] Saving save file...")
    gvas_loaded = GvasFile.load(data)
    output_gvas = gvas_loaded.write(PALWORLD_CUSTOM_PROPERTIES)
    output_sav = compress_gvas_to_sav(output_gvas, save_type)

    # 重命名原文件，避免覆盖
    try:
        original_file_path = _backup_original_save(save_file_path, log)
    except Exception as e:
        log(f"Error backing up original save file: {e}")
        result["message"] = "Failed to backup original save file"
        return result
    
    # 使用原文件的路径作为输出路径，因为原文件已经改名了
    with open(save_file_path, "wb") as f:
        f.write(output_sav)

    log("")
    log("=" * 60)
    log(f"Original file backed up to: {original_file_path}")
    log(f"Output file: {save_file_path}")
    log("Done!")
    log("=" * 60)

    return {
        "success": True,
        "message": "Pixel Art objects removed successfully",
        "stats": {"original": original_count, "deleted": deleted_total, "remaining": len(new_map_objects)},
    }
