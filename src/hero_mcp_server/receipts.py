"""Ausgabenbelege (Receipts) mit PDF in HERO anlegen.

Ablauf: Datei laden (URL oder Base64) → REST-Upload zu HERO (liefert
file_upload_uuid) → Receipt_CreateReceipt / Receipt_UpdateReceipt.
Duplikatschutz über Belegnummer + Lieferant + Bruttobetrag.
"""

import base64
import mimetypes
import os
import re
from typing import Any
from urllib.parse import unquote, urlparse

import httpx

from .client import graphql_query, upload_file

MAX_FILE_BYTES = 25 * 1024 * 1024
ALLOWED_MIME_PREFIXES = ("application/pdf", "image/")
STANDARD_VAT_RATES = (0.0, 7.0, 19.0)

# UI-Link zum Beleg; {id} wird ersetzt. Überschreibbar, falls HERO die Route ändert.
RECEIPT_URL_TEMPLATE = os.getenv(
    "HERO_RECEIPT_URL_TEMPLATE",
    "https://login.hero-software.de/Receipts/edit/{id}",
)

RECEIPT_FIELDS = """
  id
  type
  number
  internalNumber
  statusCode
  captureState
  receiptDate
  serviceDate
  dueDate
  netValue
  value
  statedTotalNet
  statedTotalVat
  statedTotalGross
  category
  isReverseCharge
  supplierVatNumber
  customerId
  customerCompanyName
  fileUploadId
  fileUpload { id uuid filename url }
"""


# ---------------------------------------------------------------------------
# Datei laden
# ---------------------------------------------------------------------------

