# Third-party notices

## Webots office seed

`webots-office-seed-v1.tar.gz` is an unchanged cache of Cyberbotics Webots
assets. It contains PROTO files, meshes, textures, HDR images, and audio files
in their original formats.

The payload includes files governed by the
[Webots Assets License Agreement](https://cyberbotics.com/webots_assets_license)
and files individually marked as Apache-2.0. Under the Webots Assets License,
Cyberbotics retains copyright and ownership; the asset license must not be
changed; formats must not be converted; and the assets may be run only with
Webots. Redistribution of the original or modified assets is permitted only
under those conditions.

Robonix does not grant additional rights to these third-party files. The
Release payload must not be presented as a general-purpose model, texture, or
media library.

## Model build tooling

`asset_builder/`, `models/`, `build_model.py`, `build_unitree_b2w.py`, the
builder tests, and `.github/workflows/test.yml` are imported from
`LittleRookie1115/robonix-model-assets-test` at
`d72b74878f0cd2467277be5f0c3f806bf4f4e515`. Their BSD-3-Clause SPDX notices
are preserved. The complete original license, including its existing Zhenyu
Zhang and Unitree copyright notices, is retained at
[licenses/model-builder-BSD-3-Clause.txt](licenses/model-builder-BSD-3-Clause.txt).
The Apache-2.0 repository license does not relicense these imported sources.

## Unitree B2-W visual model

The proposed `unitree-b2w-daadf41-v1` payload is derived from
`unitreerobotics/unitree_ros` revision
`daadf41ee9afce8f90fdc09a98506012691fa122`, package
`robots/b2w_description`, under BSD-3-Clause.

Copyright (c) 2016-2022 HangZhou YuShu TECHNOLOGY CO.,LTD. ("Unitree Robotics").
The 17 Collada meshes remain byte-for-byte upstream files. The separately
distributed URDF removes collisions, normalizes material names, and replaces
package URIs with local mesh references; it retains BSD-3-Clause.

The archive contains the exact upstream license at
`licenses/UNITREE_ROS_LICENSE-BSD-3-CLAUSE.txt`. Its complete text is also
available in [licenses/UNITREE_ROS_LICENSE-BSD-3-CLAUSE.txt](licenses/UNITREE_ROS_LICENSE-BSD-3-CLAUSE.txt).
Retain these notices with any redistribution. Source locks and transformation
details are documented in [models/unitree_b2w/README.md](models/unitree_b2w/README.md).
