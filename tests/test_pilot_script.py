import os
from pathlib import Path
import runpy
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_pilot.py"
workflow = runpy.run_path(str(SCRIPT))
load_env, main = workflow["load_env"], workflow["main"]


def test_env_is_data_and_shell_takes_precedence(tmp_path):
    path = tmp_path / ".env"
    path.write_text('CONTAGION_MODEL="model tag" # comment\nCONTAGION_API_KEY=\'$(touch unsafe);$HOME\'\nCONTAGION_PROVIDER=ollama\n')
    env = load_env(path, {"CONTAGION_PROVIDER": "mock"})
    assert env["CONTAGION_MODEL"] == "model tag"
    assert env["CONTAGION_API_KEY"] == "$(touch unsafe);$HOME"
    assert env["CONTAGION_PROVIDER"] == "mock"
    assert not (tmp_path / "unsafe").exists()


@pytest.mark.parametrize("text", ['CONTAGION_API_KEY="secret', 'PATH=secret', 'CONTAGION_MODEL=two words'])
def test_env_errors_do_not_disclose_values(tmp_path, text):
    path = tmp_path / ".env"
    path.write_text(text)
    with pytest.raises(ValueError) as exc:
        load_env(path, {})
    assert "secret" not in str(exc.value)


def test_live_order_and_failure_stops_later_steps(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", {})
    path = tmp_path / ".env"
    path.write_text('CONTAGION_BASE_URL=http://fixture.invalid\nCONTAGION_MODEL=fixture\n')
    calls = []
    def fake_run(command, **kwargs):
        calls.append(command)
        if "--check-chat" in command:
            raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert main(["--env-file", str(path)]) == 1
    assert len(calls) == 2
    assert "doctor" in calls[0] and "--check-chat" in calls[1]


def test_doctor_only_needs_no_model(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", {})
    path = tmp_path / ".env"
    path.write_text('CONTAGION_BASE_URL=http://fixture.invalid\n')
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs: calls.append(command))
    assert main(["--env-file", str(path), "--doctor-only"]) == 0
    assert len(calls) == 1 and "--check-chat" not in calls[0]


def test_mock_orders_pair_then_analysis(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", {})
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)))
    assert main(["--provider", "mock", "--out", str(tmp_path / "results")]) == 0
    assert calls[0][0][3] == "batch"
    assert calls[1][0][3] == "analyze"
    assert all(call[1]["check"] for call in calls)
