# Third-party dependency record

This document records dependency attribution, not legal clearance or a project license choice. Before distributing the source or image, review the actual upstream licenses and applicable notice obligations. No license has been chosen for Invaris itself.

## Python dependencies

`dependency-inventory.json` records all 103 versions pinned in `requirements.lock`, using metadata from their installed distributions in the isolated reproduction environment on October 11, 2026. It includes transitive packages, development tools, declared license metadata, and license-file names where supplied. Packages with missing or long-form-only license metadata are explicitly marked for review rather than assigned an invented SPDX expression.

| Direct dependency | Pinned version | Declared license metadata |
|---|---|---|
| Neatlogs | 1.4.26 | MIT |
| OpenAI Python SDK | 2.54.0 | Apache-2.0 |
| Pydantic | 2.14.0 | MIT |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| filelock | 4.1.0 | MIT |
| pytest (development) | 9.1.1 | MIT |
| Ruff (development) | 0.17.0 | MIT |

Declared metadata can be incomplete and does not replace upstream license text. The inventory is a point-in-time record, not an SBOM attestation or proof of exploitability/security. `pip check` and the dependency vulnerability audit are separate checks; absence of known advisories does not prove absence of vulnerabilities.

## Native fixture

The current fixture image was set up and its OpenSSL 3.5.9 runtime confirmed. It compiles that version from the SHA-256-verified upstream source release. The Dockerfile copies upstream `LICENSE.txt` into `/usr/share/doc/invaris/openssl-LICENSE.txt` in the runtime image. Upstream license authority: `https://github.com/openssl/openssl/blob/openssl-3.5.9/LICENSE.txt`. The Debian base and installed operating-system packages retain their own package copyright/license records; no single blanket license is claimed for the image. The Python inventory does not enumerate Debian packages. Hosted cold integration previously failed its 1 MB output limit; after the quiet `DockerFixture.build` fix, full integration CI run `38087724134` succeeded on commit `08cb143`.

## Entire and external services

The downloaded Entire executable is a development integration tool in the ignored `.tools` directory, not bundled as an Invaris runtime dependency. The official Entire Graph plugin `v0.4.0` works locally on Windows; its version/checksum verification does not establish hackathon eligibility or substitute for its license review. Neatlogs and cfo.ai account/service terms must also be reviewed separately from SDK dependency licenses. No external credentials are included in this record.
