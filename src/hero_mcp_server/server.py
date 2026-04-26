"""HERO MCP Server – MCP-Tools für die HERO Handwerkersoftware."""

import json
import logging
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from .client import create_project_lead, graphql_query

server = Server("hero-mcp-server")


# ---------------------------------------------------------------------------
# Tool-Definitionen
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="hero_create_project",
            description=(
                "Legt ein neues Projekt (Lead) in HERO an. "
                "Pflichtfeld: measure (Gewerk-Kürzel, z.B. 'PRJ') und customer.email."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "measure": {
                        "type": "string",
                        "description": "Gewerk-Kürzel, z.B. 'PRJ', 'HZG', 'SAN'",
                    },
                    "customer_email": {"type": "string", "description": "E-Mail des Kunden"},
                    "customer_title": {"type": "string", "description": "Anrede (Herr/Frau)"},
                    "customer_first_name": {"type": "string"},
                    "customer_last_name": {"type": "string"},
                    "customer_company": {"type": "string", "description": "Firmenname"},
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                    "zipcode": {"type": "string"},
                    "country_code": {"type": "string", "default": "DE"},
                    "comment": {"type": "string", "description": "Eintrag ins Projektprotokoll"},
                    "partner_notes": {"type": "string", "description": "Notiz-Feld"},
                    "partner_source": {"type": "string", "description": "Lead-Quelle"},
                },
                "required": ["measure", "customer_email"],
            },
        ),
        types.Tool(
            name="hero_get_contacts",
            description="Listet Kontakte/Kunden aus HERO. Optional: Suchbegriff und Seitenanzahl.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "Suchbegriff (Name, E-Mail, …)"},
                    "limit": {"type": "integer", "default": 20, "description": "Anzahl Ergebnisse"},
                    "offset": {"type": "integer", "default": 0},
                },
            },
        ),
        types.Tool(
            name="hero_get_projects",
            description="Listet Projekte aus HERO. Optional: Suchbegriff und Seitenanzahl.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                    "offset": {"type": "integer", "default": 0},
                },
            },
        ),
        types.Tool(
            name="hero_get_documents",
            description="Listet Dokumente (Angebote, Rechnungen, …) aus HERO.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 20},
                    "offset": {"type": "integer", "default": 0},
                },
            },
        ),
        types.Tool(
            name="hero_get_calendar_events",
            description="Listet Termine aus dem HERO-Kalender.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 20},
                    "offset": {"type": "integer", "default": 0},
                },
            },
        ),
        types.Tool(
            name="hero_create_contact",
            description="Erstellt einen neuen Kontakt in HERO.",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {"type": "string"},
                    "first_name": {"type": "string"},
                    "last_name": {"type": "string"},
                    "company_name": {"type": "string"},
                    "phone_home": {"type": "string", "description": "Festnetz"},
                    "phone_mobile": {"type": "string", "description": "Mobilnummer"},
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                    "zipcode": {"type": "string"},
                },
                "required": ["email"],
            },
        ),
        types.Tool(
            name="hero_add_logbook_entry",
            description="Fügt einen Protokoll-Eintrag zu einem HERO-Projekt hinzu.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "ID des Projekts"},
                    "message": {"type": "string", "description": "Protokoll-Text"},
                },
                "required": ["project_id", "message"],
            },
        ),
        types.Tool(
            name="hero_graphql",
            description=(
                "Führt eine beliebige GraphQL-Abfrage direkt gegen die HERO API aus. "
                "Für Experten und individuelle Abfragen."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "GraphQL Query oder Mutation"},
                    "variables": {
                        "type": "object",
                        "description": "Optionale GraphQL-Variablen",
                    },
                },
                "required": ["query"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool-Handler
# ---------------------------------------------------------------------------

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    try:
        result = await _dispatch(name, arguments)
    except Exception as exc:
        result = {"error": str(exc)}
    return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def _dispatch(name: str, args: dict[str, Any]) -> Any:
    if name == "hero_create_project":
        return await _create_project(args)
    if name == "hero_get_contacts":
        return await _get_contacts(args)
    if name == "hero_get_projects":
        return await _get_projects(args)
    if name == "hero_get_documents":
        return await _get_documents(args)
    if name == "hero_get_calendar_events":
        return await _get_calendar_events(args)
    if name == "hero_create_contact":
        return await _create_contact(args)
    if name == "hero_add_logbook_entry":
        return await _add_logbook_entry(args)
    if name == "hero_graphql":
        return await graphql_query(args["query"], args.get("variables"))
    raise ValueError(f"Unbekanntes Tool: {name}")


# ---------------------------------------------------------------------------
# Einzelne Implementierungen
# ---------------------------------------------------------------------------

async def _create_project(args: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "measure": args["measure"],
        "customer": {"email": args["customer_email"]},
    }
    customer = payload["customer"]
    for key, field in [
        ("customer_title", "title"),
        ("customer_first_name", "first_name"),
        ("customer_last_name", "last_name"),
        ("customer_company", "company_name"),
    ]:
        if args.get(key):
            customer[field] = args[key]

    if any(args.get(k) for k in ("street", "city", "zipcode")):
        payload["address"] = {
            "street": args.get("street", ""),
            "city": args.get("city", ""),
            "zipcode": args.get("zipcode", ""),
            "country_code": args.get("country_code", "DE"),
        }

    project_match: dict[str, Any] = {}
    if args.get("comment"):
        project_match["comment"] = args["comment"]
    if args.get("partner_notes"):
        project_match["partner_notes"] = args["partner_notes"]
    if args.get("partner_source"):
        project_match["partner_source"] = args["partner_source"]
    if project_match:
        payload["project_match"] = project_match

    return await create_project_lead(payload)


async def _get_contacts(args: dict[str, Any]) -> dict[str, Any]:
    query = """
    query GetContacts($limit: Int, $offset: Int) {
      contacts(first: $limit, offset: $offset) {
        id
        nr
        first_name
        last_name
        email
        phone_home
        phone_mobile
        company_name
        address {
          street
          city
          zipcode
        }
      }
    }
    """
    variables = {
        "limit": args.get("limit", 20),
        "offset": args.get("offset", 0),
    }
    return await graphql_query(query, variables)


async def _get_projects(args: dict[str, Any]) -> dict[str, Any]:
    query = """
    query GetProjects($limit: Int, $offset: Int) {
      project_matches(first: $limit, offset: $offset) {
        id
        name
        project_nr
        display_id
        measure { name }
        current_project_match_status { name }
        contact {
          first_name
          last_name
          email
          company_name
        }
        address {
          street
          city
          zipcode
        }
      }
    }
    """
    variables = {
        "limit": args.get("limit", 20),
        "offset": args.get("offset", 0),
    }
    return await graphql_query(query, variables)


async def _get_documents(args: dict[str, Any]) -> dict[str, Any]:
    query = """
    query GetDocuments($limit: Int, $offset: Int) {
      customer_documents(first: $limit, offset: $offset) {
        id
        nr
        date
        created
        type
        document_type { name }
        status_code
        status_name
        value
        vat
        currency
      }
    }
    """
    variables = {
        "limit": args.get("limit", 20),
        "offset": args.get("offset", 0),
    }
    return await graphql_query(query, variables)


async def _get_calendar_events(args: dict[str, Any]) -> dict[str, Any]:
    query = """
    query GetCalendarEvents($limit: Int, $offset: Int) {
      calendar_events(first: $limit, offset: $offset) {
        id
        title
        start_at
        end_at
        description
      }
    }
    """
    variables = {
        "limit": args.get("limit", 20),
        "offset": args.get("offset", 0),
    }
    return await graphql_query(query, variables)


async def _create_contact(args: dict[str, Any]) -> dict[str, Any]:
    query = """
    mutation CreateContact($input: ContactInput!) {
      create_contact(input: $input) {
        id
        nr
        email
        first_name
        last_name
      }
    }
    """
    contact_input: dict[str, Any] = {"email": args["email"]}
    for field in ("first_name", "last_name", "company_name", "phone_home", "phone_mobile"):
        if args.get(field):
            contact_input[field] = args[field]
    if any(args.get(k) for k in ("street", "city", "zipcode")):
        contact_input["address"] = {
            "street": args.get("street", ""),
            "city": args.get("city", ""),
            "zipcode": args.get("zipcode", ""),
        }
    return await graphql_query(query, {"input": contact_input})


async def _add_logbook_entry(args: dict[str, Any]) -> dict[str, Any]:
    query = """
    mutation AddLogbookEntry($project_id: ID!, $message: String!) {
      add_logbook_entry(project_id: $project_id, message: $message) {
        id
        created_at
        message
      }
    }
    """
    return await graphql_query(query, {
        "project_id": args["project_id"],
        "message": args["message"],
    })


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------

def main() -> None:
    import asyncio
    import os
    if os.getenv("MCP_TRANSPORT", "stdio") == "sse":
        _run_sse()
    else:
        asyncio.run(mcp.server.stdio.run_server(server))


def _run_sse() -> None:
    import os
    import uvicorn
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.routing import Mount, Route

    import httpx as _httpx

    mcp_api_key = os.getenv("MCP_API_KEY", "")
    oidc_introspection_url = os.getenv("OIDC_INTROSPECTION_URL", "")
    oidc_client_id = os.getenv("OIDC_CLIENT_ID", "")
    oidc_client_secret = os.getenv("OIDC_CLIENT_SECRET", "")

    # Auth-Reihenfolge:
    # 1. Bearer {MCP_API_KEY}  → Claude Desktop / direkte API-Clients
    # 2. Bearer {JWT}          → Claude.ai via Authelia OIDC (Token Introspection)

    async def _is_authorized(request: Request) -> bool:
        if not mcp_api_key:
            return True

        auth = request.headers.get("Authorization", "")

        # 1. Statischer Bearer Token (Claude Desktop)
        if auth == f"Bearer {mcp_api_key}":
            logging.info("Auth OK: statischer Bearer Token")
            return True

        # 2. JWT via Authelia OIDC Token Introspection (Claude.ai)
        if auth.startswith("Bearer ") and oidc_introspection_url and oidc_client_id and oidc_client_secret:
            jwt_token = auth[7:]
            logging.info("JWT erhalten, starte Introspection…")
            try:
                async with _httpx.AsyncClient() as http:
                    resp = await http.post(
                        oidc_introspection_url,
                        data={"token": jwt_token},
                        auth=(oidc_client_id, oidc_client_secret),
                        timeout=5.0,
                    )
                    active = resp.json().get("active", False)
                    logging.info("Introspection: HTTP %s, active=%s", resp.status_code, active)
                    return active
            except Exception as e:
                logging.error("Introspection fehlgeschlagen: %s", e)

        logging.warning("Auth ABGELEHNT für %s %s", request.method, request.url.path)
        return False

    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request):
        if not await _is_authorized(request):
            return Response("Unauthorized", status_code=401)
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())

    app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
