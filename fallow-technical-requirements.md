# Fallow — Technical Requirements Specification

**Companion to the Fallow PRD. This document covers what gets built, in what shape, with what contracts.**

| Field | Value |
|---|---|
| Version | 1.0 (Hackathon Scope) |
| Scope | Reference architecture, component specs, data contracts, interfaces, environment, testing |
| Assumed timeline | 24–48 hour hackathon build |

---

## 1. System Overview

Fallow is a request-scoped, stateless multi-agent pipeline. One advisory request enters, five agents execute in a mostly-linear sequence, one structured advisory exits. There is no long-running state, no background jobs, and no user-session persistence in hackathon scope. This is deliberate — it removes an entire class of failure from the demo path.

```
Client (web)
   │
   ▼
API Gateway  ──►  Orchestrator Agent
                      │
        ┌─────────────┼─────────────┬──────────────┐
        ▼             ▼             ▼              ▼
   Forecast       Research      Advisory      Localization
    Agent          Agent         Agent          Agent
        │             │             │              │
        ▼             ▼             ▼              ▼
  Weather API   Vector Store   Granite/watsonx   TTS engine
                (+ corpus)
```

---

## 2. Technology Stack

### 2.1 Required components

| Layer | Technology | Version / Notes |
|---|---|---|
| Runtime | Python 3.11+ | Backend and all agents |
| API framework | FastAPI | Async-native, auto OpenAPI docs, fast to stand up |
| LLM | IBM Granite via watsonx.ai | Instruct-tuned variant; confirm the current model ID in your watsonx console rather than hardcoding from memory |
| Agent orchestration | LangGraph *or* watsonx Agent Lab | See §2.2 for the tradeoff |
| Vector store | ChromaDB (local, persistent mode) | Milvus or watsonx.data if IBM-native depth is being scored |
| Embeddings | watsonx.ai embeddings endpoint | Falls back to a local sentence-transformer if the endpoint is rate-limited |
| Document parsing | PyMuPDF (`fitz`) | Extension bulletins are PDFs, often with tables |
| Weather data | Open-Meteo API | No API key, no signup, historical + forecast endpoints |
| TTS | Platform TTS or an open multilingual model | Must support at least one Indic language |
| Frontend | React + Vite, or plain HTML/JS | Whatever your team ships fastest |
| Charting | Recharts or Chart.js | One chart needed: forecast vs. historical baseline |

### 2.2 Orchestration decision

| Option | Pick it if | Cost |
|---|---|---|
| **watsonx Agent Lab** | IBM tooling depth is explicitly scored, and someone on the team has used it before | Learning curve mid-hackathon is a real schedule risk |
| **LangGraph calling Granite via watsonx.ai SDK** | Build speed matters more; you still get full IBM credit since Granite does all reasoning | Slightly weaker "we used the whole IBM stack" claim |

**Recommendation:** LangGraph unless someone already knows Agent Lab. The judging story is identical — Granite is the reasoning engine either way — and you cannot afford to lose six hours to platform onboarding.

### 2.3 Key dependencies

```
fastapi
uvicorn
ibm-watsonx-ai
langgraph
langchain-core
chromadb
pymupdf
httpx
pydantic
pandas
numpy
python-dotenv
```

---

## 3. Data Contracts

All inter-agent communication uses Pydantic models. **No agent passes free-form strings to another agent.** This is the single most important engineering constraint in the system — it is what makes the pipeline debuggable under demo pressure and what keeps citations attached to claims.

### 3.1 `FarmerProfile` (input)

```python
class FarmerProfile(BaseModel):
    district_id: str            # e.g. "IN-MH-AUR"
    district_name: str
    land_size_acres: float
    irrigation_access: Literal["rainfed", "borewell", "canal", "mixed"]
    crop_history: list[str]     # last 2-3 seasons, most recent first
    season: Literal["kharif", "rabi", "zaid"]
    language: str               # BCP-47, e.g. "mr", "hi", "en"
```

### 3.2 `ForecastResult` (Forecast Agent output)

```python
class ForecastResult(BaseModel):
    district_id: str
    season: str
    projected_rainfall_mm: float
    historical_mean_mm: float
    deviation_pct: float           # negative = deficit
    soil_moisture_index: float | None
    confidence: Literal["high", "medium", "low"]
    anomaly_flag: bool             # True if |deviation_pct| > threshold
    baseline_years: int            # how many years the mean is computed over
    source: str                    # "open-meteo" | "imd"
```

