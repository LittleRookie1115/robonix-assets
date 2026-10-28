# SPDX-License-Identifier: BSD-3-Clause

"""Generate fetcher-compatible deployment manifests from build metadata."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import urllib.parse

from .core import positive_size, safe_relative_path, valid_sha256, write_json


def deployment_manifest(build_manifest_path: Path, artifact_url: str) -> dict[str, object]:
    """Select and validate fields needed by the Robonix deployment fetcher."""
    document = json.loads(build_manifest_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schemaVersion") != 1:
        raise ValueError("build manifest must be a schema version 1 JSON object")
    parsed_url = urllib.parse.urlparse(artifact_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise ValueError("artifact URL must be an absolute HTTPS URL")
    if parsed_url.fragment:
        raise ValueError("artifact URL must not contain a fragment")
    lowered_parts = {part.lower() for part in parsed_url.path.split("/")}
    if lowered_parts & {"latest", "main", "master"}:
        raise ValueError("artifact URL must identify an immutable version")

    artifact = document.get("artifact")
    files = document.get("files")
    install_roots = document.get("installRoots")
    if not isinstance(artifact, dict) or not isinstance(files, dict) or not files:
        raise ValueError("build manifest artifact and files must be non-empty objects")
    if not isinstance(install_roots, list) or not install_roots:
        raise ValueError("build manifest installRoots must be a non-empty list")
    validated_files: dict[str, dict[str, object]] = {}
    for path, metadata in files.items():
        if not isinstance(metadata, dict):
            raise ValueError(f"invalid build manifest file metadata: {path}")
        validated_files[path] = {
            "bytes": positive_size(metadata.get("bytes"), path),
            "sha256": valid_sha256(metadata.get("sha256"), path),
        }
    model_id = str(document.get("modelId") or "").strip()
    version = str(document.get("version") or "").strip()
    if not model_id or not version:
        raise ValueError("build manifest modelId and version must not be empty")
    roots = [
        safe_relative_path(root, "install root").as_posix()
        for root in install_roots
    ]
    if any("/" in root for root in roots) or len(set(roots)) != len(roots):
        raise ValueError("install roots must be unique top-level directories")
    for path in validated_files:
        relative = safe_relative_path(path, "release path")
        if relative.parts[0] not in roots:
            raise ValueError(f"release file is outside install roots: {path}")
    if set(roots) - {PurePosixPath(path).parts[0] for path in validated_files}:
        raise ValueError("every install root must contain at least one release file")
    return {
        "schemaVersion": 1,
        "modelId": model_id,
        "version": version,
        "artifact": {
            "url": artifact_url,
            "bytes": positive_size(artifact.get("bytes"), "artifact"),
            "sha256": valid_sha256(artifact.get("sha256"), "artifact"),
        },
        "installRoots": roots,
        "files": validated_files,
    }


def write_deployment_manifest(
    build_manifest_path: Path, artifact_url: str, output: Path
) -> Path:
    """Write one validated fetcher manifest and return its destination."""
    document = deployment_manifest(build_manifest_path, artifact_url)
    write_json(document, output)
    return output
