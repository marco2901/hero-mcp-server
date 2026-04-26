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
                    "phone": {"type": "string"},
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                    "zipcode": {"type": "string"},
                    "country_code": {"type": "string", "default": "DE"},
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
    query GetContacts($limit: Int, $offset: Int, $search: String) {
      contacts(first: $limit, skip: $offset, search: $search) {
        id
        number
        first_name
        last_name
        email
        phone
        company_name
        address {
          street
          city
          zipcode
          country_code
        }
      }
    }
    """
    variables = {
        "limit": args.get("limit", 20),
        "offset": args.get("offset", 0),
    }
    if args.get("search"):
        variables["search"] = args["search"]
    return await graphql_query(query, variables)


async def _get_projects(args: dict[str, Any]) -> dict[str, Any]:
    query = """
    query GetProjects($limit: Int, $offset: Int, $search: String) {
      project_matches(first: $limit, skip: $offset, search: $search) {
        id
        number
        measure
        status_code
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
    if args.get("search"):
        variables["search"] = args["search"]
    return await graphql_query(query, variables)


async def _get_documents(args: dict[str, Any]) -> dict[str, Any]:
    query = """
    query GetDocuments($limit: Int, $offset: Int) {
      customer_documents(first: $limit, skip: $offset) {
        id
        number
        created_at
        document_type
        status
        value
        vat
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
      calendar_events(first: $limit, skip: $offset) {
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
        number
        email
        first_name
        last_name
      }
    }
    """
    contact_input: dict[str, Any] = {"email": args["email"]}
    for field in ("first_name", "last_name", "company_name", "phone"):
        if args.get(field):
            contact_input[field] = args[field]
    if any(args.get(k) for k in ("street", "city", "zipcode")):
        contact_input["address"] = {
            "street": args.get("street", ""),
            "city": args.get("city", ""),
            "zipcode": args.get("zipcode", ""),
            "country_code": args.get("country_code", "DE"),
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

    # Token im Pfad: /sse            → kein Token konfiguriert (lokal/test)
    # Token im Pfad: /{token}/sse    → Claude.ai trägt die volle URL ein
    # Bearer {MCP_API_KEY}           → Claude Desktop / API-Clients
    # Bearer {JWT}                   → Claude.ai via Authelia OAuth (JWT-Introspection)

    async def _is_authorized(request: Request, path_token: str | None = None) -> bool:
        if not mcp_api_key:
            return True

        # 1. Token im Pfad (Claude.ai ohne OAuth)
        if path_token and path_token == mcp_api_key:
            logging.info("Auth OK: Pfad-Token")
            return True

        # 2. Statischer Bearer Token (Claude Desktop / API-Clients)
        auth = request.headers.get("Authorization", "")
        if auth == f"Bearer {mcp_api_key}":
            logging.info("Auth OK: statischer Bearer Token")
            return True

        # 3. Authelia hat den Request bereits validiert (middlewares-authelia@file in Traefik)
        #    Authelia setzt nach erfolgreicher Validierung den Remote-User Header
        remote_user = request.headers.get("Remote-User", "")
        if remote_user:
            logging.info("Auth OK: Authelia Remote-User=%s", remote_user)
            return True

        # 4. JWT direkt via Authelia OIDC Introspection (ohne Traefik-Middleware)
        if auth.startswith("Bearer "):
            jwt_token = auth[7:]
            logging.info("JWT erhalten, versuche Introspection (erste 20 Zeichen: %s…)", jwt_token[:20])
            if not oidc_introspection_url:
                logging.warning("OIDC_INTROSPECTION_URL nicht gesetzt – JWT abgelehnt")
            elif not oidc_client_id or not oidc_client_secret:
                logging.warning("OIDC_CLIENT_ID oder OIDC_CLIENT_SECRET fehlt – JWT abgelehnt")
            else:
                logging.info("Introspection gegen %s (client_id=%s)", oidc_introspection_url, oidc_client_id)
                try:
                    async with _httpx.AsyncClient() as http:
                        resp = await http.post(
                            oidc_introspection_url,
                            data={"token": jwt_token},
                            auth=(oidc_client_id, oidc_client_secret),
                            timeout=5.0,
                        )
                        body = resp.json()
                        active = body.get("active", False)
                        logging.info("Introspection: HTTP %s, active=%s", resp.status_code, active)
                        return active
                except Exception as e:
                    logging.error("Introspection fehlgeschlagen: %s", e)

        logging.warning("Auth ABGELEHNT – kein gültiger Token. Headers: %s",
                        {k: v for k, v in request.headers.items() if k.lower() not in ("cookie",)})
        return False

    sse_plain = SseServerTransport("/messages/")
    sse_token = SseServerTransport("/t/{token}/messages/")

    async def handle_sse(request: Request):
        if not await _is_authorized(request):
            return Response("Unauthorized", status_code=401)
        async with sse_plain.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())

    async def handle_sse_with_token(request: Request):
        token = request.path_params.get("token", "")
        if not await _is_authorized(request, path_token=token):
            return Response("Unauthorized", status_code=401)
        async with sse_token.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())

    app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse_plain.handle_post_message),
            Route("/t/{token}/sse", endpoint=handle_sse_with_token),
            Mount("/t/{token}/messages/", app=sse_token.handle_post_message),
        ],
    )

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
