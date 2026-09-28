"""HERO API client – REST Lead API + GraphQL."""

import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

LEAD_API_URL = "https://login.hero-software.de/api/v1/Projects/create"
GRAPHQL_URL = "https://login.hero-software.de/api/external/v7/graphql"
# REST-Upload: liefert eine temporäre FileUpload-UUID, die GraphQL-Mutationen
# (Receipt_CreateReceipt, upload_document, upload_image, …) weiterverwenden.
UPLOAD_URL = "https://login.hero-software.de/app/v8/FileUploads/upload"


def _headers(json_body: bool = True) -> dict[str, str]:
    api_key = os.getenv("HERO_API_KEY")
    if not api_key:
        raise ValueError("HERO_API_KEY ist nicht gesetzt. Bitte .env konfigurieren.")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


async def create_project_lead(payload: dict[str, Any]) -> dict[str, Any]:
    """Erstellt ein neues Projekt über die HERO Lead API."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(LEAD_API_URL, json=payload, headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def graphql_query(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Führt eine GraphQL-Abfrage gegen die HERO API aus."""
    payload: dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(GRAPHQL_URL, json=payload, headers=_headers())
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(f"GraphQL Fehler: {data['errors']}")
        return data.get("data", {})


async def upload_file(content: bytes, filename: str, mime_type: str) -> dict[str, Any]:
    """Lädt eine Datei per REST zu HERO hoch und gibt das FileUpload-Objekt zurück.

    Die Datei landet bewusst in der Section "temp": Receipt_CreateReceipt/-Update
    akzeptieren nur temporäre Uploads ("Upload is not temporary") und übernehmen
    die Datei dann selbst.
    """
    files = {"file": (filename, content, mime_type)}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(UPLOAD_URL, files=files, headers=_headers(json_body=False))
        resp.raise_for_status()
        data = resp.json()
    if data.get("status") != "success" or not data.get("data", {}).get("uuid"):
        raise RuntimeError(f"HERO-Upload fehlgeschlagen: {data}")
    return data["data"]
