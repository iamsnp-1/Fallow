# Fallow — Product Requirements Document

**Climate-aware crop advisory powered by agentic AI, IBM Granite, and RAG**

| Field | Value |
|---|---|
| Version | 1.0 (Hackathon Scope) |
| Project type | Decision-support system + early-warning system, conversational/voice interface |
| Primary SDGs | SDG 2 (Zero Hunger), SDG 13 (Climate Action) |
| Secondary SDGs | SDG 6 (Water), SDG 15 (Land), SDG 10 (Equity of access) |
| Core stack | IBM watsonx.ai, IBM Granite, RAG over agricultural extension corpus, multi-agent orchestration |

---

## 1. Problem Statement

Smallholder farmers decide what to plant and how much to irrigate based on tradition, last season's outcome, and word of mouth. These are backward-looking signals in a forward-looking problem.

Rainfall and soil-moisture patterns are deviating from historical norms with increasing frequency. When a farmer plants a water-intensive crop into a season that will deliver 35% below-normal rainfall, the outcomes are crop failure, debt, wasted irrigation water, and accelerated groundwater depletion.

The guidance that would prevent this **already exists**. State agricultural universities, ICAR, and Krishi Vigyan Kendras publish crop-water requirement tables, seasonal advisories, and extension bulletins. The failure is one of **distribution and translation**, not knowledge:

- The guidance sits in PDFs and government portals that farmers do not read.
- It is written in technical register, often not in the farmer's primary language.
- It is generic to a region, not conditioned on this season's forecast or this farmer's land.
- Extension officers who could bridge the gap are outnumbered by farmers at ratios that make individual advisory impossible.

**Fallow closes the gap between published agronomic knowledge and the decision a specific farmer makes this week.**

---

## 2. Users and Stakeholders

### Primary user — the smallholder farmer

- Owns or works 0.5–5 acres.
- Low-to-moderate literacy; may not read comfortably in English or even in written local language.
- Device access ranges from feature phone to shared smartphone.
- Decision moment is seasonal and time-boxed — the advisory is worthless if it arrives after sowing.

### Secondary user — the extension officer / FPO coordinator

- Serves hundreds of farmers; needs to triage who is about to make a high-risk decision.
- Wants district-level aggregate view, not one farmer at a time.

### Affected community

- Rural households whose food security and income depend on the harvest.
- Local food markets, which destabilize when many farmers in a district make the same bad bet simultaneously.

### Affected environment

- Groundwater tables, drawn down by irrigating crops mismatched to actual rainfall.
- Soil health, degraded by poor rotation choices repeated across seasons.

---

## 3. Why AI Is Required

This section exists because judges specifically probe it. Each capability is mapped to why a non-AI approach fails.

| Capability | Role in Fallow | Why rules/spreadsheets/pamphlets fail |
|---|---|---|
| **Prediction** | Forecast seasonal rainfall and soil-moisture trend for a district; detect deviation from historical baseline | Requires modeling multi-variable seasonal patterns across time-series and satellite data; a static almanac encodes only the historical norm, which is exactly what is breaking |
| **Retrieval + grounding (RAG)** | Pull the specific applicable passage from hundreds of pages of extension bulletins and crop-water tables | No farmer reads the corpus; manual cross-referencing by an extension officer does not scale to thousands of farmers per officer |
| **Synthesis and reasoning (Granite)** | Combine forecast + retrieved guidance + farmer's land profile into one ranked, justified recommendation | The join across three heterogeneous sources is judgment work, not lookup; a decision tree cannot handle the combinatorics of crop × region × forecast × land history |
| **Agentic orchestration** | Sequence forecast → retrieve → reason → localize → deliver, with retries and escalation | This is a multi-step workflow with dependencies between steps, not a single question-and-answer turn |
| **Localization** | Render the advisory in the farmer's language, as speech | Translation of technical agronomic register into plain spoken local language is generation work, not string substitution |
| **Scale** | Same pipeline serves one farmer or ten thousand | The binding constraint today is human agronomist headcount; this is precisely the constraint AI removes |

