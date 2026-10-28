# SPDX-License-Identifier: BSD-3-Clause

"""Build the Unitree B2-W visual model from exact locked upstream inputs."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET

from asset_builder import (
    BuildWorkspace,
    SourceLock,
    build_file_manifest,
    sha256_file,
    verify_collada_resources,
    write_deterministic_archive,
    write_json,
)


MODEL_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = MODEL_DIR.parents[1]
PACKAGE_ROOT = "robots/b2w_description"
PACKAGE_URI = "package://b2w_description/"
SOURCE_URDF = f"{PACKAGE_ROOT}/urdf/b2w_description.urdf"
URDF_NAME = "unitree_b2w_visual.urdf"


def validate_source_identity(source_lock: SourceLock) -> None:
    """Keep the declared Unitree revision and official raw URL synchronized."""
    revision = source_lock.revision
    if len(revision) != 40 or any(
        character not in "0123456789abcdef" for character in revision
    ):
        raise ValueError("B2-W source revision must be a full lowercase Git SHA")
    if not source_lock.base_url.endswith(f"/{revision}"):
        raise ValueError("B2-W source baseUrl does not match its revision")


def output_names(revision: str) -> tuple[str, str]:
    """Derive versioned artifact names from the locked upstream revision."""
    revision_label = revision[:7]
    return (
        f"unitree-b2w-visuals-{revision_label}.tar.gz",
        f"unitree-b2w-visuals-{revision_label}.files.json",
    )


def mesh_path(reference: str) -> PurePosixPath:
    """Translate one B2-W package URI into an URDF-local release path."""
    if not reference.startswith(PACKAGE_URI):
        raise ValueError(f"unsupported B2-W Mesh URI: {reference}")
    path = PurePosixPath(reference.removeprefix(PACKAGE_URI))
    if path.is_absolute() or ".." in path.parts or path.parts[:1] != ("meshes",):
        raise ValueError(f"unsafe B2-W Mesh URI: {reference}")
    return path


def prepare_urdf(source: Path, destination: Path) -> tuple[PurePosixPath, ...]:
    """Keep visual geometry, normalize materials, and remove collision nodes."""
    root = ET.parse(source).getroot()
    root.set("name", "unitree_b2w_visual")
    root.insert(0, ET.Comment(" SPDX-License-Identifier: BSD-3-Clause "))
    for link in root.findall("link"):
        for collision in list(link.findall("collision")):
            link.remove(collision)
    for index, material in enumerate(root.findall(".//material"), 1):
        material.set("name", f"material_{index:03d}")
    assets: set[PurePosixPath] = set()
    for visual in root.findall(".//visual"):
        for mesh in visual.findall(".//mesh"):
            path = mesh_path(mesh.get("filename", ""))
            mesh.set("filename", path.as_posix())
            assets.add(path)
    if not assets:
        raise ValueError("B2-W URDF contains no visual Mesh resources")
    ET.indent(root, space="  ")
    destination.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)
    return tuple(sorted(assets))


def build(*, offline: bool = False, source_base_url: str | None = None) -> Path:
    """Generate the visual URDF, deterministic archive, and release metadata."""
    source_lock = SourceLock.load(MODEL_DIR / "source-lock.json")
    validate_source_identity(source_lock)
    archive_name, manifest_name = output_names(source_lock.revision)
    workspace = BuildWorkspace(REPOSITORY_ROOT, "unitree-b2w")
    workspace.reset()

    source_urdf = workspace.source_store.materialize(
        source_lock,
        SOURCE_URDF,
        workspace.build_dir / "source" / "b2w_description.urdf",
        offline=offline,
        base_url=source_base_url,
    )
    output_urdf = workspace.dist_dir / URDF_NAME
    assets = prepare_urdf(source_urdf, output_urdf)

    consumed_sources = {
        SOURCE_URDF,
        "LICENSE",
        *(f"{PACKAGE_ROOT}/{asset.as_posix()}" for asset in assets),
    }
    if consumed_sources != set(source_lock.files):
        missing = sorted(consumed_sources - set(source_lock.files))
        unused = sorted(set(source_lock.files) - consumed_sources)
        raise ValueError(
            f"B2-W source lock does not match build inputs; missing={missing}, unused={unused}"
        )

    release_files: list[Path] = []
    for asset in assets:
        upstream_path = f"{PACKAGE_ROOT}/{asset.as_posix()}"
        destination = workspace.build_dir.joinpath(*asset.parts)
        workspace.source_store.materialize(
            source_lock,
            upstream_path,
            destination,
            offline=offline,
            base_url=source_base_url,
        )
        if destination.suffix.lower() == ".dae":
            verify_collada_resources(destination)
        release_files.append(destination)

    license_path = workspace.source_store.materialize(
        source_lock,
        "LICENSE",
        workspace.build_dir / "licenses" / "UNITREE_ROS_LICENSE-BSD-3-CLAUSE.txt",
        offline=offline,
        base_url=source_base_url,
    )
    release_files.append(license_path)

    archive = workspace.dist_dir / archive_name
    write_deterministic_archive(release_files, workspace.build_dir, archive)
    files = build_file_manifest(release_files, workspace.build_dir)
    manifest = {
        "schemaVersion": 1,
        "modelId": source_lock.model_id,
        "version": f"unitree_ros-{source_lock.revision}",
        "upstream": source_lock.repository,
        "revision": source_lock.revision,
        "license": source_lock.license_id,
        "sourceUrdf": SOURCE_URDF,
        "generatedUrdf": {
            "path": output_urdf.name,
            "bytes": output_urdf.stat().st_size,
            "sha256": sha256_file(output_urdf),
        },
        "artifact": {
            "name": archive_name,
            "bytes": archive.stat().st_size,
            "sha256": sha256_file(archive),
        },
        "installRoots": ["meshes", "licenses"],
        "files": files,
    }
    manifest_path = workspace.dist_dir / manifest_name
    write_json(manifest, manifest_path)
    print(
        f"[build] wrote {archive} ({archive.stat().st_size / 1048576:.1f} MiB, "
        f"{len(files)} files)"
    )
    return manifest_path
