---
title: "Kosha — System Overview"
subtitle: A governance toolkit for auditable OKF knowledge maintenance
codename: "Kosha (Sanskrit कोश — treasury/lexicon; a curated knowledge-vessel). Brand as bare 'Kosha', never 'Kosha AI', to avoid clash with the IndiaAI 'AIKosha' dataset platform."
tagline: "Curated knowledge, kept alive."
date: 2026-06-27
status: Draft for internal review
---

# Kosha — System Overview

## 0. Thesis (read this first)

**The product is not an OKF converter. The converter is already commodity.** Within two weeks of OKF's launch there are at least five free tools — including Google's own — that turn pages or databases into OKF bundles. Building another one is entering a red ocean on day one.

**The defensible product is the loop the spec deliberately omits:** ingest a source → extract concepts → *deduplicate against what already exists* → merge → discover cross-links → flag contradictions → keep the bundle conformant and reviewable — and then provide a traversal-first consumer surface instead of relying on ad hoc keyword search. OKF gives you a file contract. Kosha is the engine that keeps the knowledge *alive* and the retrieval *auditable*.

The current evidence changes the product boundary. The deterministic local-provider gates pass, but four real-model Gate-0 evidence tracks returned NO-GO: on decision quality, the loop does not currently beat a good prompt. The latest S2-v3 rerun exercised a second corpus with a pre-registered two-generation-vendor matrix (`openai/gpt-4.1-nano` and `qwen/qwen3-235b-a22b-2507`), but both cells still failed the reframed kill criterion. The sanctioned path is therefore a governance-skill product — zero silent overwrites, replayable lineage, traversal-first access — while M14+ product expansion stays halted unless a future pre-registered Gate-0 run records a GO.

---

## 1. What

Kosha is a plug-and-play engine that converts an organization's scattered knowledge into a **living OKF "brain"** and keeps it current, so that any agent — Claude, Gemini, a local model — can answer from curated, cross-linked, version-controlled knowledge instead of re-deriving answers from raw documents every query.

Three surfaces, one loop:

| Surface | What the user does | What Kosha does |
|---|---|---|
| **Ingest** | Points Kosha at sources (URLs, a repo, a DB schema, a docs site, exported tickets) or says `ingest <source>` | Extracts concepts, dedupes against the existing bundle, merges/creates, cross-links, flags contradictions, regenerates indexes, appends the log — as a reviewable Git commit |
| **Consume** | Connects an agent via one MCP endpoint (or drops in a skill) | Serves deterministic traversal tools so the agent reads `index.md` → frontmatter → minimal concept set; file-based fallbacks instruct the same path but do not sandbox generic filesystem tools |
| **Govern** | Reviews a plan, approves, browses the graph | Plan-and-approve gate, conformance/CI validation, daily Git backup, interactive graph visualizer |

The unit Kosha produces and maintains is a **conformant OKF bundle** (a directory of Markdown concepts + `index.md`/`log.md`), portable and tool-neutral by construction.

### What Kosha is explicitly NOT

- Not a RAG replacement at the storage layer — it produces *cleaner source context with relationships*; you can still run retrieval over it.
- Not a new platform you're locked into — the output is plain files in your Git repo; if you delete Kosha, the bundle still works in any editor or agent.
- Not a page-mirroring converter — page-mirroring is the cheap competitor's shortcut and produces bloated, duplicative bundles (see §5).
- Not an SEO/AI-visibility play — Google's search does not rank your site on a bundle. That framing (common in the early OKF tooling) is a different, weaker market.

---

## 2. Why

### 2.1 The failure mode OKF targets, and why it's worsening

As agentic systems take on more knowledge work, the binding constraint is no longer model capability — it is **context assembly**. Every agent build re-solves the same problem: where does the curated knowledge live, and how does the agent find the right slice without burning tokens or hallucinating?

The concrete pathology (documented by a team running a Git-versioned "second brain" controlled by `CLAUDE.md` files):

- The agent **doesn't know information already exists** — it only finds what it actively searches for. Unless told which file to read, it doesn't know the file is there.
- So it **creates duplicates** — a new folder for knowledge that already lived elsewhere under a different name.
- Its search is **keyword matching across the file tree**, so on a large, nested base it makes many wrong attempts before landing — wasting time and tokens.

This is invisible at small scale and compounds badly at large scale. It is exactly the decay Kosha's dedup/merge loop prevents.

### 2.2 Why a format alone doesn't fix it

