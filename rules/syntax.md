# Project Markdown Syntax Rules

These rules apply to project-related Markdown files such as:

- `README.md`
- `PLANNING.md`
- `DOCUMENTATION.md`
- `testing/TESTING.md`
- and similar project documents.

## 1. General

- Do **not** use YAML frontmatter in project Markdown files.
- Each file:
  - starts with a single `#` heading as the document title,
  - may have a second line with attributes like:
    `+doc:readme|planning|documentation|testing +project:<slug>`
- No emojis in project Markdown files.

Example:

```markdown
# Brain Graph – Planning

+doc:planning +project:brain-graph

...
```

## 2. Headings vs. tags

- A line starting with `#` (hash + space) is always a **heading**, not a tag.
- Use `#` only once for the main title line.
- `##`, `###`, … are for section headings.

Example:

```markdown
# Brain Graph – Technical Documentation

## Architecture overview

...
```

## 3. Tags with `#tag`

- Tags are expressed as `#tag` and are used for topics/categories/labels.
- Rules for `#tag`:
  - no spaces inside the tag: `#machine-learning`, not `#machine learning`,
  - must **not** appear at the very beginning of a line (to avoid confusion with headings),
  - should be separated from text by a space or punctuation,
  - use tags only where they add real semantic value (not on every line),
  - avoid creating multiple near-duplicate tags for the same concept; prefer reusing an existing tag instead of inventing several slightly different ones.

Examples:

```markdown
This component handles local LLM inference. #llm #inference  
Plan to add support for graph-based retrieval. #graph #rag
```

## 4. Locations and organisations with `@`

- Use `@slug` for locations or organisations.
- Rules:
  - no spaces inside the slug: `@homelab`, `@kindergarten`, `@internal-tools`,
  - typically used inline in sentences, not as standalone markers at the start of a line.

Examples:

```markdown
Deployment target is the main node in the @homelab.  
This document is relevant for the @internal-tools team.
```

## 5. People with `&`

- Use `&slug` for people.

Examples:

```markdown
Primary maintainer: &toby  
Planned review session with &emma.
```

## 6. Attributes with `+key:value`

Attributes encode structured metadata and task state.  
There are two supported usage patterns:

### 6.1 Inline attributes

- `+key:value` can appear inline anywhere in a line.
- The value runs until the next whitespace.

Example:

```markdown
Implement local embedding service API. +status:todo +priority:high +effort:medium +project:brain-graph
```

### 6.2 Line-leading attributes with content

- A line may **start** with `+key:value`, followed by free text and more attributes.
- This is typically used for tasks (`+todo:`) and similar entries.

Example:

```markdown
+todo: Termin mit &emma ausmachen, für gemeinsames Treffen @cafe +date:2025-12-20 +priority:medium
```

In this example:

- `+todo:` defines the type of the entry,
- the following text is the human-readable description,
- further `+key:value` pairs (`+date:…`, `+priority:…`) add metadata.

## 7. Official attribute keys

The following attributes are recognised and should be used consistently:

- `+todo:…` – task entries, usually at the start of a line  
- `+status:todo|doing|review|blocked|done` – lifecycle state  
- `+priority:low|medium|high` – priority level  
- `+effort:tiny|small|medium|large` – rough effort estimation  
- `+doc:readme|planning|documentation|testing` – document role/type  
- `+project:<slug>` – project identifier  
- `+date:YYYY-MM-DD` – date in ISO format

Examples:

```markdown
+todo: Implement local embedding service API. +status:todo +priority:high +effort:medium +project:brain-graph  
+todo: Add integration tests for ingestion pipeline. +status:todo +priority:medium +effort:large +project:brain-graph +date:2025-12-10
```

## 8. `+status:` lifecycle

- Allowed values: `todo`, `doing`, `review`, `blocked`, `done`
- Interpret them as a simple lifecycle:

  - normal flow: `todo` → `doing` → `review` → `done`  
  - `blocked` is a side-state that can be entered from any state except `done`

- Defaults:
  - if a new `+todo:` line has no `+status:`, treat it as `+status:todo`.

- Agents may:
  - set `+status:todo` or `+status:doing` when they create a new `+todo:` entry,
  - change `todo` → `doing` when work on that item is explicitly started in this conversation,
  - change `doing` → `review` when a complete solution is proposed and the next step is “user tests/reviews”.

- Agents must **not**:
  - move any item to `+status:done` without explicit confirmation by the user
    (e.g. user says “das ist erledigt” / “markier das als done”),
  - change `done` back to another state without explicit user request.

## 9. Metadata not managed by agents

- Creation and update timestamps (created/updated) are **not** stored in these Markdown files and are **not** managed by agents.
- These values are handled by external tooling (e.g. git hooks, PKMS import pipeline).
- `+id:…` may exist in some contexts, but agents should **not** introduce or modify it in project Markdown files unless the user explicitly asks for it.
