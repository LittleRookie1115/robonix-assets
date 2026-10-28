<!-- SPDX-License-Identifier: BSD-3-Clause -->

# Unitree B2-W release definition

This model definition consumes only files declared in `source-lock.json` from
the pinned `unitreerobotics/unitree_ros` revision. `build.py` contains the
B2-W-specific transformation: it removes collision elements, normalizes
material names, rewrites `package://b2w_description/` visual Mesh references,
and rejects Collada files with undeclared external resources.

Run it through the repository entry point:

```bash
python3 build_model.py unitree_b2w
```

After one online build, verify reproducibility without network access:

```bash
python3 build_model.py unitree_b2w --offline
```

## Provenance and licenses

- Model upstream: `https://github.com/unitreerobotics/unitree_ros`
- Model revision: `daadf41ee9afce8f90fdc09a98506012691fa122`
- Source package: `robots/b2w_description`
- Inputs: 17 Collada visual meshes, one URDF, and the upstream BSD license;
  every input has a locked size and SHA-256 in `source-lock.json`.
- Builder upstream: `https://github.com/LittleRookie1115/robonix-model-assets-test`
- Builder revision: `d72b74878f0cd2467277be5f0c3f806bf4f4e515`
- Imported layout: `asset_builder/`, `models/`, `build_model.py`,
  `build_unitree_b2w.py`, tests, and CI. The builder implementation and source
  lock are preserved without changes.
- Builder license: BSD-3-Clause, retained in
  `../../licenses/model-builder-BSD-3-Clause.txt`.
- Model license: BSD-3-Clause. The archive includes the exact locked upstream
  license at `licenses/UNITREE_ROS_LICENSE-BSD-3-CLAUSE.txt`. The repository
  also carries its complete text in `../../licenses/`.

The generated URDF keeps the source link, joint, inertial, and visual geometry
data while removing collision geometry and changing the robot/material names
and mesh references. Mesh files are copied without conversion. This is a
visual model; its URDF is distributed separately from the mesh archive.

## Proposed official release

The proposed tag is `unitree-b2w-daadf41-v1`. The official registry entry is
`../../manifests/unitree-b2w-daadf41-v1.yaml`. Its canonical URL is a publication
candidate until an administrator publishes and verifies the release.

The existing personal release `unitree-b2w-daadf41-r2` supplies the reference
archive, URDF, and file manifest. The official candidate preserves those
exact bytes:

| File | Bytes | SHA-256 |
|---|---:|---|
| `unitree-b2w-visuals-daadf41.tar.gz` | 18316148 | `fa4579b821f0fbac8376c6bcf0f5ce339a7f73b03b54ecb835f198f1276f5751` |
| `unitree_b2w_visual.urdf` | 18032 | `3798cc5499c0f90ab1cbe8fd80dd17f4624ba99fdf82b3fdbcf76c0de65abe0b` |
| `unitree-b2w-visuals-daadf41.files.json` | 3327 | `83fc86dfe6389db602631c3758b467febdb3f9df040fa64b12460d996e6b1167` |

The file manifest describes all 18 archive members and the separate generated
URDF. The deployment manifest pins the canonical official archive URL and
must be generated from the manifest belonging to the bytes being uploaded.
Never overwrite an existing release asset with recompressed bytes. If a future
Python/zlib version produces a different gzip checksum, compare every member
against the original file manifest and keep the reviewed existing archive for
this release, or publish different bytes under a new tag with new metadata.