OKF standardizes the *files*. It does nothing about the two things that actually determine whether knowledge stays useful:

1. **Keeping the corpus coherent as it grows** — the dedup/merge/contradiction work the spec leaves to "producer tooling."
2. **Making the consumer use it** — in field testing, an agent *ignored* a valid OKF bundle and defaulted to grep until navigation instructions were hand-added to `CLAUDE.md`. The format is consumer-agnostic; the traversal *behavior* is not automatic.

Kosha owns both. That is the "why."

### 2.3 Why now

- **The standard just shipped** (OKF v0.1, Google Cloud, 2026-06-12). First-mover window on the *maintenance + consumer* layer is open; the producer layer is already filling.
- **The substrate is safe even if the brand isn't.** Worst case, "OKF" the name fades — but Markdown + YAML frontmatter + Git is the lowest-common-denominator substrate the whole industry is converging on (AGENTS.md, llms.txt, Obsidian-as-agent-memory). Building on it is a low-regret bet.
- **MCP is now the default agent-tool protocol.** A consumer-side MCP server is the natural, adoptable shape for traversal-first bundle access.

---

## 3. How (mechanism, one level down)

Kosha is a **deterministic spine with isolated non-deterministic surfaces** — code does the bulk; the LLM is called only for contained judgments, each wrapped in an eval harness.

| Stage | Deterministic (code) | LLM surface (eval-gated) |
|---|---|---|
| Ingest | fetch, parse, normalize to text | — |
| Extract | chunking, file I/O | "what concepts are in this source" |
| **Dedup / resolve** | embedding nearest-neighbor over concept descriptions + bodies; ID resolution | "is candidate X the same concept as existing Y" |
| Merge | apply edits, bump `timestamp`, write files | "how should this update the body" |
| Link | resolve/validate paths | "which concepts relate, and how" |
| Contradiction | structured diff of old vs new claims | "do these materially conflict" |
| Index/Log | regenerate `index.md`, append `log.md` | — |
| Conform | 3-rule validator + granularity lint | — |
| Consume | parse frontmatter, walk graph, load minimal set | the agent's own task reasoning |

The retrieval win is **progressive disclosure**: the consumer pays tokens for a table of contents (`index.md`) plus one or two leaf concepts, not the corpus. On the Kosha reference scenario, a query loads ~2 index files + 1–2 concepts versus grep's many false-positive file opens.

A worked end-to-end trace (ingest a policy update → UPDATE-not-CREATE → cross-link → log; then a query that loads only the relevant concept) lives in the companion **System Design** document, §Workflows.

---

## 4. Market research

### 4.1 The OKF-native landscape (≤ 1 month old, moving weekly)

| Player | Shape | Audience | Maintenance loop? | Traversal boundary? |
|---|---|---|---|---|
| **Google reference** (BigQuery enrichment agent, `kcmd` CLI + MCP, HTML visualizer, Knowledge Catalog ingest) | Spec author + PoC tooling, BigQuery-coupled | Enterprise data teams | No (one-shot enrichment) | Partial (kcmd sync; not forced traversal) |
| **Suganthan OKF Generator + WordPress plugin** | Free; crawls ≤100 pages, **page → concept**, graph viz, serves at `/okf/` | SEO / site owners | No (re-generates on publish) | No |
| **okf.site** | Validator, generator, OpenAPI converter, examples | Developers | No | No |
| **openknowledgeformat.com** | Validator, templates, copyable prompts, examples | Developers / teams | No | No |
| **WitsCode** | Done-for-you bundle + "does AI search pick you up" measurement | SEO consultancy clients | No | No |
| **catancs/okf-skill** | Coding-agent skill: validate / query / lint / create | Coding-agent users | Partial (per-session) | Partial (skill, can be ignored) |

**Read:** every OKF-native tool today is a **producer-side converter or validator**. The market has rushed the easy half. *No one ships both the living maintenance loop (dedupe/merge/contradiction over time) and a mature served traversal boundary.* The page-mirroring tools (Suganthan) produce exactly the bloated, duplicative bundles the concept-extraction approach is meant to avoid — which is a quality opening, not just a feature gap.

### 4.2 The adjacent landscape (what Kosha competes with for the *job*, not the format)

