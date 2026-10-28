# SPDX-License-Identifier: BSD-3-Clause

"""Common source verification and deterministic release packaging."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
from typing import BinaryIO, Iterable
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


BUFFER_BYTES = 1024 * 1024
def sha256_file(path: Path) -> str:
    """Hash one potentially large file with bounded memory use."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(BUFFER_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative_path(raw_path: str, label: str) -> PurePosixPath:
    """Accept one normalized relative POSIX path without traversal."""
    if not isinstance(raw_path, str) or raw_path != raw_path.strip():
        raise ValueError(f"invalid {label}: {raw_path!r}")
    value = raw_path
    path = PurePosixPath(value)
    if (
        not value
        or "\x00" in value
        or "\\" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix() != value
    ):
        raise ValueError(f"invalid {label}: {raw_path!r}")
    return path


def valid_sha256(raw_value: object, label: str) -> str:
    """Normalize one SHA-256 digest or reject malformed metadata."""
    value = str(raw_value or "").strip().lower()
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"invalid SHA-256 for {label}")
    return value


def positive_size(raw_value: object, label: str) -> int:
    """Require a positive exact byte count for a source or release file."""
    if isinstance(raw_value, bool):
        raise ValueError(f"invalid byte size for {label}")
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid byte size for {label}") from error
    if value < 1:
        raise ValueError(f"byte size for {label} must be positive")
    return value


@dataclass(frozen=True)
class LockedSource:
    """One immutable upstream input declared by a model source lock."""

    path: PurePosixPath
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class SourceLock:
    """Pinned upstream identity and exact files consumed by one model build."""

    model_id: str
    repository: str
    revision: str
    base_url: str
    license_id: str
    files: dict[str, LockedSource]

    @classmethod
    def load(cls, path: Path) -> "SourceLock":
        """Parse and fully validate a schema version 1 source lock."""
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ValueError("source lock must be a JSON object")
        if document.get("schemaVersion") != 1:
            raise ValueError("source lock schemaVersion must be 1")
        raw_files = document.get("files")
        if not isinstance(raw_files, dict) or not raw_files:
            raise ValueError("source lock files must be a non-empty object")
        files: dict[str, LockedSource] = {}
        for raw_path, metadata in sorted(raw_files.items()):
            if not isinstance(metadata, dict):
                raise ValueError(f"source metadata must be an object: {raw_path}")
            source_path = safe_relative_path(raw_path, "source path")
            wire_path = source_path.as_posix()
            files[wire_path] = LockedSource(
                path=source_path,
                size_bytes=positive_size(metadata.get("bytes"), wire_path),
                sha256=valid_sha256(metadata.get("sha256"), wire_path),
            )
        return cls(
            model_id=_required_text(document.get("modelId"), "modelId"),
            repository=_required_text(document.get("repository"), "repository"),
            revision=_required_text(document.get("revision"), "revision"),
            base_url=_validated_base_url(document.get("baseUrl")),
            license_id=_required_text(document.get("license"), "license"),
            files=files,
        )

    def source(self, relative_path: str) -> LockedSource:
        """Return one declared source without accepting an unreviewed path."""
        wire_path = safe_relative_path(relative_path, "source path").as_posix()
        try:
            return self.files[wire_path]
        except KeyError as error:
            raise ValueError(f"source is not declared in lock: {wire_path}") from error


def _required_text(raw_value: object, label: str) -> str:
    """Require a non-empty identity or provenance field."""
    value = str(raw_value or "").strip()
    if not value:
        raise ValueError(f"source lock {label} must not be empty")
    return value


def _validated_base_url(raw_value: object) -> str:
    """Allow HTTPS upstreams and file URLs used by isolated tests."""
    value = _required_text(raw_value, "baseUrl").rstrip("/")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"file", "https"}:
        raise ValueError("source lock baseUrl must use file or https")
    if parsed.fragment or parsed.query:
        raise ValueError("source lock baseUrl must not use a query or fragment")
    if parsed.scheme == "https" and not parsed.netloc:
        raise ValueError("source lock baseUrl must be an absolute HTTPS URL")
    if parsed.scheme == "file" and not parsed.path:
        raise ValueError("source lock file baseUrl must contain a path")
    return value


def _file_matches(path: Path, expected: LockedSource) -> bool:
    """Check an immutable source cache entry by size and digest."""
    return (
        path.is_file()
        and path.stat().st_size == expected.size_bytes
        and sha256_file(path) == expected.sha256
    )


def _copy_bounded(source: BinaryIO, destination: BinaryIO, expected_bytes: int) -> int:
    """Copy an upstream response while enforcing its locked byte count."""
    written = 0
    while True:
        chunk = source.read(BUFFER_BYTES)
        if not chunk:
            break
        destination.write(chunk)
        written += len(chunk)
        if written > expected_bytes:
            raise ValueError("upstream source exceeds its locked byte size")
    return written