**Grounding is the non-negotiable design commitment.** An agricultural advisory that hallucinates a sowing window or a water requirement causes direct economic harm. Every recommendation Fallow emits must carry a citation to a retrieved source passage, and the system must be able to say "I don't have guidance for this" rather than improvise.

---

## 4. Solution Overview

Fallow is a multi-agent advisory system. A farmer (or an extension officer on their behalf) provides district, land size, and crop history. Fallow returns a ranked crop and irrigation recommendation, delivered as plain-language speech in the local language, with every claim traceable to a published source.

### The three moments of value

1. **The warning** — "This season's rainfall is projected 35% below your district's historical average."
2. **The recommendation** — "Consider millet over rice. Here is why, and here is the bulletin that says so."
3. **The delivery** — spoken, in the farmer's language, on the device they actually have.

---

## 5. System Architecture

### 5.1 Agent topology

**Orchestrator Agent**
Owns the plan. Decides execution order, handles agent failure and retry, enforces the rule that no recommendation is emitted without a grounding citation, and escalates to a human-review flag when confidence falls below threshold.

**Forecast Agent**
- Input: district identifier, target season.
- Pulls rainfall and soil-moisture data for the district.
- Computes deviation from historical baseline for that district and season.
- Output: structured forecast object — projected rainfall, deviation percentage, confidence band, anomaly flag.
- This agent alone constitutes the early-warning capability.

**Research Agent**
- Input: district, candidate crop set, forecast object.
- Performs RAG retrieval over the extension corpus, scoped by region and crop.
- Output: ranked retrieved passages with source metadata (document title, section, publishing body, year).
- Must return passage provenance, not just text, because citations are a product requirement.

**Advisory Agent (IBM Granite)**
- Input: forecast object + retrieved passages + farmer profile.
- Synthesizes a ranked recommendation: primary crop suggestion, alternatives, irrigation guidance, sowing window.
- Must attach a citation to each substantive claim.
- Must express uncertainty explicitly where the forecast confidence band is wide.
- Output: structured advisory object, not free prose — this keeps the downstream localization deterministic.

**Localization & Delivery Agent**
- Input: structured advisory object, target language.
- Renders advisory into plain spoken-register local language.
- Generates text-to-speech audio.
- Output: localized text + audio, plus a short SMS-length variant for feature-phone delivery.

### 5.2 Data layer

**Forecast sources**
- Open-Meteo or NASA POWER API for rainfall and soil-moisture — no account friction, works immediately, sufficient for demo and defensible in a pitch.
- IMD (India Meteorological Department) public data as the production-path source.

**RAG corpus**
- State agricultural university extension bulletins.
- ICAR crop-water requirement tables.
- Krishi Vigyan Kendra seasonal advisories.
- District-level agro-climatic zone classifications.

All are public documents. Chunk, embed, and index them with document-level metadata preserved so citations can name a real source.

**Farmer profile store**
- District, land size, irrigation access (rainfed / bore well / canal), crop history for prior 2–3 seasons.
- Synthetic for hackathon demo; real via extension-officer onboarding in production.

### 5.3 Stack

| Layer | Choice | Rationale |
|---|---|---|
| Reasoning model | IBM Granite on watsonx.ai | Core synthesis and generation for Research and Advisory agents |
| Orchestration | watsonx Agent Lab, or LangGraph/CrewAI calling Granite via watsonx.ai API | Agent Lab for IBM-native depth; LangGraph if build speed matters more than platform credit |
| Vector store | Chroma or Milvus (watsonx.data for IBM-native) | Chroma stands up fastest in a hackathon timeline |
| Embeddings | watsonx.ai embedding endpoint | Keeps the retrieval path on-platform |
| Governance | watsonx.governance (stretch) | Faithfulness scoring on RAG output — strong differentiator |
| Frontend | Lightweight web app | District selector, forecast chart, advisory card with citation chips, audio playback |
| TTS | Any available local-language TTS | Voice is the accessibility requirement, not a nice-to-have |

