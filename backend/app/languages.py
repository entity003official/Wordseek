from typing import Literal

Language = Literal["zh", "en", "ja"]
LANGUAGE_NAMES = {"zh": "Chinese", "en": "English", "ja": "Japanese"}


def language_context(preference, target=None):
    return {"native_language": LANGUAGE_NAMES.get(getattr(preference, "native_language", "zh"), "Chinese"),
            "target_language": LANGUAGE_NAMES.get(target or getattr(preference, "target_language", "en"), "English")}
