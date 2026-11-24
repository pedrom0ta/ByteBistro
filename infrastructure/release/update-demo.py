"""Update the existing native Django/SQLite demo behind its HTTPS proxy."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
from http.client import parse_headers
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import subprocess
import time
from urllib.parse import urlsplit
from uuid import uuid4
from zipfile import ZipFile


BACKUP_ROOT = Path("/var/backups/bytebistro")


def systemctl(*args):
    return subprocess.check_output(["systemctl", *args], text=True).strip()


def native_app(service, python_path):
    pid = int(systemctl("show", service, "--property=MainPID", "--value"))
    if pid <= 1:
        raise RuntimeError(f"A unidade {service} precisa estar ativa.")
    process = Path(f"/proc/{pid}")
    app = (process / "cwd").resolve(strict=True)
    if not (app / "manage.py").is_file():
        raise RuntimeError("A unidade deve ser o Django nativo e ter manage.py no diretório de trabalho.")
    start = systemctl("show", service, "--property=ExecStart", "--value")
    executable = re.search(r"\bpath=([^ ;]+)", start)
    candidates = [Path(python_path)] if python_path else [app / ".venv/bin/python", app / "venv/bin/python"]
    if not python_path and executable:
        candidates.insert(0, Path(executable[1]).with_name("python"))
        candidates.append(Path(executable[1]).with_name("python3"))
    python = next((path.absolute() for path in candidates if path.is_file() and os.access(path, os.X_OK)), None)
    if python is None:
        raise RuntimeError("Informe o executável Python da aplicação com --python.")
    env = dict(item.split(b"=", 1) for item in (process / "environ").read_bytes().split(b"\0") if item)
    env.setdefault(b"DJANGO_SETTINGS_MODULE", b"config.settings")
    env[b"PYTHONDONTWRITEBYTECODE"] = b"1"
    identity = dict(line.split(":", 1) for line in (process / "status").read_text().splitlines() if ":" in line)
    uid = int(identity["Uid"].split()[1])
    gid = int(identity["Gid"].split()[1])
    groups = [int(group) for group in identity["Groups"].split()]
    return app, [str(python)], {"cwd": app, "env": env, "user": uid, "group": gid, "extra_groups": groups}


def database_path(python, execution):
    inspect = """
from django import VERSION
from django.conf import settings
from pathlib import Path
import json
if not (5, 0, 9) <= VERSION[:3] < (6,):
    raise SystemExit('A aplicação precisa usar Django 5.0.9 ou superior dentro da série 5.x.')
database = settings.DATABASES['default']
if database['ENGINE'] != 'django.db.backends.sqlite3':
    raise SystemExit('O atualizador da demonstração exige um banco SQLite.')
