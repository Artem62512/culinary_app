import json
import os

import desktop_launcher


def test_local_runtime_configuration_uses_persistent_per_user_credentials(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    username, password, first_run = desktop_launcher._configure_local_instance()
    credentials_path = tmp_path / "CulinaryApp" / "credentials.json"
    saved_credentials = json.loads(credentials_path.read_text(encoding="utf-8"))

    assert first_run is True
    assert username == saved_credentials["username"] == "local"
    assert password == saved_credentials["password"]
    assert password
    assert "CulinaryApp" in os.environ["DATABASE_URL"]
    assert "data" in os.environ["DATABASE_URL"]

    next_username, next_password, next_first_run = (
        desktop_launcher._configure_local_instance()
    )

    assert next_first_run is False
    assert (next_username, next_password) == (username, password)
