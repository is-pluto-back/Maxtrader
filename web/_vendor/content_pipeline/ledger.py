"""Append-only ledger of everything the pipeline publishes, plus a simple
revenue log. Stored as JSON so the dashboard (or a spreadsheet) can read it.

Revenue entries are added manually or by webhooks later (newsletter
platform payouts, affiliate reports, sponsor invoices) via
``record_revenue`` / the CLI's ``revenue`` subcommand.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional


class ContentLedger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except json.JSONDecodeError:
                pass
        return {"published": [], "revenue": []}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._state, indent=2, default=str))

    # -- publishing record -------------------------------------------------

    def record_publish(
        self,
        content_type: str,
        title: str,
        provider: str,
        channel: str,
        status: str,
        detail: str = "",
        dry_run: bool = False,
    ) -> str:
        entry_id = uuid.uuid4().hex[:12]
        self._state["published"].append(
            {
                "id": entry_id,
                "timestamp": datetime.now().isoformat(),
                "content_type": content_type,
                "title": title,
                "provider": provider,
                "channel": channel,
                "status": status,
                "detail": detail,
                "dry_run": dry_run,
            }
        )
        self._save()
        return entry_id

    # -- revenue record ----------------------------------------------------

    def record_revenue(
        self,
        amount: float,
        source: str,
        note: str = "",
        currency: str = "USD",
    ) -> str:
        entry_id = uuid.uuid4().hex[:12]
        self._state["revenue"].append(
            {
                "id": entry_id,
                "timestamp": datetime.now().isoformat(),
                "amount": round(float(amount), 2),
                "currency": currency,
                "source": source,  # e.g. 'newsletter', 'affiliate', 'sponsor'
                "note": note,
            }
        )
        self._save()
        return entry_id

    # -- reporting -----------------------------------------------------------

    def published(self, limit: Optional[int] = None) -> List[dict]:
        items = self._state["published"]
        return items[-limit:] if limit else items

    def total_revenue(self) -> float:
        return round(sum(r["amount"] for r in self._state["revenue"]), 2)

    def revenue_by_source(self) -> dict:
        out: dict = {}
        for r in self._state["revenue"]:
            out[r["source"]] = round(out.get(r["source"], 0) + r["amount"], 2)
        return out

    def stats(self) -> dict:
        pub = self._state["published"]
        real = [p for p in pub if not p.get("dry_run")]
        return {
            "total_published": len(real),
            "total_runs": len(pub),
            "by_channel": _count(real, "channel"),
            "by_type": _count(real, "content_type"),
            "total_revenue": self.total_revenue(),
            "revenue_by_source": self.revenue_by_source(),
        }


def _count(items: List[dict], key: str) -> dict:
    out: dict = {}
    for it in items:
        out[it[key]] = out.get(it[key], 0) + 1
    return out
