# Plan: Crypto Scalp Auto Trading System

**Datum:** 2026-06-20
**Doel:** Automatiseer de strategie van 's werelds beste crypto scalper via een 3-layer systeem op Bybit.

---

## Stage 1 — Deep Research (Parallel)

### 1A: Beste Crypto Scalper Identificatie & Strategie Analyse
- **Skill:** `deep-research-swarm`
- **Mission:** Identificeer wie de allerbeste crypto scalper is (live/verified track record, PnL, social proof). Onderzoek zijn/haar volledige strategie: entry criteria, exit criteria, timeframes, risk management, positiegrootte, gebruikte indicatoren, market structure reading, orderflow analyse, etc. Zoek interviews, YouTube breakdowns, social media posts, Substack artikelen, enz.

### 1B: GitHub Repo Onderzoek — 3-Layer Basis
- **Skill:** `deep-research-swarm` (GitHub focus)
- **Mission:** Onderzoek de beste open-source repositories voor:
  1. **Layer 1 (Data):** OpenBB Terminal / OpenBB Platform — check of dit geschikt is voor crypto real-time data via Bybit API. Zoek alternativen indien nodig.
  2. **Layer 2 (Agentic):** Paperclip-style multi-agent framework — zoek of dit open-source is, of bouw een equivalent met LangChain / AutoGen / CrewAI.
  3. **Layer 3 (Trading):** Tauric Research TradingAgents — zoek of dit open-source is, of vergelijkbare execution engines (freqtrade, hummingbot, vnpy, etc.).

---

## Stage 2 — Architectuur & Design
- **Skill:** Orchestrator-designed (geen specifieke skill nodig)
- **Mission:** Op basis van Stage 1 resultaten, ontwerp de volledige 3-layer architectuur:
  - Layer 1: Data ingestion + market data normalisatie
  - Layer 2: Multi-agent signal generation + consensus
  - Layer 3: Execution engine + risk management + Bybit API integratie

---

## Stage 3 — Implementatie (Swarm Coding)
- **Skill:** `swarm-coding`
- **Mission:** Bouw het volledige systeem in Python met de volgende componenten:
  - Bybit API wrapper (v5 API)
  - Data layer (real-time + historisch)
  - Agentic layer (multi-agent decision engine)
  - Trading layer (execution + risk management)
  - Configuratie + monitoring

---

## Stage 4 — Integratie, Documentatie & Delivery
- **Skill:** `docx` (voor documentatie)
- **Mission:** Integreer alle layers, schrijf setup instructies, documenteer de strategie, en lever het volledige systeem op.

---

## Output Bestanden
- `plan.md` (dit bestand)
- `research/scalper_profile.md` — profiel van de beste scalper
- `research/github_repos.md` — gevonden repos & analyse
- `architecture/system_design.md` — volledige architectuur
- `src/` — volledige codebase
- `docs/setup.md` — installatie & configuratie handleiding
