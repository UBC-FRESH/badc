from __future__ import annotations

import pytest

from badc import hawkears


def test_hawkears_root_exists() -> None:
    path = hawkears.get_hawkears_root()
    assert path.exists()
    assert path.name == "HawkEars"


def test_missing_submodule(tmp_path, monkeypatch):
    fake_root = tmp_path / "vendor" / "HawkEars"
    monkeypatch.setattr(hawkears, "HAWKEARS_ROOT", fake_root)
    with pytest.raises(FileNotFoundError):
        hawkears.get_hawkears_root()
