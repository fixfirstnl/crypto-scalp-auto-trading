# Crypto Scalp Auto Trading — Stap-voor-Stap Roadmap

**Datum:** 2026-06-20  
**Doel:** Het systeem succesvol opzetten, testen, en live deployen  
**Aanpak:** 1 stap per keer. Elke stap volledig afmaken voordat we naar de volgende gaan.

---

## 📋 Stappenoverzicht

| Stap | Onderwerp | Status | Geschatte tijd |
|------|-----------|--------|---------------|
| **1** | Environment voorbereiden (Python, Docker, dependencies) | 🔲 Niet gestart | 15-30 min |
| **2** | Bybit Testnet account + API keys aanmaken | 🔲 Niet gestart | 10-15 min |
| **3** | Configuratie aanpassen (.env + config bestanden) | 🔲 Niet gestart | 10 min |
| **4** | Docker infra starten (Redis + PostgreSQL) | 🔲 Niet gestart | 5-10 min |
| **5** | Layer 1 testen: Data connectie met Bybit Testnet | 🔲 Niet gestart | 15-20 min |
| **6** | Layer 2 testen: Agent pipeline draaien | 🔲 Niet gestart | 15-20 min |
| **7** | Layer 3 testen: Trading execution (dry-run) | 🔲 Niet gestart | 20-30 min |
| **8** | Full integration: End-to-end test met testnet | 🔲 Niet gestart | 30-45 min |
| **9** | Backtesten + strategie optimaliseren | 🔲 Niet gestart | 1-2 uur |
| **10** | Live deploy: klein capital, monitoren, schalen | 🔲 Niet gestart | 1-2 weken |

---

## ✅ Per stap: wat moet je doen?

### Stap 1: Environment voorbereiden
- Python 3.11+ installeren (als je dat nog niet hebt)
- `pip install -r requirements.txt` draaien
- Docker Desktop installeren (als je dat nog niet hebt)
- Verifiëren dat alles werkt

### Stap 2: Bybit Testnet account
- Ga naar testnet.bybit.com
- Maak een account aan
- Genereer API keys (Read + Trade rechten)
- API keys opslaan in `.env` bestand

### Stap 3: Configuratie
- Kopieer `.env.example` naar `.env`
- Vul API keys in
- Pas `config/bybit_config.yaml` aan (testnet = true)
- Pas `config/strategy_config.yaml` aan (risk aan jouw voorkeur)
- Pas `config/agent_config.yaml` aan (LLM model keuze)

### Stap 4: Docker infra starten
- `docker-compose up -d` draaien
- Redis checken: `docker-compose ps`
- PostgreSQL checken: `docker-compose logs postgres`

### Stap 5: Layer 1 testen
- Bybit client connectie testen
- WebSocket data ontvangen
- Indicators berekenen
- Data cache werken

### Stap 6: Layer 2 testen
- Agent pipeline draaien
- Bias agent testen
- Signal agent testen
- Risk agent testen
- Consensus checken

### Stap 7: Layer 3 testen
- Order manager testen (met dummy data)
- Position tracker testen
- Risk manager kill switches testen
- Execution engine testen (dry-run)

### Stap 8: Full integration
- `main.py` draaien op testnet
- Trading loop starten
- Telegram alerts ontvangen
- Logs checken
- Kill switch testen

### Stap 9: Backtesten
- VectorBT backtest draaien
- Historische data inladen
- Strategie parameters optimaliseren
- Walk-forward validatie

### Stap 10: Live deploy
- Overschakelen naar live API keys (klein bedrag)
- Paper trade voor 2 weken
- Performance monitoren
- Capital geleidelijk verhogen

---

*Elke stap wordt individueel begeleid. We gaan NIET verder naar de volgende stap totdat de huidige 100% werkt.*
