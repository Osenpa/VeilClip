import json
import locale
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LANGUAGE_META: dict[str, dict[str, Any]] = {
    "en": {"name": "English", "native_name": "English", "rtl": False},
    "de": {"name": "German", "native_name": "Deutsch", "rtl": False},
    "fr": {"name": "French", "native_name": "Français", "rtl": False},
    "id": {"name": "Indonesian", "native_name": "Bahasa Indonesia", "rtl": False},
    "zh_CN": {"name": "Chinese (Simplified)", "native_name": "简体中文", "rtl": False},
    "ru": {"name": "Russian", "native_name": "Русский", "rtl": False},
    "ko": {"name": "Korean", "native_name": "한국어", "rtl": False},
    "ja": {"name": "Japanese", "native_name": "日本語", "rtl": False},
    "es": {"name": "Spanish", "native_name": "Español", "rtl": False},
    "ar": {"name": "Arabic", "native_name": "العربية", "rtl": True},
    "it": {"name": "Italian", "native_name": "Italiano", "rtl": False},
    "uk": {"name": "Ukrainian", "native_name": "Українська", "rtl": False},
    "tr": {"name": "Turkish", "native_name": "Türkçe", "rtl": False},
    "hi": {"name": "Hindi", "native_name": "हिन्दी", "rtl": False},
    "pt": {"name": "Portuguese", "native_name": "Português", "rtl": False},
    "pl": {"name": "Polish", "native_name": "Polski", "rtl": False},
}

_SUPPORTED_LOCALES: dict[str, str] = {code: code for code in _LANGUAGE_META}
_FALLBACK_LANGUAGE = "en"

_translator: "Translator | None" = None
_locale_dir: Path | None = None


class Translator:
    def __init__(self, locale_dir: Path, language: str = _FALLBACK_LANGUAGE) -> None:
        self._locale_dir = locale_dir
        self._strings: dict[str, Any] = {}
        self._language = _FALLBACK_LANGUAGE
        self.load(language)

    def load(self, language: str) -> bool:
        lang = _SUPPORTED_LOCALES.get(language, _FALLBACK_LANGUAGE)
        path = self._locale_dir / f"{lang}.json"

        if not path.exists():
            logger.warning("Locale file not found: %s - using fallback.", path)
            lang = _FALLBACK_LANGUAGE
            path = self._locale_dir / f"{lang}.json"

        try:
            with path.open(encoding="utf-8") as handle:
                self._strings = json.load(handle)
            self._language = lang
            logger.debug("Loaded locale: %s", path)
            return lang == language
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to load locale file %s: %s", path, exc)
            self._strings = {}
            self._language = _FALLBACK_LANGUAGE
            return False

    def get(self, key: str, **kwargs: Any) -> str:
        value = self._resolve_string(key)
        if kwargs:
            try:
                value = value.format(**kwargs)
            except KeyError as exc:
                logger.warning("Missing placeholder %s in key '%s'.", exc, key)
        return value

    def data(self, key: str, default: Any = None) -> Any:
        value = self._resolve_node(key)
        return default if value is None else value

    @property
    def language(self) -> str:
        return self._language

    def _resolve_node(self, key: str) -> Any:
        parts = key.split(".")
        node: Any = self._strings

        for part in parts:
            if not isinstance(node, dict) or part not in node:
                logger.warning("Translation key not found: '%s'", key)
                return None
            node = node[part]

        return node

    def _resolve_string(self, key: str) -> str:
        node = self._resolve_node(key)
        if not isinstance(node, str):
            logger.warning("Translation key '%s' does not resolve to a string.", key)
            return key
        return node


def init(locale_dir: Path, language: str | None = None) -> Translator:
    global _translator, _locale_dir

    _locale_dir = locale_dir
    resolved_language = language or _detect_system_language()
    _translator = Translator(locale_dir=locale_dir, language=resolved_language)
    return _translator


def get(key: str, **kwargs: Any) -> str:
    if _translator is None:
        raise RuntimeError("i18n not initialized - call i18n.init() at startup.")
    return _translator.get(key, **kwargs)


def data(key: str, default: Any = None) -> Any:
    if _translator is None:
        raise RuntimeError("i18n not initialized - call i18n.init() at startup.")
    return _translator.data(key, default=default)


def current_language() -> str:
    return _translator.language if _translator else _FALLBACK_LANGUAGE


def set_language(language: str, persist: bool = False) -> str:
    global _translator

    if _translator is None:
        if _locale_dir is None:
            raise RuntimeError("i18n not initialized - call i18n.init() first.")
        _translator = Translator(locale_dir=_locale_dir, language=language)
    else:
        _translator.load(language)

    if persist:
        try:
            from utils.config_manager import cfg as _cfg

            _cfg.set("language", _translator.language)
        except Exception as exc:
            logger.warning("Could not persist language '%s': %s", _translator.language, exc)

    return _translator.language


def available_languages() -> list[dict[str, Any]]:
    return [
        {
            "code": code,
            "name": meta["name"],
            "native_name": meta["native_name"],
            "rtl": meta["rtl"],
        }
        for code, meta in _LANGUAGE_META.items()
    ]


def language_name(code: str, native: bool = False) -> str:
    meta = _LANGUAGE_META.get(code)
    if not meta:
        return code
    return meta["native_name"] if native else meta["name"]


def is_rtl(language: str | None = None) -> bool:
    code = language or current_language()
    meta = _LANGUAGE_META.get(code, {})
    return bool(meta.get("rtl", False))


def literal(text: str) -> str:
    if not text:
        return text
    literals = data("literals", default={}) if _translator is not None else {}
    return literals.get(text, text)


def _detect_system_language() -> str:
    try:
        import os

        env_lang = os.environ.get("LANG") or os.environ.get("LANGUAGE", "")
        if env_lang:
            normalized = env_lang.replace("-", "_").split(".")[0]
            if normalized in _SUPPORTED_LOCALES:
                logger.debug("Detected language from env: %s", normalized)
                return normalized
            short_code = normalized.split("_")[0].lower()
            if short_code in _SUPPORTED_LOCALES:
                logger.debug("Detected language from env: %s", short_code)
                return short_code

        system_locale, _ = locale.getlocale()
        if system_locale:
            normalized = system_locale.replace("-", "_")
            if normalized in _SUPPORTED_LOCALES:
                logger.debug("Detected system language: %s", normalized)
                return normalized
            short_code = normalized.split("_")[0].lower()
            if short_code in _SUPPORTED_LOCALES:
                logger.debug("Detected system language: %s", short_code)
                return short_code
    except Exception as exc:
        logger.warning("Could not detect system language: %s", exc)

    logger.debug("System language not supported - using fallback: %s", _FALLBACK_LANGUAGE)
    return _FALLBACK_LANGUAGE
