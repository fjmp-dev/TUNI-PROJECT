# Documentation

| Document | Purpose |
|---|---|
| [`PROJECT_REPORT.pdf`](PROJECT_REPORT.pdf) (`.docx`) | Project report for the supervisor: context, what was done, results, validation, known limitations, open items, handover. |
| [`TECHNICAL_DOCUMENTATION.pdf`](TECHNICAL_DOCUMENTATION.pdf) (`.docx`) | **Reference document.** Architecture, MiR and UR5e integration, interface, security, operation, troubleshooting, testing. Re-checked against the code at release v1.0. |
| [`MIR_SUITE_MANUAL.md`](MIR_SUITE_MANUAL.md) | Operator manual (13 July 2026), with UI screenshots in `manual_images/`. Where it disagrees with the technical documentation, the technical documentation is authoritative. `build_manual.sh` regenerates a .docx from it. |
| [`architecture.png`](architecture.png) | System diagram (source: `architecture.dot`, render with `dot -Tpng -Gdpi=220`). |
| `network_remote_access.md` | Network map and remote-access options. |
| `PLAN_REFACTORIZACION.md` | Refactor plan and status (July 2026). |
| `EXTERNAL_PROJECTS.md` | The vendored external projects. |
| `referencias/screenshots/` | Early screenshots (June 2026). |

Each component folder (`UR/`, `MiR/`, `PERIPHERAL/`, …) has its own README and
`documentation/`. `SECURITY.md` at the repository root records the hardening history.

**No credentials are kept in this repository.** They live only on the Jetson, in
`config/.env` (template: `config/env.example`) and `UI/backend/data/`.