class SourceStore:
    """Content-addressed local cache for exact upstream model inputs."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir

    def materialize(
        self,
        source_lock: SourceLock,
        relative_path: str,
        destination: Path,
        *,
        offline: bool = False,
        base_url: str | None = None,
    ) -> Path:
        """Verify or fetch one locked source, then copy it into the build tree."""
        expected = source_lock.source(relative_path)
        cached = self.cache_dir / expected.sha256
        if not _file_matches(cached, expected):
            if offline:
                raise FileNotFoundError(f"verified source is not cached: {expected.path}")
            self._download(expected, (base_url or source_lock.base_url).rstrip("/"), cached)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        try:
            shutil.copyfile(cached, temporary)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    def _download(self, expected: LockedSource, base_url: str, destination: Path) -> None:
        """Download one source into the cache only after exact verification."""
        base_url = _validated_base_url(base_url)
        encoded_path = urllib.parse.quote(expected.path.as_posix(), safe="/")
        url = f"{base_url}/{encoded_path}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        print(f"[build] download {expected.path}")
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as raw:
            temporary = Path(raw.name)
            try:
                with urllib.request.urlopen(url, timeout=120) as response:
                    written = _copy_bounded(response, raw, expected.size_bytes)
                raw.flush()
                os.fsync(raw.fileno())
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
        try:
            if written != expected.size_bytes or sha256_file(temporary) != expected.sha256:
                raise ValueError(f"upstream source failed verification: {expected.path}")
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class BuildWorkspace:
    """Repository paths and source cache shared by one model build."""

    repository_root: Path
    model_name: str

    @property
    def build_dir(self) -> Path:
        return self.repository_root / "build" / self.model_name

    @property
    def dist_dir(self) -> Path:
        return self.repository_root / "dist"

    @property
    def source_store(self) -> SourceStore:
        return SourceStore(self.repository_root / ".cache" / "sources")

    def reset(self) -> None:
        """Clear only this model's build tree while preserving source caches."""
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        self.build_dir.mkdir(parents=True)
        self.dist_dir.mkdir(parents=True, exist_ok=True)


def verify_collada_resources(path: Path) -> None:
    """Reject Collada files with hidden external texture or buffer references."""
    root = ET.parse(path).getroot()
    external: list[str] = []
    for image in root.iter():
        if image.tag.rsplit("}", 1)[-1] != "image":
            continue
        for element in image.iter():
            if element.tag.rsplit("}", 1)[-1] != "init_from":
                continue
            value = (element.text or "").strip()
            if value and not value.startswith("#"):
                external.append(value)
    if external:
        raise ValueError(f"Collada asset has external resources: {path}: {external}")


def _normalized_tar_info(path: Path, archive_name: str) -> tarfile.TarInfo:
    """Create stable archive metadata independent of the build host."""
    info = tarfile.TarInfo(archive_name)
    info.size = path.stat().st_size
    info.mode = 0o644
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    return info


def _release_paths(files: Iterable[Path], root: Path) -> list[tuple[PurePosixPath, Path]]:
    """Normalize, de-duplicate, and sort files below one release root."""
    normalized: dict[str, tuple[PurePosixPath, Path]] = {}
    resolved_root = root.resolve()
    for path in files:
        if path.is_symlink():
            raise ValueError(f"release member must not be a symlink: {path}")
        resolved = path.resolve(strict=True)
        try:
            relative = resolved.relative_to(resolved_root)
        except ValueError as error:
            raise ValueError(f"release file is outside build root: {path}") from error
        wire_path = safe_relative_path(relative.as_posix(), "release path")
        if not resolved.is_file():
            raise ValueError(f"release member must be a regular file: {path}")
        if wire_path.as_posix() in normalized:
            raise ValueError(f"duplicate release path: {wire_path}")
        normalized[wire_path.as_posix()] = (wire_path, resolved)
    if not normalized:
        raise ValueError("release must contain at least one file")
    return [normalized[key] for key in sorted(normalized)]


def write_deterministic_archive(files: Iterable[Path], root: Path, output: Path) -> None:
    """Write sorted files with fixed tar metadata and a zero gzip timestamp."""
    release_paths = _release_paths(files, root)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as raw_output:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_output, mtime=0) as zipped:
                with tarfile.open(fileobj=zipped, mode="w") as archive:
                    for relative, path in release_paths:
                        with path.open("rb") as source:
                            archive.addfile(
                                _normalized_tar_info(path, relative.as_posix()), source
                            )
            raw_output.flush()
            os.fsync(raw_output.fileno())
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def build_file_manifest(files: Iterable[Path], root: Path) -> dict[str, dict[str, object]]:
    """Describe every release member with its exact byte count and SHA-256."""
    return {
        relative.as_posix(): {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for relative, path in _release_paths(files, root)
    }


def write_json(document: dict[str, object], output: Path) -> None:
    """Atomically write stable, reviewable JSON with a final newline."""
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
