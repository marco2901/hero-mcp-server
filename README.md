# HERO MCP Server

MCP-Server (Model Context Protocol) für die [HERO Handwerkersoftware](https://hero-software.de). Ermöglicht KI-Assistenten wie Claude den direkten Zugriff auf Kontakte, Projekte, Dokumente und Kalender in HERO – gesichert über Authelia OIDC OAuth2.

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

Den HERO API-Key erhältst du kostenlos beim HERO Support: [hero-software.de/api-doku](https://hero-software.de/api-doku)

---

## Architektur-Überblick

`hero-mcp.your-domain.com` hat eine Doppelfunktion:

```
                    ┌─────────────────────────────────┐
                    │    hero-mcp.your-domain.com      │
                    └────────────┬────────────────────┘
                                 │ Traefik
          ┌──────────────────────┴──────────────────────┐
          │ Pfad-basiertes Routing                       │
          │                                              │
          ▼ /authorize, /api/oidc, /consent,             ▼ /sse, /messages/
          │ /.well-known, /static, /api, /               │
    ┌─────┴──────┐                               ┌───────┴────────┐
    │  Authelia  │  ←── OIDC Issuer              │ hero-mcp-server│
    │  :9091     │      Token Introspection       │  :8000 (SSE)   │
    └────────────┘                               └────────────────┘
```

**Traefik-Routing:**
- OIDC-Pfade (`/authorize`, `/api/oidc`, `/.well-known`, `/consent`, `/static`, `/api`, `/`) → **Authelia** (via file-based rules)
- MCP-Pfade (`/sse`, `/messages/`) → **hero-mcp-server** (via Docker labels)

**Auth-Flow:**
1. Claude.ai entdeckt OIDC-Config via `https://hero-mcp.your-domain.com/.well-known/openid-configuration`
2. Benutzer authentifiziert sich bei Authelia
3. Claude.ai erhält JWT Access Token
4. Claude.ai sendet `Bearer {JWT}` an `/sse`
5. hero-mcp-server validiert JWT via Authelia Token Introspection (`http://authelia:9091/api/oidc/introspection`)

---

## Option A: Lokal mit Claude Desktop (stdio)

Einfachster und sicherster Weg – kein Netzwerkzugriff, keine offenen Ports.

### Voraussetzungen
- Python 3.11+
- [Claude Desktop](https://claude.ai/download)

```bash
git clone https://github.com/your-github-user/hero-mcp-server.git
cd hero-mcp-server
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# HERO_API_KEY in .env eintragen
```

Claude Desktop konfigurieren (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "hero": {
      "command": "/absoluter/pfad/zum/hero-mcp-server/.venv/bin/hero-mcp-server",
      "env": {
        "HERO_API_KEY": "dein_hero_api_key"
      }
    }
  }
}
```

---

## Option B: Docker + Traefik + Authelia OAuth (claude.ai im Browser)

Fertige Beispiel-Dateien liegen im [`examples/`](examples/) Verzeichnis.

### Schritt 1: Authelia OIDC-Client konfigurieren

In deine Authelia `configuration.yml` unter `identity_providers.oidc.clients` eintragen
(Vorlage: [`examples/authelia-oidc-client.yml`](examples/authelia-oidc-client.yml)):

```yaml
identity_providers:
  oidc:
    clients:
      - client_id: claude-mcp
        client_name: Claude MCP
        client_secret: '$2b$12$BCRYPT_HASH_OF_YOUR_SECRET'  # bcrypt-Hash
        public: false
        authorization_policy: one_factor
        redirect_uris:
          - https://claude.ai/api/mcp/auth_callback
        scopes: [openid, profile, email, offline_access, address, phone, groups]
        grant_types: [authorization_code, refresh_token]
        response_types: [code]
        token_endpoint_auth_method: client_secret_post
```

> **bcrypt-Hash erzeugen:**
> ```bash
> docker run authelia/authelia:latest authelia crypto hash generate bcrypt --password 'dein_secret'
> ```

### Schritt 2: Traefik Routing-Regeln (file-based)

Datei in deinem Traefik-Rules-Verzeichnis ablegen
(Vorlage: [`examples/traefik-hero-mcp-oauth.yml`](examples/traefik-hero-mcp-oauth.yml)):

```yaml
http:
  middlewares:
    rewrite-authorize:
      replacePath:
        path: "/api/oidc/authorization"

  routers:
    hero-mcp-authorize:
      rule: "Host(`hero-mcp.your-domain.com`) && PathPrefix(`/authorize`)"
      entrypoints: [websecure]
      service: authelia-oidc
      middlewares: [rewrite-authorize]
      tls:
        certResolver: your-cert-resolver

    hero-mcp-root:
      rule: "Host(`hero-mcp.your-domain.com`) && Path(`/`)"
      entrypoints: [websecure]
      service: authelia-oidc
      tls:
        certResolver: your-cert-resolver

    hero-mcp-oidc:
      rule: "Host(`hero-mcp.your-domain.com`) && PathPrefix(`/api/oidc`)"
      entrypoints: [websecure]
      service: authelia-oidc
      tls:
        certResolver: your-cert-resolver

    hero-mcp-api:
      rule: "Host(`hero-mcp.your-domain.com`) && PathPrefix(`/api`)"
      entrypoints: [websecure]
      service: authelia-oidc
      tls:
        certResolver: your-cert-resolver

    hero-mcp-consent:
      rule: "Host(`hero-mcp.your-domain.com`) && PathPrefix(`/consent`)"
      entrypoints: [websecure]
      service: authelia-oidc
      tls:
        certResolver: your-cert-resolver

    hero-mcp-static:
      rule: "Host(`hero-mcp.your-domain.com`) && PathPrefix(`/static`)"
      entrypoints: [websecure]
      service: authelia-oidc
      tls:
        certResolver: your-cert-resolver

    hero-mcp-wellknown:
      rule: "Host(`hero-mcp.your-domain.com`) && PathPrefix(`/.well-known`)"
      entrypoints: [websecure]
      service: authelia-oidc
      tls:
        certResolver: your-cert-resolver

  services:
    authelia-oidc:
      loadBalancer:
        servers:
          - url: "http://authelia:9091"
```

> Traefik erkennt die Datei automatisch (hot-reload) – kein Neustart nötig.

### Schritt 3: Portainer Stack

```yaml
services:
  hero-mcp-server:
    image: ghcr.io/your-github-user/hero-mcp-server:latest
    container_name: hero-mcp-server
    restart: unless-stopped
    environment:
      - HERO_API_KEY=dein_hero_api_key
      - MCP_TRANSPORT=sse
      - MCP_API_KEY=optionaler_fallback_token       # nur für Claude Desktop im SSE-Modus
      - PORT=8000
      - OIDC_INTROSPECTION_URL=http://authelia:9091/api/oidc/introspection
      - OIDC_CLIENT_ID=claude-mcp
      - OIDC_CLIENT_SECRET=dein_secret_klartext     # Klartext (nicht der bcrypt-Hash!)
    expose:
      - "8000"
    labels:
      - traefik.enable=true
      - traefik.docker.network=traefik
      # Router für /sse  (PathPrefix akzeptiert nur einen Wert → zwei separate Router!)
      - traefik.http.routers.hero-mcp-sse.rule=Host(`hero-mcp.your-domain.com`) && PathPrefix(`/sse`)
      - traefik.http.routers.hero-mcp-sse.entrypoints=websecure
      - traefik.http.routers.hero-mcp-sse.service=hero-mcp-svc
      - traefik.http.routers.hero-mcp-sse.tls.certresolver=your-cert-resolver
      - traefik.http.routers.hero-mcp-sse.tls=true
      - traefik.http.routers.hero-mcp-sse.middlewares=middlewares-rate-limit@file,middlewares-secure-headers@file
      # Router für /messages
      - traefik.http.routers.hero-mcp-msg.rule=Host(`hero-mcp.your-domain.com`) && PathPrefix(`/messages`)
      - traefik.http.routers.hero-mcp-msg.entrypoints=websecure
      - traefik.http.routers.hero-mcp-msg.service=hero-mcp-svc
      - traefik.http.routers.hero-mcp-msg.tls.certresolver=your-cert-resolver
      - traefik.http.routers.hero-mcp-msg.tls=true
      - traefik.http.routers.hero-mcp-msg.middlewares=middlewares-rate-limit@file,middlewares-secure-headers@file
      # Service
      - traefik.http.services.hero-mcp-svc.loadbalancer.server.port=8000
    networks:
      - traefik

networks:
  traefik:
    external: true
```

> **Wichtig:** `OIDC_CLIENT_SECRET` = **Klartext** des Secrets. Den bcrypt-Hash braucht nur Authelia.

> **Kein `middlewares-authelia@file`!** Authelias ForwardAuth-Middleware ist für Browser-Sessions (Cookies). Claude.ai sendet Bearer-JWTs – diese werden direkt im Server via Token Introspection validiert.

### Schritt 4: claude.ai Connector einrichten

In claude.ai → **Settings → Integrations → Add custom connector**:

| Feld | Wert |
|------|------|
| Name | `Hero` |
| URL | `https://hero-mcp.your-domain.com/sse` |
| OAuth Client ID | `claude-mcp` |
| OAuth Client Secret | `dein_secret_klartext` |

Claude.ai führt den OAuth-Flow automatisch durch – Authelia zeigt eine Login-Seite, danach ist die Verbindung aktiv.

---

## Sicherheit

| Maßnahme | Details |
|----------|---------|
| HTTPS/TLS | Traefik + Let's Encrypt |
| OAuth2 / OIDC | Authelia als Issuer, JWT Access Tokens |
| Token Introspection | Jeder Token wird live gegen Authelia validiert |
| bcrypt Client Secret | Authelia speichert nur den Hash, nie den Klartext |
| Rate Limiting | Traefik-Middleware |
| Secure Headers | HSTS, X-Frame-Options etc. via Traefik |
| HERO API Key | Nur in Container-Umgebung, nie im Image oder Repo |

---

## Automatische Updates

GitHub Actions baut bei jedem Push auf `main` automatisch ein neues Image und veröffentlicht es auf `ghcr.io/your-github-user/hero-mcp-server:latest`.

In Portainer: **Stack → Update → "Re-pull image" → Deploy**

---

## Projektstruktur

```
hero-mcp-server/
├── src/
│   └── hero_mcp_server/
│       ├── __init__.py
│       ├── server.py        # MCP-Server, Tools, SSE-Transport & OIDC-Auth
│       └── client.py        # HERO API Client (REST Lead API + GraphQL)
├── examples/
│   ├── traefik-hero-mcp-oauth.yml   # Traefik file-based routing rules
│   └── authelia-oidc-client.yml     # Authelia OIDC-Client Konfiguration
├── .github/
│   └── workflows/
│       └── docker.yml       # Automatischer Docker-Build → ghcr.io
├── .env.example
├── claude_desktop_config.json
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## API-Referenz

- [HERO Lead API](https://hero-software.de/api-doku/lead-api)
- [HERO GraphQL Guide](https://hero-software.de/api-doku/graphql-guide)
- [MCP Protokoll](https://modelcontextprotocol.io)
- [Authelia OIDC](https://www.authelia.com/configuration/identity-providers/openid-connect/provider/)