### 3.3 `RetrievedPassage` (Research Agent output element)

```python
class RetrievedPassage(BaseModel):
    passage_id: str
    text: str
    relevance_score: float
    doc_title: str
    publishing_body: str        # e.g. "ICAR", "MPKV Rahuri KVK"
    year: int | None
    section: str | None
    page: int | None
    source_uri: str             # resolves to the actual document
```

Provenance fields are **not optional**. A passage without resolvable provenance is discarded, because the product requirement is that every claim carries a working citation.

### 3.4 `Recommendation` and `Advisory` (Advisory Agent output)

```python
class Claim(BaseModel):
    statement: str
    citation_ids: list[str]     # must be non-empty; refs RetrievedPassage.passage_id

class CropOption(BaseModel):
    crop: str
    rank: int
    rationale: list[Claim]
    water_requirement_mm: float | None
    sowing_window: str | None
    expected_viability: Literal["good", "moderate", "poor"]

class Advisory(BaseModel):
    farmer: FarmerProfile
    forecast: ForecastResult
    recommended: list[CropOption]      # ranked
    irrigation_guidance: list[Claim]
    warnings: list[str]
    hedged: bool                        # True when forecast confidence is low
    sufficient_guidance: bool           # False triggers the refusal path
    citations: dict[str, RetrievedPassage]
```

### 3.5 `LocalizedAdvisory` (Localization Agent output)

```python
class LocalizedAdvisory(BaseModel):
    language: str
    full_text: str
    sms_text: str               # <= 320 chars, 2 SMS segments
    audio_url: str
    citation_labels: dict[str, str]   # human-readable source names in-language
```

---

## 4. Component Specifications

### 4.1 Orchestrator Agent

**Responsibility:** plan execution, enforce invariants, handle failure.

Requirements:

| ID | Requirement |
|---|---|
| ORC-1 | Executes Forecast → Research → Advisory → Localization in sequence; Research may run partially in parallel across candidate crops |
| ORC-2 | **Blocks any `Advisory` where a `Claim` has an empty `citation_ids` list.** Hard failure, not a warning |
| ORC-3 | Validates every `citation_id` resolves to a passage in `Advisory.citations`; unresolvable IDs fail the response |
| ORC-4 | If Research returns fewer than N relevant passages above a relevance threshold, sets `sufficient_guidance=False` and returns the refusal path instead of calling Advisory |
| ORC-5 | Retries a failed agent once with backoff; on second failure returns a degraded response naming which stage failed |
| ORC-6 | Emits a structured trace of each agent handoff for the UI to render |
| ORC-7 | Enforces total pipeline timeout; partial results are surfaced rather than dropped |

ORC-2 through ORC-4 are the anti-hallucination spine of the system. Implement these before anything cosmetic.

### 4.2 Forecast Agent

| ID | Requirement |
|---|---|
| FC-1 | Resolve `district_id` to lat/long centroid |
| FC-2 | Fetch seasonal forecast rainfall for the target season window |
| FC-3 | Fetch historical rainfall for the same window across N years (minimum 10) to compute baseline mean |
| FC-4 | Compute `deviation_pct`; set `anomaly_flag` when magnitude exceeds configured threshold (default 20%) |
| FC-5 | Derive `confidence` from forecast horizon and spread; a long-horizon seasonal projection is never `high` |
| FC-6 | Cache responses by `(district_id, season)` — the demo will hit the same districts repeatedly and you do not want live API latency on stage |

**Note on honesty:** long-range seasonal rainfall forecasting is genuinely hard. Do not claim more skill than the underlying API provides. Surface the confidence band and let the Advisory Agent hedge. Judges respect calibration; they punish false precision.

### 4.3 Research Agent (RAG)

| ID | Requirement |
|---|---|
| RS-1 | Ingestion: parse corpus PDFs, chunk with overlap, preserve document metadata per chunk |
| RS-2 | Chunking strategy: semantic or section-aware, ~500–800 tokens with ~100 token overlap; tables extracted separately and kept intact |
| RS-3 | Embed chunks; persist to vector store with full metadata |
| RS-4 | Query construction from `FarmerProfile` + `ForecastResult` — must include district/agro-climatic zone and candidate crops |
| RS-5 | Retrieve top-k (k≈8) with metadata filtering on region where available |
| RS-6 | Apply a relevance-score floor; discard passages below it rather than padding to k |
| RS-7 | Return `RetrievedPassage[]` with complete provenance; drop any chunk lacking a resolvable `source_uri` |

