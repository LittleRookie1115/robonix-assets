# Robonix Assets

Versioned runtime assets used by Robonix deployments and examples.

This Git repository contains only small manifests, checksums, and licensing
information. Binary payloads are published as GitHub Release assets so cloning
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

## Licensing

Repository-authored metadata and documentation are licensed under Apache-2.0.
Release payloads may contain third-party material governed by separate terms.
Read [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the asset manifest
before downloading or redistributing a payload.
