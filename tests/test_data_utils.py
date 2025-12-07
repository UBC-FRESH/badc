from __future__ import annotations

import tomllib
from pathlib import Path

from badc import data


def test_connect_dataset_skips_update_for_git_submodule(tmp_path, monkeypatch):
    target = tmp_path / "bogus"
    target.mkdir()
    (target / ".git").write_text("gitdir: ../.git/modules/data/datalad/bogus\n", encoding="utf-8")
    called = False

    def fake_update(path: Path, method: str) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(data, "_update_dataset", fake_update)
    spec = data.DatasetSpec(name="bogus", url="https://example.com/bogus.git")
    config_path = tmp_path / "data.toml"

    status = data.connect_dataset(spec, target, config_path=config_path)

    assert status == "exists"
    assert called is False
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    assert config["datasets"]["bogus"]["method"] == "git-submodule"
