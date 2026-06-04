---
name: clickup-docs
description: 'Create and maintain ClickUp Docs for every Space and Folder. Each Doc has one page per project (list item) with a high-level PRD, project overview, team, links to GitHub, Notion, Google Docs, external references, and status. Trigger keywords: create doc, update doc, project doc, PRD, folder doc, space doc, project page, documentation, link repo, add reference.'
argument-hint: 'Specify the Space or Folder to document, or a specific project name.'
user-invocable: true
disable-model-invocation: false
---

# ClickUp Docs

Every Space and Folder gets a living Doc that is the authoritative reference for everything in that part of the hierarchy. Each project (list item) gets its own page in the Doc.

## Doc Hierarchy Rule

```
Space
└── Folder
    └── Doc: "[Folder Name] — Project Reference"
        ├── Page: Overview & Index  (what's in this folder, color coding meaning, links)
        ├── Page: [Project A Name]  (PRD, status, team, links)
        ├── Page: [Project B Name]
        └── ...
```

One Doc per Folder. One page per project. If a Space has no Folders (flat lists), one Doc per Space.

---

## Project Page Template

Every project page MUST contain these sections:

### [Project Name]

**Status:** 🟢 Active / 🟡 Paused / 🔴 On Hold  
**ClickUp List:** [link]  
**Last Updated:** YYYY-MM-DD  

---

#### 1. What Is This Project?
1–2 sentences. What does this product/system do? Who uses it?

#### 2. Why Does It Exist?
Business case / customer need. Why is the company building this?

#### 3. Current Phase
`Concept` / `Design` / `Build` / `Test` / `Live` / `Maintenance` / `Paused`

#### 4. Team
| Role | Person |
|------|--------|
| Lead | ... |
| Engineers | ... |
| Customer | ... |

#### 5. Key Milestones
| Milestone | Target Date | Status |
|-----------|-------------|--------|
| ... | ... | ... |

#### 6. Top Open Risks
Pulled from `risk_log.json` — top 3 open risks for this project.

#### 7. External Links & Resources
| Resource | Link | Notes |
|----------|------|-------|
| GitHub Repo | https://github.com/... | Main codebase |
| Google Drive | https://drive.google.com/... | CAD files, BOM |
| Notion Page | https://notion.so/... | Design specs |
| Obsidian Vault | obsidian://... | Engineering notes |
| Datasheet / Reference | https://... | ... |

#### 8. Open Questions
- [ ] Question 1 (owner: @Name, due: YYYY-MM-DD)

#### 9. Notes & History
Free-form. Decisions, meeting outcomes, context that doesn't fit elsewhere.

---

## Steps — Create a Folder Doc

1. Get the Folder ID and all its Lists: `GET /folder/{folder_id}/list`
2. For each List (project), retrieve its ClickUp tasks to understand current phase and status.
3. Load project memory for each project slug from `project_registry.json`.
4. Draft all project pages using the template above.
5. Show the user the draft structure — confirm before writing.
6. Create the Doc: `POST /space/{space_id}/doc` or via MCP `Create Document`
7. For each project, create a page: `POST /doc/{doc_id}/page` or via MCP `Create Document Page`
8. Record the Doc ID and page IDs in `project_registry.json` under each project.

## Steps — Update an Existing Project Page

1. Retrieve the Doc page: `GET /doc/{doc_id}/page/{page_id}` or MCP `Get Document Pages`
2. Update the specific section that has changed (status, milestone, risk, link).
3. Write back: `PUT /doc/{doc_id}/page/{page_id}` or MCP `Update Document Page`
4. Log the update in `interaction_log.json`.

## Steps — Add an External Link to a Project Page

1. Identify the project and the resource to link (GitHub, Notion, Google Drive, etc.).
2. Retrieve the project's ClickUp Doc page ID from `project_registry.json`.
3. Append to the External Links section of the page.
4. Also update `project_registry.json` with the link so future sessions can reference it without fetching the Doc.

---

## ClickUp API — Docs Endpoints

| Action | Method | Endpoint |
|--------|--------|----------|
| Create Doc | POST | `/team/{team_id}/doc` |
| Get Doc | GET | `/doc/{doc_id}` |
| List Doc Pages | GET | `/doc/{doc_id}/page` |
| Get Page Content | GET | `/doc/{doc_id}/page/{page_id}` |
| Create Page | POST | `/doc/{doc_id}/page` |
| Update Page | PUT | `/doc/{doc_id}/page/{page_id}` |

Or use MCP tools: `Create Document`, `Create Document Page`, `Update Document Page`, `Get Document Pages`.

---

## Link Format Standards

When inserting external links into a Doc page, use this standard format so they are scannable:

```
| GitHub — fracktal-works/penrose-fw | https://github.com/... | Firmware source |
| Google Drive — Penrose CAD | https://drive.google.com/... | Rev C drawings |
| Notion — Penrose Design Spec | https://notion.so/... | Feature decisions |
| Confluence / Obsidian | obsidian://vault/... | Engineering notes |
| Supplier Datasheet | https://... | Auger dimensions |
```

---

## Folder Docs to Create (R&D Hardware)

The following Docs are the highest priority for creation:

| Folder | Doc Title | Projects to Document |
|--------|-----------|----------------------|
| R&D / Hardware | Hardware Projects — Reference | Penrose, MDS, Apollo 200/300, Volterra ALF, Julia Series, Dragon/Twin Dragon, Snowflake |
| R&D / Software | Software Projects — Reference | RapidTool Shadow Box, RapidTool Fixture, RapidTool SoftJaws, Control Center, Fracktory Slicer, Fracktory Portal, VSP Engine, Klipper |
| R&D / Application Engineering | Application Engineering — Reference | AE Backlog, 3D Printed EPS Molds |

---

## Edge Cases

- If a project has no GitHub repo or Notion page yet, leave the cell blank with a `[ ]` to-do marker.
- Never hardcode ClickUp IDs in the skill — always look them up from `project_registry.json`.
- If a Doc for the Folder already exists, update it — do not create a duplicate.
- Page creation requires the Doc to exist first. Check before attempting page creation.
- ClickUp Docs support markdown in page content. Use it for tables, headings, and links.
