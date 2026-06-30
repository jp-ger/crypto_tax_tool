# Crypto Tax Tool

Lokale Windows-Desktop-Anwendung zur Auswertung von Binance-Daten für eine deutsche Krypto-Steuerdokumentation.

> Hinweis: Dieses Projekt ersetzt keine Steuerberatung. Ziel ist eine nachvollziehbare, reproduzierbare Datenaufbereitung und Berechnung auf Basis exportierter/API-geladener Transaktionen.

## Ziele

- Vollständig lokale Datenhaltung mit SQLite
- Binance-API-Synchronisierung ohne CSV-Pflicht
- Einheitliches Datenmodell für Spot, Convert, Earn, Rewards, Deposits und Withdrawals
- Historische EUR-Bewertung mit lokalem Kurscache
- FIFO-Engine mit Haltefristprüfung nach deutschem Privatvermögen-Kontext
- Excel-/CSV-/PDF-Reports für Steuerdokumentation
- Windows-GUI und spätere EXE-Erstellung

## Entwicklungsphasen

### Meilenstein 1: Fundament

- Projektstruktur
- Konfiguration
- Logging
- SQLite-Datenbank
- GUI-Shell
- Binance-Client-Schnittstelle
- Platzhalter für Sync-Service

### Meilenstein 2: Binance Sync

- Spot Trades
- Convert
- Earn / Staking / Rewards
- Deposits / Withdrawals
- Delta-Sync und Resume

### Meilenstein 3: Steuerlogik

- Historische Kurse
- FIFO-Lots
- Gebührenbehandlung
- Haltefrist
- Plausibilitätsprüfung

### Meilenstein 4: Reports

- Steuerzusammenfassung
- Einzelveräußerungen
- FIFO-Nachweis
- Offene Bestände
- Finanzamt-kompatibler Export

## Quick Start für Entwickler

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
python -m crypto_tax_tool
```

## Repository-Struktur

```text
src/crypto_tax_tool/
  api/          Exchange-Clients, zunächst Binance
  database/     SQLite-Initialisierung und Repositories
  gui/          PySide6 Desktop-Oberfläche
  models/       Einheitliche Domänenmodelle
  services/     Sync-, Tax-, Pricing- und Report-Services
  utils/        Logging, Pfade, Hilfsfunktionen

tests/          Automatisierte Tests
docs/           Architektur- und Steuerlogik-Dokumentation
```
