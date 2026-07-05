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
        return {"published": [], "revenue": [], "metrics": []}

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

    # -- performance metrics -------------------------------------------------

    def record_metrics(
        self,
        channel: str,
        views: int = 0,
        retention_pct: float = 0.0,
        ctr_pct: float = 0.0,
        note: str = "",
    ) -> str:
        """Log a post's performance (views / avg retention / link CTR) so
        future content can be steered by what actually worked."""
        entry_id = uuid.uuid4().hex[:12]
        self._state.setdefault("metrics", []).append(
            {
                "id": entry_id,
                "timestamp": datetime.now().isoformat(),
                "channel": channel,
                "views": int(views),
                "retention_pct": float(retention_pct),
                "ctr_pct": float(ctr_pct),
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

    def review(self, days: int = 7) -> str:
        """Markdown performance review of the last N days — the input to
        next week's content decisions."""
        from datetime import timedelta

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        pub = [
            p
            for p in self._state["published"]
            if p["timestamp"] >= cutoff and not p.get("dry_run")
        ]
        rev = [r for r in self._state["revenue"] if r["timestamp"] >= cutoff]
        met = [m for m in self._state.get("metrics", []) if m["timestamp"] >= cutoff]

        lines = [f"# Performance review — last {days} days", ""]
        lines.append(f"- Posts published: **{len(pub)}** "
                     f"({', '.join(f'{k}: {v}' for k, v in _count(pub, 'channel').items()) or 'none'})")
        lines.append(f"- Revenue: **${sum(r['amount'] for r in rev):,.2f}** "
                     f"({', '.join(f'{k}: ${v:,.2f}' for k, v in _sum_by(rev, 'source', 'amount').items()) or 'none logged'})")
        if met:
            best = max(met, key=lambda m: m["views"])
            lines.append(
                f"- Views: **{sum(m['views'] for m in met):,}** across "
                f"{len(met)} tracked posts; avg retention "
                f"{sum(m['retention_pct'] for m in met) / len(met):.1f}%, "
                f"avg CTR {sum(m['ctr_pct'] for m in met) / len(met):.2f}%"
            )
            lines.append(
                f"- Top post: {best['channel']} — {best['views']:,} views"
                + (f" ({best['note']})" if best.get("note") else "")
            )
        else:
            lines.append("- No metrics logged — run "
                         "`run_content_pipeline.py metrics` after checking analytics")
        lines += [
            "",
            "## Next iteration",
            "- Double down on the top channel/format above",
            "- Rewrite the weakest hook style; test one new hook pattern",
            "- If retention < 45%: tighten scene 1-2 of the short script",
            "- If CTR < 2%: strengthen the CTA and bio-link offer",
        ]
        return "\n".join(lines)

    def stats(self) -> dict:
        pub = self._state["published"]
        real = [p for p in pub if not p.get("dry_run")]
        metrics = self._state.get("metrics", [])
        return {
            "total_published": len(real),
            "total_runs": len(pub),
            "by_channel": _count(real, "channel"),
            "by_type": _count(real, "content_type"),
            "total_revenue": self.total_revenue(),
            "revenue_by_source": self.revenue_by_source(),
            "total_views": sum(m["views"] for m in metrics),
            "avg_retention_pct": round(
                sum(m["retention_pct"] for m in metrics) / len(metrics), 1
            )
            if metrics
            else 0,
            "metrics_logged": len(metrics),
        }


def _count(items: List[dict], key: str) -> dict:
    out: dict = {}
    for it in items:
        out[it[key]] = out.get(it[key], 0) + 1
    return out


def _sum_by(items: List[dict], key: str, value_key: str) -> dict:
    out: dict = {}
    for it in items:
        out[it[key]] = round(out.get(it[key], 0) + it[value_key], 2)
    return out
