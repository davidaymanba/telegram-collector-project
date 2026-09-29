from __future__ import annotations

import os
import stat
import unicodedata
from pathlib import Path

import pytest

from app.config import Settings
from app.storage.paths import (
    StorageLayout,
    UnsafePathError,
    atomic_write,
    ensure_within,
    move_file,
    safe_filename,
    sha256_file,
    split_extension,
    write_private_text,
)


@pytest.mark.parametrize("raw, expected", [
    ("lecture 1.pdf", "lecture 1.pdf"),
    ("../../etc/passwd", "passwd"),
    ("..\\..\\windows\\system32.dll", "system32.dll"),
    ("/abs/path/file.PDF", "file.pdf"),
    ("a<b>c:d\"e|f?g*h.docx", "a_b_c_d_e_f_g_h.docx"),
    ("..", "file"),
    ("", "file"),
    (None, "file"),
    ("   .hidden.pdf  ", "hidden.pdf"),
    ("محاضرة ١ - قواعد البيانات.pdf", "محاضرة ١ - قواعد البيانات.pdf"),
    ("name‮cod.exe", "name_cod.exe"),          # RTL override attack neutralised
    ("tab\tand\nnewline.pdf", "tab_and_newline.pdf"),
])
def test_safe_filename(raw: str | None, expected: str) -> None:
    assert safe_filename(raw) == expected


def test_safe_filename_nfd_to_nfc() -> None:
    nfd = unicodedata.normalize("NFD", "مُحاضرة é.pdf")
    out = safe_filename(nfd)
    assert out == unicodedata.normalize("NFC", out)
    assert unicodedata.is_normalized("NFC", out)
    assert out.endswith(".pdf")


def test_safe_filename_truncates_utf8_bytes_keeping_extension() -> None:
    name = "قواعد " * 100 + ".pdf"
    out = safe_filename(name)
    assert len(out.encode()) <= 180
    assert out.endswith(".pdf")
    out.encode("utf-8").decode("utf-8")  # no broken multi-byte sequence


def test_split_extension() -> None:
    assert split_extension("a.b.PDF") == ("a.b", "pdf")
    assert split_extension("noext") == ("noext", "")
    assert split_extension(".bashrc") == (".bashrc", "")
    assert split_extension("weird.ext with space") == ("weird.ext with space", "")


def test_ensure_within(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    assert ensure_within(root, root / "a" / "b.txt") == (root / "a" / "b.txt").resolve()
    assert ensure_within(root, Path("a/b.txt")) == (root / "a/b.txt").resolve()
    with pytest.raises(UnsafePathError):
        ensure_within(root, root / ".." / "escape.txt")
    with pytest.raises(UnsafePathError):
        ensure_within(root, Path("/etc/passwd"))


def test_ensure_within_blocks_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "link").symlink_to(outside)
    with pytest.raises(UnsafePathError):
        ensure_within(root, root / "link" / "file.txt")


def test_layout_paths_are_confined(settings: Settings) -> None:
    layout = StorageLayout(settings)
    layout.ensure()
    p = layout.processed_path("../../DB101", "lecture", 5, "../x.pdf")
    assert p.is_relative_to(layout.processed.resolve())
    assert p.name == "5_x.pdf"
    assert layout.text_path(9).name == "9.txt"
    assert stat.S_IMODE(os.stat(layout.texts).st_mode) == 0o700


def test_atomic_write_and_private_text(tmp_path: Path) -> None:
    dest = tmp_path / "out" / "f.bin"
    with atomic_write(dest) as fh:
        fh.write(b"hello")
        assert (dest.parent / "f.bin.part").exists()
        assert not dest.exists()
    assert dest.read_bytes() == b"hello"
    assert not (dest.parent / "f.bin.part").exists()

    txt = tmp_path / "t.txt"
    write_private_text(txt, "نص")
    assert txt.read_text(encoding="utf-8") == "نص"
    assert stat.S_IMODE(txt.stat().st_mode) == 0o600


def test_atomic_write_cleans_up_on_error(tmp_path: Path) -> None:
    dest = tmp_path / "f.bin"
    with pytest.raises(RuntimeError), atomic_write(dest) as fh:
        fh.write(b"partial")
        raise RuntimeError("boom")
    assert not dest.exists()
    assert not (tmp_path / "f.bin.part").exists()


def test_move_file_never_overwrites(tmp_path: Path) -> None:
    a = tmp_path / "a.pdf"
    a.write_bytes(b"1")
    b = tmp_path / "dest" / "x.pdf"
    b.parent.mkdir()
    b.write_bytes(b"existing")
    moved = move_file(a, b)
    assert moved.name == "x (1).pdf"
    assert b.read_bytes() == b"existing"


def test_sha256(tmp_path: Path) -> None:
    p = tmp_path / "x"
    p.write_bytes(b"abc")
    assert sha256_file(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