---

## 6. Functional Requirements

### Must have (hackathon deliverable)

| ID | Requirement |
|---|---|
| F1 | User selects a district and enters land size and irrigation access |
| F2 | Forecast Agent retrieves seasonal rainfall/soil-moisture and computes deviation from historical baseline |
| F3 | System visibly flags anomalous seasons (early-warning state) |
| F4 | Research Agent performs RAG retrieval scoped to district and candidate crops |
| F5 | Advisory Agent produces a ranked crop recommendation with irrigation guidance |
| F6 | Every substantive claim in the advisory carries a clickable citation resolving to the source passage |
| F7 | Advisory is rendered in at least one local language and playable as audio |
| F8 | Agent handoffs are visible in the UI — the user can see the pipeline execute |
| F9 | System returns an explicit "insufficient guidance" state rather than fabricating when retrieval fails |

### Should have

| ID | Requirement |
|---|---|
| F10 | Second district produces a materially different recommendation (proves the system is not hardcoded) |
| F11 | Extension-officer view: district-level list of farmers flagged as high-risk this season |
| F12 | SMS-length advisory variant for feature-phone delivery |

### Could have (stretch)

| ID | Requirement |
|---|---|
| F13 | watsonx.governance faithfulness/confidence score displayed alongside each advisory |
| F14 | Voice input, so the farmer can ask a follow-up question aloud |
| F15 | Season-over-season tracking: did the farmer follow the advisory, and what was the outcome |

### Explicitly out of scope for hackathon

- Real farmer onboarding and authentication
- Live IMD account integration
- Payment, subsidy, or insurance integration
- More than two demo languages
- Mobile-native app

---

## 7. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Groundedness** | No recommendation without a resolved citation. Hallucinated agronomic guidance is the primary product risk. |
| **Latency** | Full pipeline under ~20 seconds for demo credibility; async with progress states if longer |
| **Accessibility** | Voice-first output; SMS fallback; no assumption of literacy or smartphone |
| **Transparency** | Reasoning chain visible on request — the farmer and the extension officer must both be able to ask "why" |
| **Humility** | Wide forecast confidence bands must surface as hedged language, not false precision |
| **Localization** | Spoken register, not literal translation of technical text |

---

## 8. Success Metrics

### Demo-day metrics (what you show judges)

- Advisory produced end-to-end in under 20 seconds.
- 100% of substantive claims carry a resolving citation.
- Two districts with different forecasts produce materially different recommendations.
- Advisory delivered as audio in a local language.

### Impact metrics (what you claim, and defend)

| Dimension | Metric | How estimated |
|---|---|---|
| **Environmental** | Litres of irrigation water saved per season per acre | Delta between crop-water requirement of the traditional crop and the recommended crop, from ICAR tables |
| **Environmental** | Reduced groundwater draw in over-extracted blocks | Water saved × adoption rate in a target district |
| **Economic** | ₹ per season protected from crop failure | Expected yield loss under forecast conditions for traditional crop vs. recommended crop |
| **Social** | Farmers reached per agronomist-equivalent | Advisory throughput vs. extension-officer-to-farmer ratio baseline |
| **Social** | Share of advisories consumed via voice | Proxy for reach into low-literacy users otherwise excluded |

Do not claim precision you cannot defend. "Estimated water saving of X litres/acre/season based on ICAR crop-water tables, assuming Y adoption" is a far stronger claim than an unsourced tonnage figure.

---

