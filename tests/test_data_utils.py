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


def test_disconnect_dataset_uses_datalad_drop(tmp_path, monkeypatch):
    dataset_path = tmp_path / "bogus"
    (dataset_path / ".datalad").mkdir(parents=True)
    ran_commands: list[list[str]] = []

    monkeypatch.setattr(
        data.shutil, "which", lambda name: "/usr/bin/datalad" if name == "datalad" else None
    )
    monkeypatch.setattr(data, "_run", lambda cmd, cwd=None: ran_commands.append(cmd))
    removed = []
    monkeypatch.setattr(data.shutil, "rmtree", lambda path: removed.append(path))

    result = data.disconnect_dataset(
        "bogus",
        dataset_path,
        drop_content=True,
        dry_run=False,
        config_path=tmp_path / "config.toml",
    )

    assert result == "removed"
    assert [
        "datalad",
        "drop",
        "-d",
        str(dataset_path),
        "--recursive",
        "--reckless",
        "auto",
    ] in ran_commands
    assert removed == [dataset_path]


def test_disconnect_dataset_falls_back_to_rmtree(tmp_path, monkeypatch):
    dataset_path = tmp_path / "bogus"
    (dataset_path / ".git").mkdir(parents=True)
    monkeypatch.setattr(data.shutil, "which", lambda name: None)
    dropped = []
    monkeypatch.setattr(data.shutil, "rmtree", lambda path: dropped.append(path))

    result = data.disconnect_dataset(
        "bogus",
        dataset_path,
        drop_content=True,
        dry_run=False,
        config_path=tmp_path / "config.toml",
    )

    assert result == "removed"
    assert dropped == [dataset_path]
