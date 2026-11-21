"""Start the local, packaged Culinary App server and open it in a browser."""
import json
import os
import secrets
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path


APP_NAME = "CulinaryApp"


def _data_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    path = root / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _configure_local_instance() -> tuple[str, str, bool]:
    data_dir = _data_dir()
    credentials_path = data_dir / "credentials.json"
    first_run = not credentials_path.exists()

    if first_run:
        credentials = {
            "username": "local",
            "password": secrets.token_urlsafe(18),
        }
        temporary_path = credentials_path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(credentials), encoding="utf-8")
        temporary_path.replace(credentials_path)
    else:
        credentials = json.loads(credentials_path.read_text(encoding="utf-8"))

    db_path = data_dir / "data" / "culinary.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    from sqlalchemy.engine import URL

    os.environ["DATABASE_URL"] = URL.create(
        "sqlite",
        database=str(db_path),
    ).render_as_string(hide_password=False)
    os.environ["APP_USERNAME"] = credentials["username"]
    os.environ["APP_PASSWORD"] = credentials["password"]
    os.environ["CULINARY_APP_DATA_DIR"] = str(data_dir)
    return credentials["username"], credentials["password"], first_run


def _resource_path(relative_path: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return root / relative_path


def _initialize_database() -> None:
    backend_dir = _resource_path("backend")
    sys.path.insert(0, str(backend_dir))
    os.chdir(backend_dir)

    from app.core.database import Base, engine
    import app.models  # noqa: F401
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    config = Config(str(backend_dir / "alembic.ini"))
    db_path = _data_dir() / "data" / "culinary.db"
    tables = set(inspect(engine).get_table_names())
    application_tables = tables - {"alembic_version"}
    is_new_database = not application_tables
    if is_new_database:
        Base.metadata.create_all(bind=engine)
        command.stamp(config, "head")
    else:
        if not {"users", "recipes"}.issubset(application_tables):
            raise RuntimeError(
                "Локальная база выглядит неполной. Сохраните её копию и "
                "восстановите резервную копию перед обновлением."
            )
        command.upgrade(config, "head")


def _show_message(title: str, message: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, title, 0x40)
    except (AttributeError, OSError):
        print(f"{title}\n{message}")


def _select_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    try:
        username, password, first_run = _configure_local_instance()
        _initialize_database()

        import uvicorn

        from app.main import app

        port = _select_port()
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=port,
                log_level="warning",
                access_log=False,
            )
        )
        server_thread = threading.Thread(target=server.run, daemon=True)
        server_thread.start()

        for _ in range(100):
            if server.started:
                break
            if not server_thread.is_alive():
                raise RuntimeError("Локальный сервер завершился при запуске.")
            time.sleep(0.1)
        else:
            raise RuntimeError("Локальный сервер не запустился за 10 секунд.")

        url = f"http://127.0.0.1:{port}/"
        (_data_dir() / "local-url.txt").write_text(url + "\n", encoding="utf-8")
        if first_run:
            credentials_file = _data_dir() / "credentials.txt"
            credentials_file.write_text(
                f"Логин: {username}\nПароль: {password}\n\n"
                "Эти данные действуют только для приложения на этом компьютере.\n",
                encoding="utf-8",
            )
            if os.environ.get("CULINARY_APP_SILENT_FIRST_RUN") != "1":
                _show_message(
                    "Culinary App — первый запуск",
                    "Приложение установлено. Данные для входа сохранены в:\n"
                    f"{credentials_file}\n\nОткройте этот файл, чтобы войти.",
                )
                try:
                    os.startfile(str(credentials_file))
                except OSError:
                    pass

        if os.environ.get("CULINARY_APP_NO_BROWSER") != "1":
            webbrowser.open(url)
        while server_thread.is_alive():
            time.sleep(1)
        return 0
    except Exception as exc:
        details = f"{exc}\n\nПодробности записаны в журнал приложения."
        try:
            log_path = _data_dir() / "startup-error.log"
            log_path.write_text(traceback.format_exc(), encoding="utf-8")
            details += f"\n\n{log_path}"
        except OSError:
            pass
        _show_message("Не удалось запустить Culinary App", details)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