| Category | Examples | Why OKF/Kosha is different |
|---|---|---|
| RAG platforms / vector DBs | LlamaIndex, LangChain retrievers, Pinecone, Weaviate | RAG re-derives at query time from raw chunks; OKF stores curated, cross-linked concepts agents read and update. Complementary, not exclusive. |
| Knowledge-graph / metadata catalogs | Collibra, Dataplex/Knowledge Catalog, Unity Catalog | Heavy, registry-based, vendor-bound. OKF is file-based, Git-native, portable; Kosha is the lightweight loop on top. |
| Personal/team knowledge tools | Notion, Obsidian, MkDocs | Human-first, API-gated or plugin-fragile, not interoperable across orgs. OKF is the interoperable substrate; Kosha adds the agent loop. |
| Context-engineering / agent-memory startups | (emerging) | Most are proprietary memory stores. Kosha's output is an *open* artifact — anti-lock-in is a sales asset. |

### 4.3 The incumbents we have to answer for (previously omitted)

The dangerous competitors are not the OKF-native tools — they're the platforms already selling "company knowledge → agent answers" at enterprise scale, with connectors, permissions, and sales motions a solo builder cannot match.

| Incumbent | What it already does | Why it's a threat | Why we can still differentiate |
|---|---|---|---|
| **Glean** | Enterprise search + assistant over connected company knowledge | Owns the exact job ("agents answer from our knowledge"), enterprise-entrenched | Closed, proprietary index; no portable artifact; not Git-native or cross-org |
| **Microsoft Copilot + Graph** | Knowledge/answers across M365 | Default for M365 shops; massive distribution | Locked to the Microsoft graph; no open bundle you can take elsewhere |
| **Notion AI / Atlassian Rovo / Dropbox Dash** | Q&A over their own knowledge stores | Already where the docs live | Each is a silo; none produces an interoperable, agent-agnostic artifact |

**The question this forces:** is OKF-based maintenance a *wedge against* these, or a *feature they absorb in a quarter*? The honest answer: our only durable difference is the **open, portable, agent-agnostic artifact** — the one thing none of them will ever ship, because lock-in is their model. That is either the wedge or the niche ceiling; it is not a small distinction, and it should be stated to anyone evaluating this.

### 4.4 Feature, company, or skill? (the replicability threat)

`catancs/okf-skill` already does validate/query/lint/create as an open-source skill. A competent engineer can get a meaningful fraction of the value from a good `AGENTS.md` plus an existing coding agent told to maintain concept files. Real-model Gate-0 has now tested the decision-quality bar and returned NO-GO: the maintenance loop does not currently beat a good prompt. Kosha's current product boundary is therefore an open-source governance skill with a verifiable audit trail, not an authorized decision-quality product. Reopen that boundary only with a future pre-registered GO.

### 4.5 ICP decision (a premise worth challenging)

The brief says "anyone can use by sheer plug-and-play." That phrasing hides a fork that determines the entire product:

| Wedge | "Anyone" = | Crowding | Fit to your strengths | Willingness to pay for *quality* |
|---|---|---|---|---|
| **Consumer / SEO / marketer** | non-technical site owners | High (Suganthan, WitsCode already here, free) | Low | Low — they can't tell good dedup from bad |
| **Developer / platform team** | engineers wiring agents to internal knowledge | Low (only catancs skill, Google kcmd) | High (your deterministic-spine, eval-rigor background) | High — they feel token cost, latency, and agent errors directly |

**Recommendation: lead with the developer / platform-team wedge; treat consumer as later expansion.** "Plug-and-play" (low friction) is compatible with either, but the buyer who can *perceive and pay for* the maintenance-loop quality is the engineer, not the marketer. Going consumer-first puts you in a free, commoditized fight on the half of the problem that's already solved.

---

## 5. Risks