**Corpus scoping:** pick two or three districts and build deep corpus coverage for those, rather than thin national coverage. A demo that works excellently for two districts beats one that works badly everywhere, and the coverage limitation is easy to acknowledge honestly in the pitch.

### 4.4 Advisory Agent (Granite)

| ID | Requirement |
|---|---|
| AD-1 | Prompt includes forecast object, retrieved passages with IDs, and farmer profile |
| AD-2 | **Constrained output** — must return JSON matching the `Advisory` schema; validate and retry once on schema violation |
| AD-3 | System prompt instructs: cite passage IDs for every substantive claim; do not use outside knowledge for agronomic facts |
| AD-4 | Must set `sufficient_guidance=False` rather than improvising when passages do not cover the question |
| AD-5 | Must set `hedged=True` and soften language when `ForecastResult.confidence` is `low` |
| AD-6 | Candidate crop set constrained to locally available and locally marketable crops — passed in as context, not left to the model |
| AD-7 | Temperature low (≈0.2); this is a reasoning task, not a creative one |

AD-6 addresses a real failure mode: an agronomically ideal crop with no local seed supply or no local buyer is useless advice.

### 4.5 Localization & Delivery Agent

| ID | Requirement |
|---|---|
| LC-1 | Input is the **structured** `Advisory` object, never generated prose |
| LC-2 | Render via language templates populated from the structure, with Granite used for natural phrasing within slots |
| LC-3 | Output spoken register, not literal translation of technical text |
| LC-4 | Generate `sms_text` ≤ 320 characters carrying the single most decision-relevant fact |
| LC-5 | Generate TTS audio; return a playable URL |
| LC-6 | Preserve citation references as human-readable source names in-language |

LC-1 is a correctness requirement. Translating free-form model prose compounds any error in the original; templating from structure does not.

---

## 5. API Specification

### `POST /api/advisory`

Request body: `FarmerProfile`

Response: 
```json
{
  "advisory": { /* Advisory */ },
  "localized": { /* LocalizedAdvisory */ },
  "trace": [
    {"agent": "forecast", "status": "ok", "ms": 820},
    {"agent": "research", "status": "ok", "ms": 1140, "passages": 8},
    {"agent": "advisory", "status": "ok", "ms": 4300},
    {"agent": "localization", "status": "ok", "ms": 2100}
  ]
}
```

### `GET /api/forecast/{district_id}?season=kharif`

Returns `ForecastResult`. Used by the UI to render the warning beat before the user asks for a recommendation.

### `GET /api/citation/{passage_id}`

Returns the full `RetrievedPassage` including `source_uri`. Backs the citation-chip click interaction.

### `GET /api/districts`

Returns the seeded district list for the selector.

### Streaming

`/api/advisory` should support Server-Sent Events emitting each trace entry as it completes, so the UI can render agent handoffs live rather than after the fact. This is a demo-critical detail — the visible pipeline is one of your three reveals.

---

## 6. Frontend Requirements

| ID | Requirement |
|---|---|
| UI-1 | District selector, land size input, irrigation access selector, language selector |
| UI-2 | Forecast chart: projected rainfall vs. historical baseline, with the deviation called out numerically |
| UI-3 | Visually distinct anomaly state when `anomaly_flag` is true |
| UI-4 | Live agent-handoff rendering driven by the SSE trace stream — not a generic spinner |
| UI-5 | Advisory card: ranked crops, rationale, sowing window, irrigation guidance |
| UI-6 | Citation chips inline on claims; click opens the source passage with the relevant text highlighted |
| UI-7 | Audio playback control for the localized advisory |
| UI-8 | Explicit, non-alarming rendering of the `sufficient_guidance=False` refusal state |
| UI-9 | Hedged advisories visually marked as lower-confidence |
| UI-10 | Responsive; assume it may be demoed from a laptop or a phone |

---

## 7. Configuration

