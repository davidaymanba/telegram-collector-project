"""Text cleaning and Arabic normalisation.

`clean_text` keeps the text readable (it is what we store and show). `normalize_arabic` is
lossy and only used for matching/searching: it folds letter variants so that
"الإمتحان", "الامتحان" and "الامتحـــان" all compare equal.
"""

from __future__ import annotations

import re
import unicodedata

_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"
_ALEF = re.compile(r"[آأإٱٲٳ]")  # آ أ إ ٱ ...
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩﻿]")
_SPACES = re.compile(r"[ \t  - 　]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_WORD_SEP = re.compile(r"[_\-.,;:!?()\[\]{}/\\|\"'«»،؛؟…]+")


def clean_text(text: str) -> str:
    """Unicode NFC, strip control/bidi characters, collapse spaces, keep paragraph breaks."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(_TATWEEL, "")
    text = _CONTROL.sub("", text)
    lines = [_SPACES.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    return _BLANK_LINES.sub("\n\n", text).strip()


def normalize_arabic(text: str) -> str:
    """Aggressive folding for search/classification (never stored as the display text)."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _TASHKEEL.sub("", text).replace(_TATWEEL, "")
    text = _ALEF.sub("ا", text)          # → ا
    text = text.replace("ى", "ي")    # ى → ي
    text = text.replace("ة", "ه")    # ة → ه
    text = text.replace("ؤ", "و")    # ؤ → و
    text = text.replace("ئ", "ي")    # ئ → ي
    text = text.translate(_ARABIC_DIGITS)
    text = _CONTROL.sub("", text)
    return _SPACES.sub(" ", text.replace("\n", " ")).strip()


def normalize_for_match(text: str) -> str:
    """normalize_arabic + casefold + treat punctuation/underscores as spaces."""
    text = normalize_arabic(text).casefold()
    text = _WORD_SEP.sub(" ", text)
    return _SPACES.sub(" ", text).strip()
