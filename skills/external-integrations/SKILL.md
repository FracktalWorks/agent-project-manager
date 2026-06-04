---
name: external-integrations
description: 'Connect ClickUp projects to external tools: GitHub (repos, issues, PRs), Notion (pages, databases), Google Docs/Sheets (docs, BOMs, budgets), and Obsidian (vault notes). Read metadata, link resources in ClickUp Docs, and surface cross-tool status in project tracking. Trigger keywords: github, notion, google docs, google sheets, obsidian, link repo, link doc, sync, connect, external, BOM, CAD, reference.'
argument-hint: 'Name the tool and the project you want to connect.'
user-invocable: true
disable-model-invocation: false
---

# External Integrations

Link ClickUp projects to the tools where the actual work lives. The goal is not to duplicate data — it is to make every external resource discoverable from ClickUp and the project Doc without having to hunt for it.

## Supported Integrations

| Tool | What We Read | What We Link |
|------|-------------|--------------|
| **GitHub** | Repos, open issues, recent commits, PR status | Repo URL, issue list, latest release |
| **Notion** | Page title, last edited, key properties | Page URL, database record URL |
| **Google Docs** | Doc title, last modified | Doc URL, folder URL |
| **Google Sheets** | Sheet title, tab names | Sheet URL, specific tab URL |
| **Obsidian** | Note title (local vault only) | `obsidian://open?vault=...&file=...` URI |

---

## GitHub

### Read GitHub Repo Info
```bash
python scripts/integrations/github_info.py \
    --repo "fracktal-works/penrose-firmware" \
    --output ".tmp/{project-slug}/github_info.json"
```
Returns: repo description, language, last commit date, open issues count, latest release tag.

### List Open Issues for a Project
```bash
python scripts/integrations/github_info.py \
    --repo "fracktal-works/penrose-firmware" \
    --mode issues --state open --limit 10
```

### Link Repo to Project
After fetching repo info, update the project's ClickUp Doc page (via `clickup-docs` skill) and `project_registry.json`:
```json
{
  "slug": "penrose-pellet-extruder",
  "external_links": {
    "github": "https://github.com/fracktal-works/penrose-firmware",
    "github_issues": "https://github.com/fracktal-works/penrose-firmware/issues"
  }
}
```

### GitHub → ClickUp Task Links
For significant GitHub issues (bugs, feature work), create a corresponding ClickUp task and store both IDs:
```json
{
  "clickup_task_id": "86d37jqg4",
  "github_issue": "https://github.com/fracktal-works/penrose-firmware/issues/42",
  "sync_direction": "github_is_source"
}
```
Do not auto-create tasks from every GitHub issue — only escalated / customer-facing ones.

### Required Environment Variable
```
GITHUB_TOKEN=ghp_...
```

---

## Notion

### Read Notion Page
```bash
python scripts/integrations/notion_info.py \
    --page-id "{notion_page_id}" \
    --output ".tmp/{project-slug}/notion_info.json"
```
Returns: page title, last edited time, properties (if database page).

### Link Notion Page to Project
Update `project_registry.json` and the ClickUp Doc External Links section:
```json
{
  "external_links": {
    "notion_design_spec": "https://notion.so/fracktal/{page_id}"
  }
}
```

### Required Environment Variables
```
NOTION_API_TOKEN=secret_...
```

---

## Google Docs & Sheets

### Read Doc / Sheet Metadata
```bash
python scripts/integrations/google_info.py \
    --file-id "{google_file_id}" \
    --output ".tmp/{project-slug}/google_info.json"
```

### Common Use Cases

| Use Case | What to Link |
|----------|-------------|
| CAD / BOM | Google Sheet with part list and supplier info |
| Project Budget | Google Sheet with cost tracking |
| Meeting Notes | Google Doc per meeting or per project |
| Customer Requirements | Google Doc shared with customer |
| Test Report | Google Doc with test results and sign-off |

### Required Environment Variables
```
GOOGLE_SERVICE_ACCOUNT_JSON=path/to/service_account.json
```
or OAuth credentials via `google_auth.py --setup`.

---

## Obsidian

Obsidian is a local-first tool — no API. Links are deep links using the `obsidian://` URI scheme.

### URI Format
```
obsidian://open?vault={VaultName}&file={NoteTitle}
```
Example: `obsidian://open?vault=Fracktal&file=Penrose+Design+Notes`

### How to Register an Obsidian Link
Ask the user for the vault name and note/folder path, then store in `project_registry.json`:
```json
{
  "external_links": {
    "obsidian_notes": "obsidian://open?vault=Fracktal&file=Projects%2FPenrose"
  }
}
```

---

## Project Registry — External Links Schema

All external links for a project are stored in `project_registry.json`. This is the single source of truth for "where does this project live?"

```json
{
  "slug": "penrose-pellet-extruder",
  "name": "Penrose Pellet Extruder",
  "clickup_list_id": "901611050642",
  "clickup_doc_id": null,
  "external_links": {
    "github_repo": "https://github.com/fracktal-works/penrose-firmware",
    "github_issues": "https://github.com/fracktal-works/penrose-firmware/issues",
    "notion_spec": "https://notion.so/fracktal/...",
    "google_bom": "https://docs.google.com/spreadsheets/d/...",
    "google_budget": "https://docs.google.com/spreadsheets/d/...",
    "google_meeting_notes": "https://docs.google.com/document/d/...",
    "obsidian_notes": "obsidian://open?vault=Fracktal&file=Projects%2FPenrose",
    "datasheet_auger": "https://...",
    "datasheet_motor": "https://..."
  }
}
```

---

## Workflow — Link a New Resource to a Project

1. Ask the user: which project? which tool? what is the URL / path?
2. Validate the URL is accessible (basic HTTP check if it is a public URL).
3. Update `project_registry.json` with the new link under `external_links`.
4. Retrieve the project's ClickUp Doc page ID from `project_registry.json`.
5. Append the link to the External Links section of the Doc page via `clickup-docs` skill.
6. Confirm to user: "Linked [resource] to [project]. Visible in the Hardware Projects Doc."

---

## Workflow — Surface All Links for a Project

When a user asks "where are the files for project X?":
1. Load `project_registry.json`, find the project by name or slug.
2. Present all `external_links` as a formatted table.
3. If the ClickUp Doc exists, offer to open it.

---

## Edge Cases
- If the user doesn't know the exact file ID, ask for the URL and parse the ID from it.
- Notion URLs contain the page ID as the last segment: `notion.so/workspace/{page_id}`.
- Google Drive file IDs are in URLs: `docs.google.com/spreadsheets/d/{file_id}/edit`.
- Never store OAuth tokens or service account keys in `project_registry.json`. Use `.env` only.
- GitHub private repos require `GITHUB_TOKEN` with `repo` scope.
