# Project Outputs

Each subfolder is a project tracked by Agent-Project-Manager. Structure rules:
`.github/instructions/outputs-folder.instructions.md`

## Structure

```
outputs/
├── _memory/                  # Long-term cross-project memory (JSON + FTS5 SQLite)
├── morning_reports/          # Daily morning reports (morning_report_YYYY-MM-DD.md)
├── {project-slug}/           # One folder per project
│   ├── tasks.json                  # ClickUp task plan
│   ├── project-plan/               # project_plan.md (+ DOCX/PDF exports, metadata.json)
│   ├── project-docs/               # ClickUp Doc spec.json + doc_ids.json
│   └── research/                   # Reference PDFs, extracted text
└── README.md                 # This file
```

## Projects

| Project | Slug | Contents |
|---|---|---|
| Control Center | `control-center` | tasks.json |
| Julia Series | `julia-series` | project-docs (spec + ClickUp doc IDs) |
| Klipper | `klipper` | tasks.json |
| MDS (Material Drying System) | `mds` | project-docs (spec + ClickUp doc IDs) |
| Penrose Pellet Extruder | `penrose-pellet-extruder` | project-docs (spec + ClickUp doc IDs) |

ClickUp IDs and external links for every project live in `_memory/project_registry.json`.
