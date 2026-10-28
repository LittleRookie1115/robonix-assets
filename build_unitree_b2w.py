#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

"""Backward-compatible entry point for the Unitree B2-W release build."""

from models.unitree_b2w.build import build


if __name__ == "__main__":
    build()
