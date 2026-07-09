---
title: Second Corpus Manifest
type: concept
---

**Domain:** Historical spaceflight operations and procedures (non-Python, non-API documentation).
**Source:** NASA Apollo Flight Journal (AFJ) mission transcripts and commentary.
**License:** Public Domain (NASA material not protected by copyright in the US).
**Privacy:** Contains names of public figures (astronauts, CAPCOMs); no private individual data, PII, or modern user content. No GDPR/CCPA exposure.

## Selection Rationale
To generalize the negative result from S1 (which used `pydoc-stdlib`), we require a domain that is:
1. Procedural and deeply interlinked (like API docs).
2. Semantically distinct from software engineering.
3. Completely free of synthetic generation artifacts or LLM training bleed that favors code-trained models.

## Exclusion Criteria
When extracting concepts for this corpus, we exclude:
- Boilerplate navigation and non-transcript HTML.
- Images, audio clips, and raw telemetry data.
- Biographies and external links not directly related to mission procedures.
- Any content added post-2023 to avoid recent LLM-generated contamination.