print(json.dumps(str(Path(database['NAME']).resolve(strict=True))))
"""
    result = subprocess.check_output([*python, "-c", inspect], text=True, **execution)
    database = Path(json.loads(result.splitlines()[-1]))
    if not database.is_file() or not database.stat().st_size:
        raise RuntimeError("O banco SQLite ativo precisa existir e conter dados.")
    return database


def updated_files(archive, app):
    updates = {}
    with ZipFile(archive) as source:
        for item in source.infolist():
            parts = PurePosixPath(item.filename).parts
            if item.is_dir() or len(parts) < 4 or parts[:2] != ("apps", "web"):
                continue
            relative = Path(*parts[2:])
            if relative != Path("config/urls.py") and parts[2] not in {"shop", "static", "templates"}:
                continue
            target = app / relative
            if target.resolve() != target or not target.is_relative_to(app):
                raise RuntimeError(f"Caminho indireto na aplicação: {relative}")
            content = source.read(item)
            if not target.exists() or target.read_bytes() != content:
                updates[relative] = content
        required = {"apps/web/config/urls.py", "apps/web/shop/views.py", "apps/web/templates/home.html"}
        if not required.issubset(source.namelist()):
            raise RuntimeError("O ZIP precisa vir do empacotador de release do ByteBistro.")
    return updates


def copy_database(source, target):
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
        with closing(sqlite3.connect(target)) as backup:
            original.backup(backup)
            if backup.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise RuntimeError(f"Falha na verificação do backup SQLite em {target}.")


def nginx_response(url, path):
    origin = urlsplit(url)
    port = origin.port or 443
    response = subprocess.check_output([
        "curl", "--silent", "--show-error", "--http1.1", "--include", "--max-time", "5",
        "--noproxy", "*", "--connect-to", f"{origin.hostname}:{port}:127.0.0.1:{port}", url + path,
    ])
    head, _, body = response.partition(b"\r\n\r\n")
    status_line, _, headers = head.partition(b"\r\n")
    return int(status_line.split()[1]), parse_headers(BytesIO(headers + b"\r\n\r\n")), body


def verify_site(url, updated=False):
    status, _, body = nginx_response(url, "/cardapio/")
    if status != 200 or b"bytebistro" not in body.lower():
        raise RuntimeError("O cardápio HTTPS não respondeu como ByteBistro.")
    if updated:
        status, headers, _ = nginx_response(url, f"/pedidos/{uuid4()}/status/")
        if (
            status != 404
            or not headers.get("Content-Type", "").startswith("application/json")
            or "no-store" not in headers.get("Cache-Control", "")
        ):
            raise RuntimeError("A rota pública de status ainda não reflete o código atualizado.")


def deploy(service, archive, url, python_path):
    app, python, execution = native_app(service, python_path)
    database = database_path(python, execution)
    updates = updated_files(archive, app)
    verify_site(url)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8]
    backup_dir = BACKUP_ROOT / stamp
    backup_dir.mkdir(parents=True, mode=0o700)
    existing = set()
    for relative in updates:
        target = app / relative
        if target.is_file():
            saved = backup_dir / "files" / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
            existing.add(relative)
    backup = backup_dir / "database.sqlite3"
    print(f"Aplicação: {app}\nBanco: {database}\nBackup: {backup_dir}", flush=True)
    applied = []
    database_backed_up = False
    try:
        systemctl("stop", service)
        copy_database(database, backup)
        database_backed_up = True
        for relative, content in updates.items():
            target = app / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            applied.append(relative)
            target.write_bytes(content)
        subprocess.run([*python, "manage.py", "check"], check=True, **execution)
        subprocess.run([*python, "manage.py", "migrate", "--noinput"], check=True, **execution)
        systemctl("start", service)
        for attempt in range(8):
            try:
                verify_site(url, updated=True)
                break
            except (OSError, RuntimeError, subprocess.CalledProcessError):
                if attempt == 7:
                    raise
                time.sleep(1)
    except BaseException:
        print("A atualização falhou. Restaurando os arquivos e o banco anteriores.", flush=True)
        systemctl("stop", service)
        for relative in applied:
            target = app / relative
            if relative in existing:
                shutil.copy2(backup_dir / "files" / relative, target)
            else:
                target.unlink(missing_ok=True)
        if database_backed_up:
            copy_database(backup, database)
        systemctl("start", service)
        raise
    print(f"Release ativo em {url}/", flush=True)


if __name__ == "__main__":
    import fcntl

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", help="Unidade systemd que executa o Django")
    parser.add_argument("archive", type=Path, help="ZIP do release do ByteBistro")
    parser.add_argument("--url", required=True, help="Endereço HTTPS público existente")
    parser.add_argument("--python", help="Caminho absoluto do Python da aplicação, se necessário")
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Execute com sudo.")
    if not re.fullmatch(r"[A-Za-z0-9_.@-]+\.service", args.service) or args.service.startswith("-"):
        parser.error("Informe o nome de uma unidade .service do Django.")
    if not args.url.startswith("https://"):
        parser.error("Informe a URL HTTPS existente.")
    with Path("/run/lock/bytebistro-demo-update.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Outra atualização do ByteBistro está em andamento.")
        deploy(args.service, args.archive, args.url.rstrip("/"), args.python)
