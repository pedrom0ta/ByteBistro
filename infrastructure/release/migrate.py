"""Initialize application credentials and migrate the private RDS database."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import urlretrieve

import psycopg
from psycopg import sql


def aws(*args):
    return subprocess.check_output(["aws", *args, "--no-cli-pager"], text=True)


def read_secret(arn):
    value = aws("secretsmanager", "get-secret-value", "--secret-id", arn, "--query", "SecretString", "--output", "text")
    return json.loads(value) if value.strip() != "None" else None


def write_secret(arn, values):
    # Pass values through stdin instead of placing credentials in the process arguments.
    subprocess.run(
        ["aws", "secretsmanager", "put-secret-value", "--secret-id", arn,
         "--secret-string", "file:///dev/stdin", "--no-cli-pager"],
        input=json.dumps(values), text=True, stdout=subprocess.DEVNULL, check=True,
    )


def existing_secret(arn):
    versions = json.loads(aws(
        "secretsmanager", "list-secret-version-ids", "--secret-id", arn,
        "--query", "Versions[?contains(VersionStages, 'AWSCURRENT')]", "--output", "json",
    ))
    return read_secret(arn) if versions else None


def database_url(host, user, password, database):
    encoded = urlencode({
        "sslmode": "require",
        "sslaccept": "strict",
        "sslcert": "/app/rds-ca.pem",
        "connection_limit": "3",
    })
    return f"postgresql://{user}:{quote(password, safe='')}@{host}:5432/{database}?{encoded}"


def migrate():
    host = os.environ["DB_HOST"]
    database = "bytebistro"
    bundle = "/tmp/bytebistro-rds-ca.pem"
    urlretrieve("https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem", bundle)
    admin = read_secret(os.environ["DB_ADMIN_SECRET"])
    arns = {service: os.environ[f"{service.upper()}_SECRET"] for service in ("web", "api", "worker")}
    roles = {service: f"bytebistro_{service}" for service in arns}
    stored = {service: existing_secret(arn) for service, arn in arns.items()}
    web = stored["web"] or {
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
        "GRAPHQL_SERVICE_TOKEN": secrets.token_urlsafe(48),
        "PGHOST": host,
        "PGDATABASE": database,
        "PGUSER": roles["web"],
        "PGPASSWORD": secrets.token_urlsafe(48),
    }
    credentials = {"web": web}

    for service in ("api", "worker"):
        if stored[service]:
            credentials[service] = stored[service]
            continue
        password = secrets.token_urlsafe(48)
        credentials[service] = {
            "DATABASE_URL": database_url(host, roles[service], password, database),
        }
        if service == "api":
            credentials[service]["GRAPHQL_SERVICE_TOKEN"] = web["GRAPHQL_SERVICE_TOKEN"]

    # Persist newly generated passwords before configuring PostgreSQL so retries reuse them.
    for service, values in credentials.items():
        if not stored[service]:
            write_secret(arns[service], values)

    with psycopg.connect(
        host=host, dbname=database, user=admin["username"], password=admin["password"],
        sslmode="verify-full", sslrootcert=bundle, connect_timeout=10, autocommit=True,
    ) as connection:
        for service, role in roles.items():
            values = credentials[service]
            password = values["PGPASSWORD"] if service == "web" else unquote(urlsplit(values["DATABASE_URL"]).password)
            role_name = sql.Identifier(role)
            if connection.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone():
                connection.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(role_name, sql.Literal(password)))
            else:
                connection.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(role_name, sql.Literal(password)))
        connection.execute("GRANT USAGE, CREATE ON SCHEMA public TO bytebistro_web")
        connection.execute("GRANT USAGE ON SCHEMA public TO bytebistro_api, bytebistro_worker")

    env = {
        **os.environ, **web,
        "DJANGO_DEBUG": "0",
        "DJANGO_SETTINGS_MODULE": "config.aws_settings",
        "BYTEBISTRO_PUBLIC_HOST": "migration.invalid",
        "BYTEBISTRO_ORIGIN_HOST": "migration.invalid",
        "PGSSLROOTCERT": bundle,
    }
    web_directory = Path(__file__).resolve().parents[2] / "apps" / "web"
    for command in (["migrate", "--noinput"], ["createcachetable"]):
        subprocess.run([sys.executable, "manage.py", *command], cwd=web_directory, env=env, check=True)
    with psycopg.connect(
        host=host, dbname=database, user=web["PGUSER"], password=web["PGPASSWORD"],
        sslmode="verify-full", sslrootcert=bundle, connect_timeout=10,
    ) as connection:
        connection.execute("GRANT SELECT ON shop_order TO bytebistro_api")
        connection.execute("GRANT SELECT ON shop_order TO bytebistro_worker")
        connection.execute("GRANT SELECT, UPDATE ON shop_orderoutbox TO bytebistro_worker")
        connection.execute("GRANT INSERT ON shop_orderevent TO bytebistro_worker")
        seq_row = connection.execute("SELECT pg_get_serial_sequence('shop_orderevent', 'id')").fetchone()
        if seq_row and seq_row[0]:
            seq_parts = connection.execute("SELECT parse_ident(%s)", (seq_row[0],)).fetchone()[0]
            connection.execute(
                sql.SQL("GRANT USAGE, SELECT ON SEQUENCE {} TO bytebistro_worker").format(
                    sql.Identifier(*seq_parts)
                )
            )
    print("Database migrations and runtime grants ready.")


if __name__ == "__main__":
    migrate()
