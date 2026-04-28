"""
国际化 (i18n) 模块
负责加载语言文件、提供翻译文本、管理语言切换监听器。
所有界面文字和日志内容都通过此模块获取，以支持多语言即时切换。
"""

import json
from importlib import resources
from pathlib import Path
from typing import Callable, List, Dict

# 默认语言代码
DEFAULT_LANG = "en"

# 语言文件所在目录
LANG_DIR = Path(__file__).parent

# 语言代码到显示名称的映射（用于下拉列表）
LANGUAGE_OPTIONS = {
    "en": "lang_en",
    "zh_CN": "lang_zh",
    "ja": "lang_ja",
}




class I18n:
    """
    国际化引擎类。

    负责加载 JSON 翻译文件，在内存中维护当前语言的翻译字典。
    支持注册监听器，当语言切换时通知所有 UI 组件刷新。
    """

    def __init__(self, lang_code: str = None):
        """
        初始化 i18n 引擎。

        Args:
            lang_code: 初始语言代码，如 "en", "zh_CN", "ja"。若为 None 则使用默认语言。
        """
        self._lang = (lang_code or DEFAULT_LANG).strip()
        self._translations: Dict[str, Dict[str, str]] = {}
        self._listeners: List[Callable[[], None]] = []
        self._load_all_translations()

    # def _load_all_translations(self) -> None:
    #     """加载语言目录下所有 .json 翻译文件到内存。"""
    #     for json_file in LANG_DIR.glob("*.json"):
    #         lang_code = json_file.stem
    #         try:
    #             with open(json_file, "r", encoding="utf-8") as f:
    #                 self._translations[lang_code] = json.load(f)
    #         except Exception as e:
    #             print(f"[i18n] 警告: 无法加载语言文件 {json_file}: {e}")


    def _load_all_translations(self) -> None:
        """使用 importlib.resources 加载包内所有 .json 翻译文件（兼容打包）。"""
        pkg = __package__  # i18n 包
        try:
            for res in resources.files(pkg).iterdir():
                if res.suffix == ".json":
                    lang_code = res.stem
                    try:
                        text = res.read_text(encoding="utf-8")
                        self._translations[lang_code] = json.loads(text)
                    except Exception as e:
                        print(f"[i18n] 警告: 无法加载语言资源 {res}: {e}")
        except Exception as e:
            print(f"[i18n] 资源加载错误: {e}")

    def get(self, key: str, **kwargs) -> str:
        """
        获取指定 key 的翻译文本。

        如果当前语言中不存在该 key，则回退到默认语言；
        如果默认语言也不存在，则返回 key 本身。

        Args:
            key: 翻译键名。
            **kwargs: 格式化参数，用于替换文本中的 {placeholder}。

        Returns:
            翻译后的字符串。
        """
        text = self._translations.get(self._lang, {}).get(key)
        if text is None:
            # 回退到默认语言
            text = self._translations.get(DEFAULT_LANG, {}).get(key, key)
        return text.format(**kwargs) if kwargs else text

    def set_language(self, lang_code: str) -> None:
        """
        切换当前语言，并通知所有已注册的监听器刷新界面。

        Args:
            lang_code: 目标语言代码。
        """
        lang_code = lang_code.strip()
        if lang_code == self._lang:
            return
        if lang_code not in self._translations:
            print(f"[i18n] 警告: 语言 '{lang_code}' 不存在，可用语言: {list(self._translations.keys())}")
            return
        self._lang = lang_code
        self._notify_listeners()

    def get_current_language(self) -> str:
        """返回当前语言代码。"""
        return self._lang

    def add_listener(self, callback: Callable[[], None]) -> None:
        """
        注册语言切换监听器。

        当语言发生切换时，所有监听器会被调用。UI 组件应在监听器中刷新自身的文字。

        Args:
            callback: 无参数、无返回值的回调函数。
        """
        self._listeners.append(callback)

    def _notify_listeners(self) -> None:
        """内部方法：调用所有已注册的监听器。"""
        for cb in self._listeners:
            try:
                cb()
            except Exception as e:
                print(f"[i18n] 监听器错误: {e}")

    def available_languages(self) -> List[str]:
        """返回已加载的所有语言代码列表。"""
        return list(self._translations.keys())


# 全局单例实例，在应用启动时由外部注入语言设置
translator: I18n = I18n(DEFAULT_LANG)


def t(key: str, **kwargs) -> str:
    """
    全局快捷翻译函数。

    通过此函数在任何地方获取翻译文本，无需直接引用 translator 实例。

    Args:
        key: 翻译键名。
        **kwargs: 格式化参数。

    Returns:
        翻译后的字符串。
    """
    return translator.get(key, **kwargs)
