from __future__ import annotations

import unicodedata

import pytest

from app.processing.text import clean_text, normalize_arabic, normalize_for_match


@pytest.mark.parametrize("raw, expected", [
    ("أحمد", "احمد"),
    ("إمتحان", "امتحان"),
    ("آخر", "اخر"),
    ("ٱلكتاب", "الكتاب"),
    ("مستوى", "مستوي"),
    ("محاضرة", "محاضره"),
    ("الامتحـــان", "الامتحان"),            # tatweel
    ("مُحَاضَرَةٌ", "محاضره"),               # tashkeel
    ("مسؤول", "مسوول"),
    ("٢٠٢٦", "2026"),                        # Arabic-Indic digits
    ("  قواعد\t\tالبيانات \n SQL ", "قواعد البيانات SQL"),
])
def test_normalize_arabic(raw: str, expected: str) -> None:
    assert normalize_arabic(raw) == expected


def test_variants_compare_equal() -> None:
    forms = ["الإمتحان النهائى", "الامتحان النهائي", "الأمتحـان النّهائي"]
    assert len({normalize_arabic(f) for f in forms}) == 1


def test_normalize_for_match_casefolds_and_splits_punctuation() -> None:
    assert normalize_for_match("DB101_Lecture-3.PDF") == "db101 lecture 3 pdf"
    assert normalize_for_match("محاضرة،قواعد؛بيانات") == "محاضره قواعد بيانات"


def test_clean_text_keeps_paragraphs_and_readability() -> None:
    raw = "Line  one\r\n\r\n\r\n\r\nمحاضـــرة‏  2\x00\n"
    out = clean_text(raw)
    assert out == "Line one\n\nمحاضرة 2"


def test_clean_text_nfc() -> None:
    nfd = unicodedata.normalize("NFD", "é")
    assert clean_text(nfd) == "é"


def test_empty() -> None:
    assert clean_text("") == "" and normalize_arabic("") == ""
