# Authoring OKF bundles

Kosha produces and maintains OKF bundles, but they are plain files — you can write or edit one by hand, validate it, and serve it. This guide covers the on-disk format Kosha reads and writes: concept documents, the reserved `index.md`/`log.md` files, Kosha's frontmatter extensions, and the conformance rules the validator enforces.

A **bundle** is a directory of Markdown concept documents plus per-directory `index.md` maps and an optional `log.md`. It is the OKF unit of distribution: portable, tool-neutral, and readable by any editor or agent without Kosha installed.

## Anatomy

```text
bundles/northwind/
  index.md                 # bundle root — table of contents (okf_version only)
  log.md                   # dated change history (optional)
  policies/
    index.md               # directory map
    refunds.md             # a concept (concept_id = "policies/refunds")
    returns/
      index.md
      standard.md          # concept_id = "policies/returns/standard"
      gold-members.md
  entities/  playbooks/  references/
```

A concept's **identity is its path**: `concept_id` is the file path minus `.md`. Moving a concept is a rename plus a link rewrite, not a metadata change.

## A concept document

A concept is YAML frontmatter followed by a Markdown body. Example (`policies/returns/gold-members.md`):

```markdown
---
type: Policy
title: Gold Member Returns
description: Gold tier members get a 45-day return window instead of the standard 30 days.
tags: [returns, policy, loyalty]
timestamp: 2026-06-20T09:00:00Z
effective_from: 2026-06-20T00:00:00Z
---

# Gold Member Returns

A customer whose [membership tier](/entities/membership-tier.md) is **Gold** has
**45 days** from delivery to return an item, rather than the
[standard 30-day window](/policies/returns/standard.md).
```

### Frontmatter fields

| Field | Required | Meaning |
|---|---|---|
| `type` | **yes** (OKF spec) | The concept kind — e.g. `Policy`, `Playbook`, `Entity`, `Reference` |
| `description` | effectively (lint) | One-line summary; progressive disclosure depends on it. Missing → lint **warning**, not a failure |
| `title` | no | Human-readable title |
| `resource` | no | A canonical URL/path the concept describes |
| `tags` | no | List of keywords |
| `timestamp` | no | Last-change time (Kosha bumps this on merge) |
| `effective_from` | no | Kosha extension — temporal validity start |
| `effective_to` | no | Kosha extension — validity end; absent/`null` = currently in force |
| `access_level` | no | Kosha extension — label for bundle-level access |

**Unknown keys are preserved.** Producer extensions you add survive a Kosha round-trip untouched, so you can carry custom metadata without breaking conformance.

### Links

Use **standard, bundle-relative Markdown links**: `[text](/path/to/concept.md)`. The leading `/` is the bundle root. Links are untyped directed edges; the relationship lives in the prose. Kosha computes backlinks ("cited by") as the reverse edges.

> **Never use Obsidian `[[wikilinks]]`.** They silently break interop with spec-following consumers. Kosha's writer enforces standard links; hand-authored bundles must do the same.

A link to a not-yet-written concept is tolerated — it surfaces as a non-failing broken-link warning, tracked as "knowledge not captured yet," not an error.

## Reserved files

### `index.md` — the directory map

Each directory has an `index.md` listing its direct contents so a consumer can descend one level at a time. It is **not** a concept:

- It carries **no frontmatter** — except the **bundle-root** `index.md`, which may declare only `okf_version`.
- Its body is `#` section headings whose bullet entries are standard links with descriptions.

```markdown
---
okf_version: '0.1'
---

# Policies

* [Returns](/policies/returns/index.md) - When and how customers may send products back.
* [Refunds](/policies/refunds.md) - How refund amounts are calculated and issued.
```

Kosha regenerates these automatically on ingest; when writing by hand, keep them in sync with the directory (or run an ingest to regenerate).

### `log.md` — the change history

Optional. A reverse-chronological changelog with `## YYYY-MM-DD` ISO-date headings, newest first:

```markdown
# Update Log

## 2026-06-20
* **Policy change**: Added the [gold member 45-day return window](/policies/returns/gold-members.md).

## 2026-04-01
* **Creation**: Established core [entities](/entities/index.md).
```

Kosha appends to it on each ingest.

## Temporal validity

The same concept can carry history instead of forking into multiple files. `effective_from` / `effective_to` bound when a concept (or, internally, a claim) is in force:

- A consumer answering *"what is the policy now"* reads only what is currently in force (`effective_to` absent or in the future).
- A consumer answering *"what was it in Q1"* passes an `asof` date and reads the version in force then.

The MCP server's `load_concept` applies this filter automatically ([MCP integration](mcp-integration.md#temporal-validity)). When a policy changes, Kosha closes the old window (`effective_to`) and adds the new statement rather than overwriting — history is retained, not deleted.

## Conformance rules

`kosha validate <bundle>` applies three OKF v0.1 rules as **errors** (any error fails validation and blocks CI):

1. Every non-reserved `.md` file contains a parseable YAML frontmatter block.
2. Every frontmatter block has a non-empty `type`.
3. Reserved files follow their conventions: `index.md` carries no frontmatter (except the bundle-root `okf_version`); `log.md` uses ISO `YYYY-MM-DD` headings ordered newest-first.

Two checks are **warnings** that never fail validation:

- **Broken cross-link** — a link whose target file is absent (tolerated as not-yet-written knowledge).
- **Granularity** — the "one concept, one thing" lint; a concept that mixes topics is flagged for splitting.

```bash
uv run kosha validate bundles/northwind
# OK: bundles/northwind is OKF-conformant (0 warning(s))
```

## Round-trip stability

Kosha's parser and serializer round-trip a conformant concept **byte-for-byte** and preserve unknown keys, so editing a bundle through Kosha never churns formatting or drops metadata you added by hand. This is what lets the producer loop run dozens of times without the bundle degrading.

See also: [getting started](getting-started.md) · [system design — data model](system_design.md).