## 9. Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Model hallucinates a sowing window or water requirement | **Critical** — causes direct economic harm | Hard requirement: no claim without retrieved citation; Orchestrator blocks uncited output; explicit "insufficient guidance" state |
| Forecast is wrong and farmer follows bad advice | High | Surface confidence bands; hedge language on low-confidence forecasts; frame as decision-support, never as a guarantee |
| Recommendation is agronomically sound but culturally or economically infeasible (no seed access, no market for the crop) | High | Constrain candidate crop set to locally available and locally marketable options; flag as known limitation in pitch |
| Translation flattens nuance or produces confusing register | Medium | Structured advisory object → templated localization, not free-form translation of prose |
| Over-reliance displaces extension officers rather than augmenting them | Medium | Position extension-officer view as core, not peripheral; system triages, humans decide |
| RAG corpus is regionally thin | Medium | Scope demo to districts where corpus coverage is genuinely good; be honest about coverage limits |

---

## 10. Demo Script

Target: 3–4 minutes, three distinct reveals.

1. **Setup (20s)** — Select a district, enter 2 acres, rainfed. One sentence of framing: this is the decision a farmer makes once a season, and gets one shot at.

2. **The warning (40s)** — Forecast Agent runs. Chart shows projected rainfall against the district's historical baseline, 35% below. Anomaly state fires. *This is the early-warning beat.*

3. **The pipeline (60s)** — Ask "what should I plant." Agent handoffs render visibly: Forecast → Research → Advisory. Not a spinner — the audience watches the system reason.

4. **The grounded recommendation (60s)** — Advisory card appears: millet over rice, with sowing window and irrigation guidance. Click a citation chip; the source bulletin passage opens and highlights. *This is the trust beat — the one that separates you from every ungrounded chatbot in the room.*

5. **The delivery (30s)** — Press play. The advisory speaks in the local language. *This is the access beat.*

6. **The proof it's real (20s)** — Switch to a district with normal rainfall. Different forecast, different recommendation. Nothing was hardcoded.

7. **Close (20s)** — One line on impact metric and one line on what production looks like.

---

## 11. Build Plan

### Phase 1 — Foundation
- Stand up watsonx.ai access and confirm Granite inference works end to end.
- Assemble and chunk the RAG corpus; index with source metadata preserved.
- Wire the forecast API and validate district-level data returns cleanly.

### Phase 2 — Agents
- Implement Forecast Agent and validate deviation computation against a known season.
- Implement Research Agent; verify retrieval returns relevant, correctly-attributed passages.
- Implement Advisory Agent with strict structured output and mandatory citation fields.
- Wire the Orchestrator, including the uncited-output block and the insufficient-guidance path.

### Phase 3 — Interface
- District selector, forecast chart, anomaly state.
- Advisory card with citation chips that resolve to source passages.
- Visible agent-handoff rendering.
- Localization and TTS playback.

### Phase 4 — Harden and rehearse
- Seed two contrasting districts and confirm divergent recommendations.
- Handle API failure states gracefully — a dead API mid-demo should degrade, not crash.
- Rehearse the demo script against the clock.
- Stretch items only if Phase 4 is genuinely complete.

### Team split suggestion

| Role | Owns |
|---|---|
| Data / ML | Forecast Agent, historical baseline, deviation logic |
| RAG / backend | Corpus, embeddings, Research Agent, citation provenance |
| Agents / integration | Granite prompts, Advisory Agent, Orchestrator, failure handling |
| Frontend / narrative | UI, agent-handoff visualization, localization/TTS, demo rehearsal |

---

## 12. Positioning Notes

Frame Fallow as a **decision-support and early-warning system with a conversational interface** — not as a chatbot. The distinction matters to judges: a chatbot answers questions, a decision-support system changes a decision, and an early-warning system changes it *in time*.

The two claims that differentiate Fallow in a room full of sustainability projects:

1. **Grounded by construction.** Every agronomic claim resolves to a published source, and the system refuses rather than improvises. Most hackathon RAG projects retrieve; fewer enforce.

2. **Built for the device and literacy the user actually has.** Voice-first with SMS fallback is an access decision, not a feature. It is also the reason the impact story is about equity and not just efficiency.
