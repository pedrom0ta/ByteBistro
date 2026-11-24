"""Package only the sources required by the two CodeBuild jobs."""
import argparse
from hashlib import file_digest
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[2]
EXPLICIT_FILES = (
    "apps/web/.dockerignore", "apps/web/Dockerfile", "apps/web/requirements.txt",
    "apps/web/requirements-aws.txt", "apps/web/manage.py",
    "apps/services/.dockerignore", "apps/services/Dockerfile", "apps/services/package.json",
    "apps/services/package-lock.json", "apps/services/tsconfig.json", "apps/services/prisma/schema.prisma",
    "infrastructure/release/buildspec.yml", "infrastructure/release/build.sh",
    "infrastructure/release/migrate.yml", "infrastructure/release/migrate.py",
)
SOURCE_DIRECTORIES = (
    "apps/web/config", "apps/web/shop", "apps/web/static", "apps/web/templates", "apps/services/src",
)
TEXT_SUFFIXES = {".py", ".css", ".js", ".html", ".svg", ".ts"}
IMAGE_SUFFIXES = {".png", ".webp", ".jpeg", ".jpg"}


def package(destination):
    sources = [ROOT / filename for filename in EXPLICIT_FILES]
    for folder in SOURCE_DIRECTORIES:
        source = ROOT / folder
        if not source.is_dir():
            raise FileNotFoundError(f"Missing release source directory: {folder}")
        sources.extend(
            path for path in source.rglob("*")
            if path.is_file() and path.suffix in TEXT_SUFFIXES | IMAGE_SUFFIXES
        )

    with NamedTemporaryFile(dir=destination.parent, suffix=".tmp", delete=False) as output:
        temporary_path = Path(output.name)
    try:
        with ZipFile(temporary_path, "w") as archive:
            for path in sorted(sources):
                relative_path = path.relative_to(ROOT)
                if path.resolve() != path or path.is_symlink():
                    raise ValueError(f"Linked release source: {relative_path.as_posix()}")
                content = path.read_bytes()
                if path.suffix not in IMAGE_SUFFIXES:
                    content = content.replace(b"\r\n", b"\n")
                member = ZipInfo(relative_path.as_posix())
                member.compress_type = ZIP_DEFLATED
                archive.writestr(member, content)
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--print-tag", action="store_true", help="Print the release tag derived from the ZIP")
    args = parser.parse_args()
    package(args.destination)
    if args.print_tag:
        with args.destination.open("rb") as archive:
            digest = file_digest(archive, "sha256").hexdigest()
        print(f"release-{digest[:16]}")