def _filename_from_disposition(header: str) -> str | None:
    m = re.search(r"filename\*\s*=\s*[^']*''([^;]+)", header, re.IGNORECASE)
    if m:
        return unquote(m.group(1).strip().strip('"'))
    m = re.search(r'filename\s*=\s*"?([^";]+)"?', header, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _check_mime(mime: str, filename: str) -> str:
    mime = (mime or "").split(";")[0].strip().lower()
    if not mime or mime == "application/octet-stream":
        mime = mimetypes.guess_type(filename)[0] or ""
    if not mime.startswith(ALLOWED_MIME_PREFIXES):
        raise ValueError(
            f"Dateityp '{mime or 'unbekannt'}' wird nicht akzeptiert (nur PDF/Bilder). "
            "Ist der Link abgelaufen oder zeigt er auf eine Login-Seite?"
        )
    return mime


async def load_file(args: dict[str, Any]) -> tuple[bytes, str, str]:
    """Gibt (Inhalt, Dateiname, MIME-Typ) aus sourceUrl oder fileBase64 zurück."""
    source_url = args.get("sourceUrl")
    file_b64 = args.get("fileBase64")
    filename = args.get("filename")

    if file_b64:
        if not filename:
            raise ValueError("filename ist bei fileBase64 Pflicht")
        if "," in file_b64[:100] and file_b64.startswith("data:"):
            file_b64 = file_b64.split(",", 1)[1]
        content = base64.b64decode(file_b64, validate=False)
        mime = _check_mime(mimetypes.guess_type(filename)[0] or "", filename)
    elif source_url:
        if urlparse(source_url).scheme not in ("http", "https"):
            raise ValueError("sourceUrl muss http(s) sein")
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            async with client.stream("GET", source_url) as resp:
                resp.raise_for_status()
                chunks: list[bytes] = []
                size = 0
                async for chunk in resp.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_FILE_BYTES:
                        raise ValueError("Datei größer als 25 MB")
                    chunks.append(chunk)
                content = b"".join(chunks)
                if not filename:
                    filename = _filename_from_disposition(
                        resp.headers.get("content-disposition", "")
                    ) or os.path.basename(unquote(urlparse(str(resp.url)).path))
                filename = filename or "beleg.pdf"
                mime = _check_mime(resp.headers.get("content-type", ""), filename)
    else:
        raise ValueError("Entweder sourceUrl oder fileBase64 + filename angeben")

    if not content:
        raise ValueError("Datei ist leer")
    if len(content) > MAX_FILE_BYTES:
        raise ValueError("Datei größer als 25 MB")
    if mime == "application/pdf" and not content.startswith(b"%PDF"):
        raise ValueError("Inhalt ist kein PDF (Signatur %PDF fehlt)")
    if mime == "application/pdf" and not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    return content, filename, mime


# ---------------------------------------------------------------------------
# Lieferant
# ---------------------------------------------------------------------------

async def _find_supplier(name: str) -> dict[str, Any] | None:
    data = await graphql_query(
        """
        query FindSupplier($search: String) {
          contacts(search: $search, first: 25) { id nr company_name category }
        }
        """,
        {"search": name},
    )
    wanted = name.casefold().strip()
    candidates = [c for c in data.get("contacts") or [] if c.get("company_name")]
    suppliers = [c for c in candidates if c.get("category") == "supplier"] or candidates
    for c in suppliers:
        if c["company_name"].casefold().strip() == wanted:
            return c
    for c in suppliers:
        if c["company_name"].casefold().startswith(wanted):
            return c
    return None


async def _create_supplier(name: str) -> dict[str, Any]:
    data = await graphql_query(
        """
        mutation CreateSupplier($contact: CustomerInput) {
          create_contact(findExisting: true, contact: $contact) { id nr company_name category }
        }
        """,
        {"contact": {"company_name": name, "category": "supplier", "type": "commercial"}},
    )
    return data["create_contact"]


async def _resolve_supplier(args: dict[str, Any], create: bool) -> tuple[int | None, dict[str, Any] | None, bool]:
    """Gibt (customerId, Kontakt, neu_angelegt) zurück."""
    if args.get("customerId"):
        return int(args["customerId"]), None, False
    name = (args.get("supplierName") or "").strip()
    if not name:
        raise ValueError("customerId oder supplierName angeben")
    found = await _find_supplier(name)
    if found:
        return int(found["id"]), found, False
    if not create:
        return None, None, False
    created = await _create_supplier(name)
    return int(created["id"]), created, True


# ---------------------------------------------------------------------------
# Beträge / Positionen
# ---------------------------------------------------------------------------

def _amounts(args: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    net, vat, gross = (args.get(k) for k in ("totalNet", "totalVat", "totalGross"))
    net = float(net) if net is not None else None
    vat = float(vat) if vat is not None else None
    gross = float(gross) if gross is not None else None
    if gross is None and net is not None and vat is not None:
        gross = round(net + vat, 2)
    if net is None and gross is not None and vat is not None:
        net = round(gross - vat, 2)
    if vat is None and gross is not None and net is not None:
        vat = round(gross - net, 2)
    return net, vat, gross


def _vat_rate(args: dict[str, Any], net: float | None, vat: float | None) -> float:
    if args.get("vatRate") is not None:
        return float(args["vatRate"])
    if args.get("isReverseCharge"):
        return 0.0
    if not net or vat is None:
        return 19.0
    rate = vat / net * 100
    nearest = min(STANDARD_VAT_RATES, key=lambda r: abs(r - rate))
    # Rundungsdifferenzen (z. B. 1,04 / 5,46 = 19,05 %) auf den Regelsatz ziehen
    return nearest if abs(nearest - rate) < 0.5 else round(rate, 2)


def _positions(args: dict[str, Any], net: float | None, vat: float | None, gross: float | None) -> list[dict[str, Any]]:
    if args.get("positions"):
        return args["positions"]
    if gross is None and net is None:
        raise ValueError("Mindestens totalGross (oder totalNet + totalVat) angeben")
    rate = _vat_rate(args, net, vat)
    pos: dict[str, Any] = {
        "value": gross if gross is not None else net,
        "vat": rate,
        "vatIncl": gross is not None,
    }
    for key in ("description", "bookAccountId", "projectMatchId", "costCenterId"):
        if args.get(key) is not None:
            pos[key] = args[key]
    return [pos]


# ---------------------------------------------------------------------------
# Duplikatsuche
# ---------------------------------------------------------------------------

async def _find_duplicate(number: str, customer_id: int | None, supplier_name: str | None, gross: float | None) -> dict[str, Any] | None:
    filters: dict[str, Any] = {"number": {"equals": number}}
    if customer_id:
        filters["customerId"] = {"equals": customer_id}
    data = await graphql_query(
        f"""
        query FindReceipt($filters: Receipt_ReceiptFiltersInput) {{
          Receipt_Receipts(filters: $filters, first: 50) {{ edges {{ node {{ {RECEIPT_FIELDS} }} }} }}
        }}
        """,
        {"filters": filters},
    )
    for edge in data["Receipt_Receipts"]["edges"]:
        r = edge["node"]
        if r.get("number") != number:
            continue
        if not customer_id and supplier_name:
            if (r.get("customerCompanyName") or "").casefold().strip() != supplier_name.casefold().strip():
                continue
        if gross is not None:
            amount = r.get("statedTotalGross") if r.get("statedTotalGross") is not None else r.get("value")
            if amount is None or abs(float(amount) - gross) > 0.005:
                continue
        return r
    return None


# ---------------------------------------------------------------------------
# Öffentliche Operationen
# ---------------------------------------------------------------------------

def _result(action: str, receipt: dict[str, Any], **extra: Any) -> dict[str, Any]:
    rid = receipt["id"]
    return {
        "action": action,
        "receiptId": int(rid),
        "internalNumber": receipt.get("internalNumber"),
        "link": RECEIPT_URL_TEMPLATE.format(id=rid),
        "receipt": receipt,
        **extra,
    }


async def _update_file(receipt_id: int, file_upload_uuid: str) -> dict[str, Any]:
    data = await graphql_query(
        f"""
        mutation AttachReceiptFile($input: Receipt_UpdateReceiptInput!) {{
          Receipt_UpdateReceipt(input: $input) {{ {RECEIPT_FIELDS} }}
        }}
        """,
        {"input": {"id": receipt_id, "fileUploadUuid": file_upload_uuid}},
    )
    return data["Receipt_UpdateReceipt"]


async def create_receipt(args: dict[str, Any]) -> dict[str, Any]:
    number = str(args.get("number") or "").strip()
    if not number:
        raise ValueError("number (Belegnummer) ist Pflicht – sie dient dem Duplikatschutz")
    if not args.get("receiptDate"):
        raise ValueError("receiptDate ist Pflicht (YYYY-MM-DD)")
    if not (args.get("sourceUrl") or args.get("fileBase64")):
        raise ValueError("sourceUrl oder fileBase64 + filename angeben")

    net, vat, gross = _amounts(args)
    supplier_name = args.get("supplierName")

    # 1. Lieferant nur nachschlagen – neu angelegt wird erst, wenn wirklich ein Beleg entsteht
    customer_id, supplier, _ = await _resolve_supplier(args, create=False)

    # 2. Duplikatschutz (vor dem Upload, damit keine verwaisten Temp-Dateien entstehen)
    existing = await _find_duplicate(number, customer_id, supplier_name, gross)
    if existing:
        if existing.get("fileUploadId") and not args.get("replaceFile"):
            return _result(
                "exists",
                existing,
                message="Beleg existiert bereits und hat schon eine Datei – nichts geändert "
                "(replaceFile=true ersetzt die Datei).",
            )
        content, filename, mime = await load_file(args)
        upload = await upload_file(content, filename, mime)
        updated = await _update_file(int(existing["id"]), upload["uuid"])
        return _result(
            "file_attached",
            updated,
            message="Beleg existierte bereits – nur die Datei wurde angehängt, kein zweiter Beleg angelegt.",
        )

    # 3. Datei laden + hochladen
    content, filename, mime = await load_file(args)
    upload = await upload_file(content, filename, mime)

    # 4. Lieferant ggf. anlegen
    supplier_created = False
    if customer_id is None:
        customer_id, supplier, supplier_created = await _resolve_supplier(
            args, create=bool(args.get("createSupplier", True))
        )
        if customer_id is None:
            raise ValueError(f"Lieferant '{supplier_name}' nicht in HERO gefunden (createSupplier=false)")

    receipt_input: dict[str, Any] = {
        "type": args.get("type", "output"),
        "number": number,
        "receiptDate": args["receiptDate"],
        "customerId": customer_id,
        "fileUploadUuid": upload["uuid"],
        "category": args.get("category", "INVOICE"),
        "currency": args.get("currency", "EUR"),
        "isReverseCharge": bool(args.get("isReverseCharge", False)),
        "source": "WEB",
        "receiptPositions": _positions(args, net, vat, gross),
    }
    for key in ("serviceDate", "dueDate", "supplierVatNumber", "externalCustomerNumber", "taxId"):
        if args.get(key) not in (None, ""):
            receipt_input[key] = args[key]
    for key, value in (("statedTotalNet", net), ("statedTotalVat", vat), ("statedTotalGross", gross)):
        if value is not None:
            receipt_input[key] = value

    data = await graphql_query(
        f"""
        mutation CreateReceipt($input: Receipt_CreateReceiptInput!) {{
          Receipt_CreateReceipt(input: $input) {{ {RECEIPT_FIELDS} }}
        }}
        """,
        {"input": receipt_input},
    )
    extra: dict[str, Any] = {}
    if supplier_created:
        extra["supplierCreated"] = supplier
    return _result("created", data["Receipt_CreateReceipt"], **extra)


async def attach_receipt_file(args: dict[str, Any]) -> dict[str, Any]:
    receipt_id = args.get("receiptId")
    if not receipt_id:
        raise ValueError("receiptId fehlt")
    content, filename, mime = await load_file(args)
    upload = await upload_file(content, filename, mime)
    updated = await _update_file(int(receipt_id), upload["uuid"])
    return _result("file_attached", updated)
