## Consuming this OKF knowledge bundle

This repository is an OKF knowledge bundle. Answer knowledge questions **only** by
traversing it, loading the smallest set of concepts that answers the question.

When the Kosha MCP server is connected, use its tools: `find_concepts`,
`list_index`, `read_frontmatter`, `load_concept`, `follow_links`. Without MCP,
perform the same traversal by hand against the files:

- `find_concepts` → if an embedding index is available, jump to the few concepts nearest the question; otherwise start from the bundle-root `index.md`.
- `list_index` → read a directory's `index.md` to see its contents before opening any document. Descend one level at a time.
- `read_frontmatter` → read a concept's YAML frontmatter (type, description, effective dates) to judge relevance before loading its body.
- `load_concept` → read the concept body. Honor temporal validity: ignore any claim whose `effective_to` has passed (use the value in force now). Treat a concept you are not cleared to read as absent.
- `follow_links` → follow the standard markdown links in a concept body to reach related concepts; load only the neighbors you actually need.

Rules:
- **Do not grep, ripgrep, or full-text search** the bundle. Traverse from `index.md` (and the embedding jump) instead.
- **Do not load the whole corpus.** Stop as soon as the loaded concepts answer the question.
- Cite the `concept_id`s you used.
