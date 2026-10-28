# Robonix Assets

Versioned runtime assets used by Robonix deployments and examples.

This Git repository contains small manifests, checksums, licensing information,
and reproducible model build definitions. Binary payloads are published as
GitHub Release assets so cloning
Robonix does not download large files or retain them in Git history.

## Download policy

Robonix downloads release assets through the following mirror by default:

```text
https://ghfast.top/<original GitHub release URL>
```

Deployments may override the mirror or the complete asset URL. Every download
must be verified against the SHA-256 value in its manifest before extraction.
An HTTP success status alone is not sufficient because a mirror may return an
HTML error page instead of the requested archive.

## Assets

| Asset | Manifest | Purpose |
|---|---|---|
| `webots-office-seed-v1` | [`manifests/webots-office-seed-v1.yaml`](manifests/webots-office-seed-v1.yaml) | Minimal Cyberbotics Webots cache required by the Robonix Tiago office example. |
| `unitree-b2w-daadf41-v1` (pending publisher) | [`manifests/unitree-b2w-daadf41-v1.yaml`](manifests/unitree-b2w-daadf41-v1.yaml) | Unitree B2-W visual meshes and generated URDF pinned to upstream `daadf41ee9afce8f90fdc09a98506012691fa122`. |

## Build a model

Use Python 3.11 or newer; the builder uses only the standard library.
`asset_builder/` contains common source verification and deterministic archive
code, and `models/<model_name>/` contains each recipe and exact source lock.
See [models/README.md](models/README.md) for the recipe contract and
[the B2-W definition](models/unitree_b2w/README.md) for provenance and licenses.

```bash
python3 build_model.py unitree_b2w
python3 build_model.py unitree_b2w --offline
```

The initial build downloads only locked files and verifies their sizes and
SHA-256 values. For a completely offline first build, populate the ignored
`.cache/sources/` with previously verified content-addressed source files.
The build rechecks every cache entry before use. It writes the ignored
`build/` and `dist/` directories; generated meshes, archives, and URDFs are
release attachments and must stay out of Git.

Run the common tests and check two offline builds:

```bash
python3 -m compileall -q asset_builder models tests build_model.py build_unitree_b2w.py
python3 -m unittest discover -s tests -v
python3 build_model.py unitree_b2w --offline
sha256sum dist/* > .cache/first-build.sha256
python3 build_model.py unitree_b2w --offline
sha256sum -c .cache/first-build.sha256
```

## Prepare and publish a model release

1. Review the source lock, provenance, BSD notices, archive members, generated
   URDF, and `dist/unitree-b2w-visuals-daadf41.files.json`.
2. Generate the deployment manifest using the proposed immutable canonical URL:

   ```bash
   python3 build_model.py unitree_b2w --offline \
     --artifact-url https://github.com/syswonder/robonix-assets/releases/download/unitree-b2w-daadf41-v1/unitree-b2w-visuals-daadf41.tar.gz
   ```

3. Stage the archive, generated URDF, file manifest, and
   `dist/unitree_b2w.model-assets.json` (named `model-assets.json` for deployment),
   together with checksums and the applicable notices. Verify the staged bytes
   against the registry entry. If rebuilding changes the gzip checksum, follow
   the [B2-W byte preservation policy](models/unitree_b2w/README.md).
4. An administrator with write access must land the reviewed source and
   registry changes, create tag `unitree-b2w-daadf41-v1` at that reviewed commit,
   and upload the exact staged files. Use a draft release for inspection,
   then publish it. Never replace assets on an existing version.
5. After publication, download through both the canonical URL and the default
   mirror, verify exact size and SHA-256, and run the consumer fetch test.
   Mark the registry entry published only after these checks pass.

The proposed B2-W URL is **pending publisher**. A local build or passing local
fetch test does not establish public availability. The preparation account has
no push permission to this repository.

Deployment `model-assets.json` keeps the canonical GitHub release URL.
The Robonix fetcher applies `--mirror https://ghfast.top/` by default to
canonical GitHub release URLs. `--mirror ''` selects direct access. An explicit
`--artifact-url` bypasses mirror rewriting, which also supports local HTTP
testing. These options do not change any expected byte size or hash.

## Licensing

Repository-authored metadata and documentation are licensed under Apache-2.0.
Imported BSD-marked builder code, recipe documentation, tests, and CI retain
BSD-3-Clause under [their original license](licenses/model-builder-BSD-3-Clause.txt).
Unitree model files and the derived visual URDF also retain BSD-3-Clause.
Release payloads may contain third-party material governed by separate terms.
Read [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the asset manifest
before downloading or redistributing a payload.
