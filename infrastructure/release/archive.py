"""Package only the sources required by the two CodeBuild jobs."""
import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[2]
EXPLICIT_FILES = (
    "client/.dockerignore", "client/Dockerfile", "client/requirements.txt",
    "client/requirements-aws.txt", "client/manage.py",
    "backend/.dockerignore", "backend/Dockerfile", "backend/package.json",
    "backend/package-lock.json", "backend/tsconfig.json", "backend/prisma/schema.prisma",
    "infrastructure/release/buildspec.yml", "infrastructure/release/build.sh",
    "infrastructure/release/migrate.yml", "infrastructure/release/migrate.py",
)
SOURCE_DIRECTORIES = (
    "client/config", "client/shop", "client/static", "client/templates", "backend/src",
)
TEXT_SUFFIXES = {".py", ".css", ".js", ".html", ".svg", ".ts"}
IMAGE_SUFFIXES = {".png", ".webp", ".jpeg", ".jpg"}


def package(destination):
    sources = [ROOT / filename for filename in EXPLICIT_FILES]
    for folder in SOURCE_DIRECTORIES:
        sources.extend(
            path for path in (ROOT / folder).rglob("*")
            if path.is_file() and path.suffix in TEXT_SUFFIXES | IMAGE_SUFFIXES
        )
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(sources):
            content = path.read_bytes()
            if path.suffix not in IMAGE_SUFFIXES:
                content = content.replace(b"\r\n", b"\n")
            member = ZipInfo(path.relative_to(ROOT).as_posix())
            member.compress_type = ZIP_DEFLATED
            archive.writestr(member, content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    package(parser.parse_args().destination)