```
WATSONX_API_KEY=
WATSONX_PROJECT_ID=
WATSONX_URL=
GRANITE_MODEL_ID=
EMBEDDING_MODEL_ID=

CHROMA_PERSIST_DIR=./data/chroma
CORPUS_DIR=./data/corpus

WEATHER_API_BASE=https://api.open-meteo.com
FORECAST_CACHE_TTL=3600

ANOMALY_THRESHOLD_PCT=20
BASELINE_YEARS=15
RETRIEVAL_TOP_K=8
RELEVANCE_FLOOR=0.35
MIN_PASSAGES_FOR_ADVISORY=3
PIPELINE_TIMEOUT_S=30
```

Every threshold is configurable and none are hardcoded. You will tune `RELEVANCE_FLOOR` and `MIN_PASSAGES_FOR_ADVISORY` during rehearsal, and you do not want to be editing source code at 3am to do it.

---

## 8. Non-Functional Requirements

| Category | Requirement | Target |
|---|---|---|
| Latency | Full pipeline, cached forecast | < 20s |
| Latency | Forecast-only endpoint | < 2s |
| Reliability | Any single external API failure degrades gracefully, never crashes the demo | Mandatory |
| Groundedness | Claims with resolving citations | 100% |
| Determinism | Same input produces substantively the same recommendation | Low temperature + cached forecast |
| Offline resilience | Pre-seeded cache for demo districts so the demo survives venue wifi | Mandatory |
| Observability | Structured logs per agent with timing and token counts | Required for trace UI |
| Security | API keys in env only, never committed, never sent to client | Mandatory |

**The offline-resilience requirement is not paranoia.** Hackathon venue networks fail during demos with remarkable consistency. Pre-cache forecast responses and pre-compute one full advisory per demo district as a fallback path.

---

## 9. Testing Requirements

| ID | Test |
|---|---|
| T1 | Deviation computation verified against a known historical season with a known outcome |
| T2 | Retrieval returns topically correct passages for a hand-checked set of queries |
| T3 | Every `citation_id` in an `Advisory` resolves — assert programmatically, not by eye |
| T4 | Advisory Agent returns schema-valid JSON across repeated runs |
| T5 | Refusal path fires when the corpus is deliberately stripped of relevant docs |
| T6 | Two contrasting districts produce materially different recommendations |
| T7 | Each external API failure injected individually; pipeline degrades without crashing |
| T8 | Pipeline timeout produces a partial result, not a hang |
| T9 | Full demo script executed end-to-end against the clock, at least twice |

T3 and T5 are the tests that protect your core claim. Run them before you polish anything.

---

## 10. Build Sequence

Ordered by dependency and by demo risk, highest-risk-first.

**Phase 1 — De-risk the unknowns**
1. Confirm Granite inference works end-to-end from your code. Do this first; everything depends on it.
2. Confirm the weather API returns usable seasonal + historical data for your chosen districts.
3. Confirm TTS produces intelligible output in your target language.

Anything that fails here changes the plan, so find out in hour one, not hour twenty.

**Phase 2 — Backbone**
4. Define all Pydantic contracts. Freeze them; downstream work parallelizes off these.
5. Corpus ingestion and indexing with metadata preserved.
6. Forecast Agent + cache.
7. Research Agent with provenance.

**Phase 3 — Reasoning**
8. Advisory Agent with constrained JSON output.
9. Orchestrator with ORC-2 through ORC-4 invariants.
10. Localization Agent + TTS.

**Phase 4 — Surface**
11. API endpoints + SSE trace stream.
12. Frontend: inputs, forecast chart, advisory card, citation chips, audio.
13. Agent-handoff visualization.

**Phase 5 — Harden**
14. Seed demo districts, pre-cache everything.
15. Failure injection tests.
16. Rehearse the demo twice against the clock.

Stretch items (watsonx.governance scoring, extension-officer view, voice input) only after Phase 5 is genuinely complete. A polished stretch feature on top of a fragile core loses to a solid core every time.

---

## 11. Parallelization Plan

With the contracts in §3 frozen early, four workstreams run independently:

| Workstream | Owns | Blocked by |
|---|---|---|
| Forecast | FC-1 to FC-6, caching, historical baseline | Contracts only |
| RAG | Corpus, ingestion, RS-1 to RS-7 | Contracts only |
| Agents | Granite prompts, AD-*, Orchestrator, LC-* | Contracts; integrates with Forecast + RAG late |
| Frontend | UI-1 to UI-10, SSE consumption, demo rehearsal | Contracts; mocks API until backend lands |

The frontend should build entirely against mocked API responses shaped by the §3 contracts. It must not wait for the backend — that dependency is the most common way hackathon teams lose their final hours.