| # | Risk | Severity | Mitigation / position |
|---|---|---|---|
| R1 | **Standard immaturity.** v0.1, single-vendor; field caveat from practitioners is "an optimization, not something you need yet" until agents support OKF out of the box. | High | Kosha's governance value (anti-duplication, audit trail, replayable changes) is real *today* regardless of OKF adoption. Substrate (MD+YAML+Git) survives even if the brand does not. |
| R2 | **Producer layer commoditized.** Free converters already exist, including Google's. | High | Don't compete there. Differentiate on maintenance loop + governance guarantee + traversal-first consumption. Treat conversion as a loss-leader feature, not the product. |
| R3 | **Google platform risk.** Knowledge Catalog / `kcmd` could grow the maintenance loop and a consumer adapter. | Med-High | Stay model- and cloud-neutral (Google's is BigQuery/GCP-coupled). Win on portability, local-first, and agent-agnostic auditability. Speed + neutrality are the hedge. |
| R4 | **Spec churn.** A major version bump can rename required fields / reserved filenames. | Med | Pin `okf_version`; keep the writer behind an adapter; conformance suite gates regressions. Cheap to track a one-page spec. |
| R5 | **"Plug-and-play" vs quality tension.** Zero-touch favors page-mirroring; high-quality concept extraction needs judgment. | Med-High | Make the *common path* zero-touch but back it with the dedup/granularity loop; expose a review gate for the judgment calls rather than hiding them. |
| R6 | **Auto-edit corrupts the knowledge base.** An agent that rewrites the brain can damage it. | Med | Human approve-before-write gate, Git branch-not-main, daily backup, contradiction flagging instead of silent overwrite. Treat these as required defaults. |
| R7 | **Differentiation is illegible to non-technical buyers.** "Better dedup" doesn't demo. | Med | Reinforces the developer-wedge recommendation; for developers, show the audit trail, token/latency profile, and duplicate-rate checks on their own corpus. |
| R8 | **Cross-org exchange needs trust/provenance** the spec lacks (the "buy expert bundles" vision). | Low (near-term) | Out of scope for v1. Note as a v2 platform bet, not a wedge. |
| R9 | **Long-context erosion (premise risk).** The token-saving thesis assumes structured retrieval beats dumping docs into context. As windows hit 1–10M tokens and per-token cost falls, "just put the raw docs in context" gets stronger every quarter. | **High** | Don't anchor on token savings alone. Re-anchor the value on *coherence + dedup + governance* (things long context does **not** give you). Benchmark traversal vs long-context vs RAG on a real corpus at current prices — this is gating (see Premise-Validation spike in the Design doc). |
| R10 | **Incumbent absorption.** Glean / Copilot / Notion / Rovo / Dash already own "knowledge → agent answers" and could add OKF I/O. | High | Compete only where they won't follow: open, portable, agent-agnostic artifact + local-first. If that's not enough differentiation, this is a niche, not a market. |
| R11 | **Replicable by a skill.** Much of the value may be reachable via `AGENTS.md` + an existing agent (cf. `catancs/okf-skill`). | High | Current real-model Gate-0 evidence says the loop does not beat a prompt on measured decision quality. Treat Kosha as a governance skill until a future pre-registered run records a GO. |
| R12 | **Source-of-truth conflict / staleness.** One-way ingest from living sources (Confluence, Slack, Drive) makes the bundle a drifting copy the moment it's written. | **High** | Decide explicitly: cache (accept staleness + re-ingest cadence) vs source-of-truth (migration friction). Undecided = "yet another silo." Gating decision (see Design doc §6). |
| R13 | **Maintenance-loop unit economics.** Every ingest = many LLM calls (extract+dedup+merge+link+contradiction), ongoing — unlike RAG's cheap one-time embed. | Med-High | Model cost-per-ingest before promising "ingest everything"; it shapes pricing and may kill a consumer tier. Use cheap models + deterministic short-circuits in the dedup band. |
| R14 | **Marketplace IP & liability.** Bundles LLM-extracted from copyrighted sources raise ownership questions; sold "expert bundles" raise professional-liability questions. | Low (near-term) / High (if pursued) | Kills the v3 marketplace earlier than the missing trust layer. Keep marketplace out of scope until there's a provenance + licensing + disclaimer model. |

> **Architecture-level fault lines** (access control vs OKF's openness, edit-drift from repeated LLM merges, contradiction *resolution* + temporal validity, traversal latency) are design risks, not strategy risks — they live in the System Design doc, §2.x and §7. They don't threaten *whether* to build, but they will determine *whether it works*.

---

## 6. Possible moat

Ranked by defensibility. The format itself is **not** on this list — it's commodity.

1. **Maintenance-loop quality (conditional data/eval moat).** Getting "this source updates *that* concept, don't spawn a duplicate" right — at high precision/recall, measured against golden corpora — is genuinely hard and compounds. Today this is an unearned moat claim: four real-model Gate-0 evidence tracks returned NO-GO, the latest S2-v3 second-corpus rerun satisfied the pre-registered two-generation-vendor shape but still failed the reframed kill criterion, and the labeled corpus is still too small. No labeled corpus → no measurable quality → no moat. Plan the data acquisition before reopening the product-quality claim.
2. **Traversal-surface standardization (distribution advantage, not enforcement by itself).** Whoever ships the MCP traversal server that agents *standardize on* owns the consumption side. If "to use OKF knowledge you point your agent at Kosha's endpoint" becomes the default, that's sticky integration surface. The catch: a host session with generic filesystem tools can still search files unless a future sandboxed boundary removes that access. Treat this as a fast-mover advantage and a quality play, not a structural moat.
3. **Closed-loop workflow lock-in (the workflow moat).** Producer + consumer + governance in one Git-native, CI-gated loop creates switching cost at the *process* level even though the artifact is open. The openness of the artifact is the trust that gets you in; the loop is what keeps you.
4. **Weak / non-moats:** the OKF format, validators, page converters, the visualizer. Useful as free top-of-funnel, never as the defensible core.

A blunt self-check: if a competitor cloned the *format* support in a weekend, what's left? Answer must be "the dedup/merge quality and the consumer adapter agents depend on." If those aren't excellent, there is no moat.

---

## 7. Examples

### 7.1 Northwind support brain (the canonical demo)

A retailer's support knowledge as a small bundle (`policies/`, `playbooks/`, `entities/`, `references/`). A source arrives: *"Gold members now get a 45-day return window instead of 30."* Kosha:

1. Locates `policies/returns.md` via progressive disclosure (root index → policies index → frontmatter).
2. Decides **UPDATE, not CREATE** — the "return window" concept already exists (no duplicate folder).
3. Edits the body, adds the member exception, bumps `timestamp`.
4. Discovers a new concept (`entities/membership-tier.md`), mints it; the link was valid even before the file existed.
5. Checks for contradiction (exception, not conflict → no flag).
6. Appends to `log.md`; presents the plan; writes on approval as a Git commit.

Then a support agent asks *"How long does a Gold member have to return boots?"* → loads `index.md`, `policies/index.md`, `returns.md`, maybe `membership-tier.md`. Never loads playbooks/references. (Full trace with diagrams in the System Design doc.)

### 7.2 Other company scenarios

| Scenario | Sources Kosha ingests | Who consumes | Payoff |
|---|---|---|---|
| **Data-team metadata-as-code** | BigQuery/warehouse schemas, dbt models, metric defs | Analytics agent | Catalog lives in Git, diffable via PR; agent stops guessing join paths |
| **Incident runbooks for on-call agents** | Runbook docs, past incident write-ups | On-call agent | Faster triage; agent follows cross-links to the exact join path |
| **Engineering wiki replacement** | Repo docs, ADRs, Confluence export | Coding agents + humans | One source of truth, browsable graph + agent-consumable, no stale Notion |
| **Vendor API knowledge** | A vendor's published OKF bundle | Your integration agent | Consume directly, no integration ticket (portability payoff) |
| **Expert procedure capture** | An expert's process, captured once as a `Playbook` | Any team member's agent | A 2-day expert analysis becomes a reusable, parameterized procedure |

---

## 8. Open questions to resolve before committing

Three of these are **gating** — they can each independently invalidate the headline benefit and none requires building anything to investigate. Settle them with a spike before writing more design (see the Premise-Validation spike in the System Design doc).

- **[GATING] Premise break-even:** at what corpus size and price does index-traversal actually beat long-context-with-raw-docs and beat RAG — on *both* tokens and wall-clock latency? Is that window widening or closing? If closing, the wedge is coherence/governance, not token savings.
- **[GATING] Source-of-truth stance:** is the bundle a cache of living sources (accept staleness, define re-ingest cadence) or the canonical store (accept migration friction)? Undecided means "yet another silo."
- **[GATING] Eval-data acquisition:** where does the labeled dedup/granularity corpus come from? The moat depends on data you don't have.
- **ICP lock:** developer-first (recommended) vs consumer-first. Gates everything downstream.
- **Feature/company/skill:** what specifically makes this not replicable by `AGENTS.md` + an existing agent? Define the must-beat-a-prompt bar.
- **Consumer adapter form:** MCP server (strongest traversal interface) vs skill vs `AGENTS.md` fragment — or ship all three and let the environment pick. Host-level enforcement requires a sandboxed serving boundary, not just instructions.
- **Quality bar:** what dedup precision/recall and duplicate-rate / token-delta on a reference corpus constitutes "good enough to charge for"?
- **Hosting model:** local-first CLI + MCP (matches your stack and the anti-lock-in story) vs hosted SaaS (easier onboarding, and possibly *required* for concept-level access control — see Design doc §6).
- **Pricing legibility:** how to make "better maintenance" demoable on a prospect's own knowledge in under five minutes.
