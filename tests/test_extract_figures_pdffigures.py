"""Tests for scripts.extract_figures_pdffigures (approach B — pdffigures2 wrapper)."""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_raises_when_jar_not_configured(tmp_path, monkeypatch):
    from scripts.extract_figures_pdffigures import extract, PdfFiguresNotAvailable

    monkeypatch.delenv("PDFFIGURES2_JAR", raising=False)
    with pytest.raises(PdfFiguresNotAvailable):
        extract(Path("any.pdf"), tmp_path)


def test_calls_java_subprocess_with_expected_args(tmp_path, monkeypatch):
    from scripts import extract_figures_pdffigures as mod

    jar = tmp_path / "pdffigures2.jar"
    jar.write_bytes(b"fake jar")
    monkeypatch.setenv("PDFFIGURES2_JAR", str(jar))

    calls = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        # Simulate pdffigures2 writing the JSON index and one figure PNG
        json_path = Path(kwargs.get("cwd", ".")) / "figures.json"
        # The command includes -f <prefix>; parse to discover output paths
        data = [
            {
                "name": "Figure 1",
                "page": 0,
                "caption": "Figure 1: Architecture.",
                "renderURL": str(tmp_path / "fig-1.png"),
            }
        ]
        # Find the -f flag to know where to write json
        try:
            fi = cmd.index("-f")
            json_path = Path(cmd[fi + 1])
        except ValueError:
            pass
        json_path.write_text(json.dumps(data))
        Path(data[0]["renderURL"]).write_bytes(b"\x89PNG fake")
        m = MagicMock()
        m.returncode = 0
        m.stdout = b""
        m.stderr = b""
        return m

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    figures = mod.extract(Path("paper.pdf"), tmp_path)

    assert len(calls) == 1
    cmd = calls[0]
    assert cmd[0] == "java"
    assert "-jar" in cmd
    assert str(jar) in cmd
    assert "paper.pdf" in cmd

    assert len(figures) == 1
    assert figures[0]["number"] == 1
    assert figures[0]["caption"] == "Figure 1: Architecture."
    assert figures[0]["page"] == 1  # pdffigures2 uses 0-index, we normalise to 1
    assert Path(figures[0]["image_path"]).exists()


def test_nonzero_exit_raises(tmp_path, monkeypatch):
    from scripts import extract_figures_pdffigures as mod

    jar = tmp_path / "j.jar"
    jar.write_bytes(b"fake")
    monkeypatch.setenv("PDFFIGURES2_JAR", str(jar))

    def fake_run(cmd, *args, **kwargs):
        m = MagicMock()
        m.returncode = 1
        m.stderr = b"boom"
        return m

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="pdffigures2"):
        mod.extract(Path("paper.pdf"), tmp_path)


def test_is_available_env_check(monkeypatch, tmp_path):
    from scripts.extract_figures_pdffigures import is_available

    monkeypatch.delenv("PDFFIGURES2_JAR", raising=False)
    assert is_available() is False

    fake_jar = tmp_path / "pdffigures2.jar"
    fake_jar.write_bytes(b"fake")
    monkeypatch.setenv("PDFFIGURES2_JAR", str(fake_jar))
    assert is_available() is True

    monkeypatch.setenv("PDFFIGURES2_JAR", "/nonexistent/path.jar")
    assert is_available() is False
