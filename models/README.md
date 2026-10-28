<!-- SPDX-License-Identifier: BSD-3-Clause -->

# Model build definitions

Each externally distributed robot model has one directory under `models/` with:

```text
models/<model_name>/
├── README.md
├── source-lock.json
└── build.py
```

`source-lock.json` pins the upstream repository, immutable revision, license,
base URL, and exact byte size and SHA-256 of every consumed source file.
`build.py` contains only model-specific preparation such as Xacro expansion,
package URI rewriting, visual-resource selection, format conversion, or
collision removal. It must use `asset_builder` for verified source acquisition,
deterministic archives, and generated file manifests.

A build definition must:

- consume only files declared by its source lock and reject unused lock entries;
- write Mesh and texture paths relative to the generated URDF using `/`;
- include only redistributable visual resources and required licenses;
- reject undeclared external dependencies in prepared resources;
- produce identical output hashes from the same source lock and code;
- work with `build_model.py <model_name> --offline` after one online build.

Generated build trees, source caches, archives, manifests, and URDF outputs stay
outside Git under `build/`, `.cache/`, and `dist/`. Publish reviewed files from
`dist/` as immutable release assets.
