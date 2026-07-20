"""
Thanoy Legal AI client
======================
Thin async client for iApp's **Thanoy** Thai-legal AI. Given a (Thai) case
summary it asks Thanoy which Thai laws the conduct may violate, and returns the
advice text for the report's "legal advice" section (part 3 of the output).

Thanoy is a SEPARATE specialist from the MITRE pipeline:
  • our pipeline explains the *technical* incident (grounded in MITRE ATT&CK)
  • Thanoy maps it to *Thai law* (พ.ร.บ.คอมพิวเตอร์ / พ.ร.บ.ไซเบอร์ / ป.อาญา …)

We deliberately do NOT teach Thai law to the MITRE model — it would hallucinate
มาตรา numbers (the same failure mode as fabricated ATT&CK IDs). Thanoy is trained
on real Thai statutes + court decisions, so we delegate to it.

Design notes:
  • OPTIONAL — if ``THANOY_API_KEY`` is unset, or the call times out / errors,
    ``get_legal_advice`` returns ``None`` and the caller omits the legal section.
    It must NEVER crash report generation.
  • The output is AI-generated and NOT authoritative → it is returned WITH a Thai
    disclaimer (``LEGAL_DISCLAIMER``) so a prosecutor / นิติกร verifies the cited
    sections before relying on them.

API (per iapp.co.th/docs/llm/thanoy-legal):
  POST {THANOY_API_URL}
  headers: {"apikey": <key>, "Content-Type": "application/json"}
  body:    {"query": "<Thai legal question>"}
  resp:    {"response": [{"text": "...", "type": ...}], "token_size": {...}, ...}
"""

from __future__ import annotations

import logging
import httpx

from app.config import settings

logger = logging.getLogger("app.thanoy")

THANOY_ENABLED = settings.thanoy_enabled
THANOY_API_KEY = settings.thanoy_api_key
THANOY_API_URL = settings.thanoy_api_url
THANOY_TIMEOUT = settings.thanoy_timeout

# Rendered after the advice. AI legal output is preliminary, not a binding opinion.
LEGAL_DISCLAIMER = (
    "หมายเหตุ: คำแนะนำทางกฎหมายข้างต้นจัดทำโดยระบบ AI (Thanoy) เพื่อเป็นข้อมูล"
    "เบื้องต้นเท่านั้น มิใช่ความเห็นทางกฎหมายที่ผูกพัน โปรดให้พนักงานอัยการหรือ"
    "นิติกรตรวจสอบตัวบทและเลขมาตราที่อ้างอิงก่อนนำไปใช้"
)

# Built from the case summary; asks Thanoy for the specific statutes + sections.
_QUERY_TEMPLATE = (
    "จากข้อเท็จจริงของเหตุการณ์ความผิดทางไซเบอร์ต่อไปนี้ โปรดระบุว่าการกระทำดังกล่าว"
    "อาจเข้าข่ายความผิดตามกฎหมายไทยฉบับใดและมาตราใดบ้าง (เช่น พ.ร.บ. ว่าด้วยการกระทำ"
    "ความผิดเกี่ยวกับคอมพิวเตอร์, พ.ร.บ. การรักษาความมั่นคงปลอดภัยไซเบอร์, ประมวล"
    "กฎหมายอาญา) พร้อมอธิบายเหตุผลโดยย่อและประเมินความเสียหายเบื้องต้น โดยอ้างอิงเลข"
    "มาตราให้ชัดเจน:\n\n{summary}"
)


def _build_query(case_summary: str) -> str:
    return _QUERY_TEMPLATE.format(summary=case_summary.strip())


def _parse_response(data) -> str:
    """Extract the advice text from Thanoy's response (shape-tolerant)."""
    if isinstance(data, dict):
        r = data.get("response", data.get("text"))
        if isinstance(r, list):
            parts = [
                str(x.get("text", "")).strip() if isinstance(x, dict) else str(x).strip()
                for x in r
            ]
            return "\n".join(p for p in parts if p).strip()
        if isinstance(r, str):
            return r.strip()
    if isinstance(data, str):
        return data.strip()
    return ""


async def get_legal_advice(case_summary: str, *, timeout: float | None = None) -> str | None:
    """Ask Thanoy which Thai laws the incident may violate.

    Returns the advice text WITH the disclaimer appended, or ``None`` if Thanoy is
    disabled (no API key), the summary is empty, or the call fails. Never raises.
    """
    if not THANOY_ENABLED or not case_summary or not case_summary.strip():
        return None

    headers = {"apikey": THANOY_API_KEY, "Content-Type": "application/json"}
    payload = {"query": _build_query(case_summary)}

    try:
        async with httpx.AsyncClient(timeout=timeout or THANOY_TIMEOUT) as client:
            resp = await client.post(THANOY_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
            advice = _parse_response(resp.json())
    except Exception as e:  # network / timeout / bad status / bad JSON
        logger.error("Thanoy legal advice unavailable, skipping section: %s", e)
        return None

    if not advice:
        logger.warning("Thanoy empty response, skipping legal section")
        return None

    return f"{advice}\n\n{LEGAL_DISCLAIMER}"
