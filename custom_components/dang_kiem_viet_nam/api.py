"""HTTP/XML client for the Vietnamese vehicle inspection certificate site."""

from __future__ import annotations

import json
import ssl
from pathlib import Path
import xml.etree.ElementTree as ET

import aiohttp
import certifi

ENDPOINT = "https://gcndangkiem.vr.org.vn/chi-tiet"

# Use the maintained public CA bundle and the official RapidSSL intermediate.
# Windows can build this chain automatically, but OpenSSL/aiohttp may fail when
# the remote server omits the intermediate certificate. The intermediate is
# distributed by DigiCert and its SHA-256 fingerprint is checked at development
# time: 44:22:E9:63:EE:53:CD:58:CC:9F:85:CD:40:BF:5F:FE:C0:09:5F:DF:1A:15:45:35:66:1C:1C:06:BC:AD:C6:9B.
# TLS certificate and hostname verification remain enabled. The intermediate
# certificate expires on 2027-11-02; update this bundled certificate before then
# or preferably when the website fixes its served certificate chain.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
_INTERMEDIATE_CERT = Path(__file__).with_name("rapidssl_tls_rsa_ca_g1.pem")
_SSL_CONTEXT.load_verify_locations(cafile=str(_INTERMEDIATE_CERT))

# Deliberately allow-list fields so that owner names, addresses, and other
# personal fields present in the source XML are never copied into HA state.
SAFE_XML_FIELDS = frozenset(
    {
        "NgayKD",
        "HanKDtoi",
        "BienDK",
        "SoKhung",
        "SoMay",
        "SoPhieuKD",
        "SoTemGCN",
        "VetTruoc",
        "CDCS1_2",
        "CS",
        "CTBanhXe",
        "ChieuCao",
        "ChieuDai",
        "ChieuRong",
        "ChuKyKD",
        "CoLop1",
        "CoLop2",
        "DungTich",
        "LoaiPT",
        "NamSX",
        "NgayDK",
        "NhanHieu",
        "NhienLieu",
        "Nmax",
        "NoiSX",
        "Odometer",
        "VongQuay",
    }
)


class DangKiemApiError(Exception):
    """Raised when the remote endpoint does not return a usable record."""


def _local_name(tag: str) -> str:
    """Return an XML tag name without any namespace prefix."""
    return tag.rsplit("}", 1)[-1]


def _parse_record(xml_content: bytes) -> dict[str, str]:
    """Parse one certificate record while excluding personal information."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as err:
        raise DangKiemApiError("The server response was not valid XML") from err

    record = next(
        (element for element in root.iter() if _local_name(element.tag) == "GiayChungNhanDangKiem"),
        None,
    )
    if record is None:
        raise DangKiemApiError("The XML response did not contain a certificate record")

    data: dict[str, str] = {}
    for child in record:
        name = _local_name(child.tag)
        if name in SAFE_XML_FIELDS:
            data[name] = (child.text or "").strip()

    if not data.get("BienDK") and not data.get("SoKhung"):
        raise DangKiemApiError("The XML response did not contain vehicle identification data")

    return data


async def async_fetch_vehicle(
    session: aiohttp.ClientSession,
    query: dict[str, str],
) -> dict[str, str]:
    """Fetch a vehicle certificate using the public XML download handler."""
    request_data = {
        "biendangky": query.get("biendangky", "").strip(),
        "sokhung": query.get("sokhung", "").strip(),
        "somay": query.get("somay", "").strip(),
        "soseri": query.get("soseri", "").strip(),
        "loaipt": query.get("loaipt", "1").strip() or "1",
    }
    params = {
        "handler": "DownloadXml",
        "data": json.dumps(request_data, ensure_ascii=False, separators=(",", ":")),
        "type": "1",
    }
    headers = {
        "Accept": "application/xml, text/xml;q=0.9, */*;q=0.8",
        # Match the User-Agent used by the successful Windows curl test.
        "User-Agent": "Mozilla/5.0",
    }

    try:
        async with session.get(
            ENDPOINT,
            params=params,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
            ssl=_SSL_CONTEXT,
        ) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            if response.status != 200:
                raise DangKiemApiError(
                    f"HTTP {response.status}; Content-Type={content_type or 'unknown'}"
                )
            content = await response.read()
            if "xml" not in content_type and not content.lstrip().startswith(b"<"):
                raise DangKiemApiError(
                    "HTTP 200 but response is not XML "
                    f"(Content-Type={content_type or 'unknown'}, bytes={len(content)})"
                )
    except (aiohttp.ClientError, TimeoutError) as err:
        # Avoid including the full request URL in the message/log: it contains
        # vehicle lookup data. Keep the exception class for useful diagnostics.
        detail = getattr(err, "os_error", None)
        reason = f": {detail}" if detail else ""
        raise DangKiemApiError(
            f"HTTP request failed: {type(err).__name__}{reason}"
        ) from err

    return _parse_record(content)
