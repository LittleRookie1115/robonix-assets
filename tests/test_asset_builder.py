# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from asset_builder import (
    BuildWorkspace,
    SourceLock,
    build_file_manifest,
    deployment_manifest,
    sha256_file,
    verify_collada_resources,
    write_deterministic_archive,
)


class AssetBuilderTest(unittest.TestCase):
    def setUp(self) -> None:
        """Create isolated source, cache, build, and distribution directories."""
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.upstream = self.root / "upstream"
        self.upstream.mkdir()
        self.payload = b"solid link\nendsolid link\n"
        source = self.upstream / "models" / "link one.stl"
        source.parent.mkdir(parents=True)
        source.write_bytes(self.payload)
        self.lock_path = self.root / "source-lock.json"
        self.lock_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "modelId": "fixture-robot",
                    "repository": "https://example.invalid/fixture",
                    "revision": "abc123",
                    "baseUrl": self.upstream.as_uri(),
                    "license": "BSD-3-Clause",
                    "files": {
                        "models/link one.stl": {
                            "bytes": len(self.payload),
                            "sha256": hashlib.sha256(self.payload).hexdigest(),
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        """Remove all test artifacts and caches."""
        self.temporary.cleanup()

    def test_source_store_verifies_cache_and_supports_offline_rebuild(self) -> None:
        """An online fetch seeds exact content that a later offline build can reuse."""
        source_lock = SourceLock.load(self.lock_path)
        workspace = BuildWorkspace(self.root, "fixture")
        workspace.reset()
        first = workspace.source_store.materialize(
            source_lock,
            "models/link one.stl",
            workspace.build_dir / "meshes" / "link.stl",
        )
        (self.upstream / "models" / "link one.stl").unlink()
        second = workspace.source_store.materialize(
            source_lock,
            "models/link one.stl",
            workspace.build_dir / "meshes" / "link-copy.stl",
            offline=True,
        )
        self.assertEqual(first.read_bytes(), self.payload)
        self.assertEqual(second.read_bytes(), self.payload)

    def test_source_store_rejects_changed_upstream_content(self) -> None:
        """A mutable upstream URL cannot silently change a locked source input."""
        source_lock = SourceLock.load(self.lock_path)
        source = self.upstream / "models" / "link one.stl"
        source.write_bytes(b"changed upstream")
        workspace = BuildWorkspace(self.root, "fixture")
        with self.assertRaisesRegex(ValueError, "failed verification"):
            workspace.source_store.materialize(
                source_lock,
                "models/link one.stl",
                workspace.build_dir / "meshes" / "link.stl",
            )
        self.assertEqual(list((self.root / ".cache" / "sources").iterdir()), [])

    def test_source_store_repairs_corrupt_cache_entry(self) -> None:
        """A same-named cache entry is re-fetched unless its content is verified."""
        source_lock = SourceLock.load(self.lock_path)
        expected = source_lock.source("models/link one.stl")
        workspace = BuildWorkspace(self.root, "fixture")
        cached = self.root / ".cache" / "sources" / expected.sha256
        cached.parent.mkdir(parents=True)
        cached.write_bytes(b"corrupt")
        installed = workspace.source_store.materialize(
            source_lock,
            "models/link one.stl",
            workspace.build_dir / "meshes" / "link.stl",
        )
        self.assertEqual(installed.read_bytes(), self.payload)
        self.assertEqual(cached.read_bytes(), self.payload)

    def test_archive_is_deterministic_and_manifest_matches_members(self) -> None:
        """File timestamps and input order do not affect release bytes or metadata."""
        build_root = self.root / "build-input"
        first_file = build_root / "meshes" / "a.stl"
        second_file = build_root / "licenses" / "LICENSE.txt"
        first_file.parent.mkdir(parents=True)
        second_file.parent.mkdir(parents=True)
        first_file.write_bytes(self.payload)
        second_file.write_text("license\n", encoding="utf-8")
        first_archive = self.root / "first.tar.gz"
        second_archive = self.root / "second.tar.gz"

        write_deterministic_archive(
            [second_file, first_file], build_root, first_archive
        )
        first_file.touch()
        second_file.touch()
        write_deterministic_archive(
            [first_file, second_file], build_root, second_archive
        )

        self.assertEqual(sha256_file(first_archive), sha256_file(second_archive))
        with tarfile.open(first_archive, "r:gz") as archive:
            self.assertEqual(
                archive.getnames(),
                ["licenses/LICENSE.txt", "meshes/a.stl"],
            )
        self.assertEqual(
            set(build_file_manifest([first_file, second_file], build_root)),
            {"licenses/LICENSE.txt", "meshes/a.stl"},
        )

    def test_archive_rejects_symlink_member(self) -> None:
        """A release cannot disguise a symbolic link as a resolved regular file."""
        build_root = self.root / "build-input"
        target = build_root / "meshes" / "target.stl"
        link = build_root / "meshes" / "link.stl"
        target.parent.mkdir(parents=True)
        target.write_bytes(self.payload)
        link.symlink_to(target.name)
        with self.assertRaisesRegex(ValueError, "must not be a symlink"):
            write_deterministic_archive([link], build_root, self.root / "bad.tar.gz")

    def test_source_lock_rejects_traversing_path(self) -> None:
        """Source definitions cannot escape their immutable upstream root."""
        document = json.loads(self.lock_path.read_text(encoding="utf-8"))
        document["files"]["../outside"] = document["files"].pop(
            "models/link one.stl"
        )
        self.lock_path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid source path"):
            SourceLock.load(self.lock_path)

    def test_source_lock_rejects_non_normalized_path(self) -> None:
        """Equivalent spellings cannot collapse onto one reviewed source path."""
        document = json.loads(self.lock_path.read_text(encoding="utf-8"))
        document["files"]["models//link one.stl"] = document["files"].pop(
            "models/link one.stl"
        )
        self.lock_path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid source path"):
            SourceLock.load(self.lock_path)

    def test_checked_in_model_lock_and_definition_load(self) -> None:
        """CI validates every currently registered model's real source metadata."""
        repository_root = Path(__file__).resolve().parents[1]
        source_lock = SourceLock.load(
            repository_root / "models" / "unitree_b2w" / "source-lock.json"
        )
        definition = importlib.import_module("models.unitree_b2w.build")
        self.assertEqual(source_lock.model_id, "unitree-b2w-visual")
        self.assertEqual(len(source_lock.files), 19)
        self.assertTrue(callable(definition.build))
        definition.validate_source_identity(source_lock)
        self.assertEqual(
            definition.output_names(source_lock.revision),
            (
                "unitree-b2w-visuals-daadf41.tar.gz",
                "unitree-b2w-visuals-daadf41.files.json",
            ),
        )

    def test_collada_rejects_external_image_without_fixed_namespace(self) -> None:
        """Texture dependencies are detected across Collada namespace variants."""
        collada = self.root / "external.dae"
        collada.write_text(
            "<COLLADA><library_images><image><init_from>textures/body.png"
            "</init_from></image></library_images></COLLADA>",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "external resources"):
            verify_collada_resources(collada)

    def test_deployment_manifest_keeps_only_fetcher_fields(self) -> None:
        """Publisher metadata becomes a fetcher manifest with one immutable URL."""
        build_manifest = self.root / "build-manifest.json"
        build_manifest.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "modelId": "fixture-robot",
                    "version": "vendor-abc123",
                    "upstream": "https://example.invalid/vendor",
                    "artifact": {
                        "name": "fixture.tar.gz",
                        "bytes": 42,
                        "sha256": "a" * 64,
                    },
                    "installRoots": ["meshes"],
                    "files": {
                        "meshes/link.stl": {"bytes": 12, "sha256": "b" * 64}
                    },
                }
            ),
            encoding="utf-8",
        )
        result = deployment_manifest(
            build_manifest,
            "https://example.invalid/releases/v1/fixture.tar.gz",
        )
        self.assertEqual(
            result["artifact"]["url"],
            "https://example.invalid/releases/v1/fixture.tar.gz",
        )
        self.assertNotIn("upstream", result)

    def test_deployment_manifest_rejects_mutable_release_url(self) -> None:
        """A convenience latest URL cannot enter a reproducible deployment lock."""
        build_manifest = self.root / "build-manifest.json"
        build_manifest.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "modelId": "fixture-robot",
                    "version": "v1",
                    "artifact": {"bytes": 1, "sha256": "a" * 64},
                    "installRoots": ["meshes"],
                    "files": {"meshes/a": {"bytes": 1, "sha256": "b" * 64}},
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "immutable version"):
            deployment_manifest(
                build_manifest,
                "https://example.invalid/releases/latest/fixture.tar.gz",
            )

    def test_deployment_manifest_accepts_object_storage_version_id(self) -> None:
        """An exact object-store version query can identify immutable content."""
        build_manifest = self.root / "build-manifest.json"
        build_manifest.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "modelId": "fixture-robot",
                    "version": "v1",
                    "artifact": {"bytes": 1, "sha256": "a" * 64},
                    "installRoots": ["meshes"],
                    "files": {"meshes/a": {"bytes": 1, "sha256": "b" * 64}},
                }
            ),
            encoding="utf-8",
        )
        url = "https://objects.example.invalid/robot/model.tar.gz?versionId=abc123"
        result = deployment_manifest(build_manifest, url)
        self.assertEqual(result["artifact"]["url"], url)

    def test_deployment_manifest_rejects_empty_install_root(self) -> None:
        """Every atomically installed root must own at least one declared file."""
        build_manifest = self.root / "build-manifest.json"
        build_manifest.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "modelId": "fixture-robot",
                    "version": "v1",
                    "artifact": {"bytes": 1, "sha256": "a" * 64},
                    "installRoots": ["meshes", "textures"],
                    "files": {"meshes/a": {"bytes": 1, "sha256": "b" * 64}},
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "every install root"):
            deployment_manifest(
                build_manifest,
                "https://example.invalid/releases/v1/fixture.tar.gz",
            )

    def test_offline_source_store_rejects_missing_and_corrupt_cache(self) -> None:
        source_lock = SourceLock.load(self.lock_path)
        workspace = BuildWorkspace(self.root, "fixture")
        expected = source_lock.source("models/link one.stl")
        cached = workspace.source_store.cache_dir / expected.sha256
        destination = workspace.build_dir / "meshes" / "link.stl"
        with patch("urllib.request.urlopen", side_effect=AssertionError("network")):
            for contents in [None, b"x" * len(self.payload)]:
                with self.subTest(contents=contents):
                    if contents is not None:
                        cached.parent.mkdir(parents=True, exist_ok=True)
                        cached.write_bytes(contents)
                    with self.assertRaisesRegex(FileNotFoundError, "not cached"):
                        workspace.source_store.materialize(
                            source_lock, "models/link one.stl", destination, offline=True
                        )
                    self.assertFalse(destination.exists())

    def test_b2w_urdf_keeps_visuals_and_normalizes_resources(self) -> None:
        definition = importlib.import_module("models.unitree_b2w.build")
        source = self.root / "source.urdf"
        output = self.root / "visual.urdf"
        source.write_text(
            '<robot name="b2w"><link name="base"><visual><geometry>'
            '<mesh filename="package://b2w_description/meshes/base.dae"/>'
            '</geometry><material name="old"/></visual>'
            '<collision><geometry><box size="1 1 1"/></geometry></collision>'
            '</link></robot>',
            encoding="utf-8",
        )
        assets = definition.prepare_urdf(source, output)
        root = ET.parse(output).getroot()
        self.assertEqual([path.as_posix() for path in assets], ["meshes/base.dae"])
        self.assertEqual(root.get("name"), "unitree_b2w_visual")
        self.assertEqual(root.findall(".//collision"), [])
        self.assertEqual(root.find(".//mesh").get("filename"), "meshes/base.dae")
        self.assertEqual(root.find(".//material").get("name"), "material_001")
        self.assertIn("SPDX-License-Identifier: BSD-3-Clause", output.read_text())

    def test_b2w_rejects_unsafe_mesh_paths(self) -> None:
        definition = importlib.import_module("models.unitree_b2w.build")
        for reference in [
            "https://example.invalid/body.dae",
            "package://b2w_description/meshes/../../outside.dae",
            "package://b2w_description//meshes/body.dae",
            "package://other/meshes/body.dae",
        ]:
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                definition.mesh_path(reference)


if __name__ == "__main__":
    unittest.main()
