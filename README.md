# HERO MCP Server

MCP-Server (Model Context Protocol) für die [HERO Handwerkersoftware](https://hero-software.de). Ermöglicht KI-Assistenten wie Claude den direkten Zugriff auf Kontakte, Projekte, Dokumente und Kalender in HERO.

## Features

| Tool | Beschreibung |
|------|-------------|
| `hero_create_project` | Neues Projekt via Lead API anlegen |
| `hero_get_contacts` | Kontakte/Kunden abfragen & suchen |
| `hero_get_projects` | Projekte auflisten & suchen |
| `hero_get_documents` | Dokumente (Angebote, Rechnungen) abrufen |
| `hero_get_calendar_events` | Kalendertermine abrufen |
| `hero_create_contact` | Neuen Kontakt erstellen |
| `hero_add_logbook_entry` | Protokolleintrag zu Projekt hinzufügen |
| `hero_graphql` | Direkte GraphQL-Abfrage (Experten-Tool) |

## API-Key beantragen

Den API-Key erhältst du kostenlos beim HERO Support: [hero-software.de/api-doku](https://hero-software.de/api-doku)

---

## Lokale Installation (Claude Desktop)

### Voraussetzungen

- Python 3.11+
- [Claude Desktop](https://claude.ai/download)

### 1. Repository klonen

```bash
git clone https://github.com/your-github-user/hero-mcp-server.git
cd hero-mcp-server
```

### 2. Abhängigkeiten installieren

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

### 3. API-Key konfigurieren

```bash
cp .env.example .env
```

`.env` öffnen und den API-Key eintragen:

```env
HERO_API_KEY=dein_api_key_hier
```

### 4. Claude Desktop konfigurieren

Datei öffnen:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Folgenden Block in `mcpServers` eintragen (Pfad anpassen):

```json
{
  "mcpServers": {
    "hero": {
      "command": "/absoluter/pfad/zum/hero-mcp-server/.venv/bin/hero-mcp-server",
      "env": {
        "HERO_API_KEY": "dein_api_key_hier"
      }
    }
  }
}
```

### 5. Claude Desktop neu starten

Der HERO-Server erscheint nun in Claude unter den verfügbaren Tools.

---

## Docker-Deployment (Portainer)

### Voraussetzungen

- Docker & Docker Compose
- [Portainer](https://www.portainer.io/) (optional, aber empfohlen)

### Image bauen

```bash
docker build -t hero-mcp-server:latest .
```

### Mit Docker Compose starten

```bash
# API-Key als Umgebungsvariable setzen
export HERO_API_KEY=dein_api_key_hier

docker compose up -d
```

Oder direkt in der `docker-compose.yml` eintragen:

```yaml
environment:
  - HERO_API_KEY=dein_api_key_hier
```

### Deployment über Portainer

1. In Portainer einloggen
2. **Stacks → Add Stack** öffnen
3. Stack-Name vergeben, z.B. `hero-mcp-server`
4. `docker-compose.yml` hochladen oder Inhalt einfügen
5. Unter **Environment variables** den Key `HERO_API_KEY` mit deinem API-Key eintragen
6. **Deploy the stack** klicken

> **Hinweis:** Der MCP-Server kommuniziert über stdio – im Docker-Container wird er als Dienst betrieben, der von einem MCP-fähigen Host (z.B. einem weiteren Container oder einem Reverse-Proxy mit MCP-Unterstützung) angesprochen wird.

### docker-compose.yml Übersicht

```yaml
services:
  hero-mcp-server:
    build: .
    image: hero-mcp-server:latest
    container_name: hero-mcp-server
    restart: unless-stopped
    environment:
      - HERO_API_KEY=${HERO_API_KEY}
    stdin_open: true
    tty: true
```

---

## Projektstruktur

```
hero-mcp-server/
├── src/
│   └── hero_mcp_server/
│       ├── __init__.py
│       ├── server.py        # MCP-Server & Tool-Definitionen
│       └── client.py        # HERO API Client (REST + GraphQL)
├── .env.example             # Vorlage für API-Key
├── claude_desktop_config.json  # Beispiel-Konfiguration für Claude Desktop
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## API-Referenz

- [HERO Lead API](https://hero-software.de/api-doku/lead-api)
- [HERO GraphQL Guide](https://hero-software.de/api-doku/graphql-guide)
- [MCP Protokoll Dokumentation](https://modelcontextprotocol.io)
