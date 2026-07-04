"""Pipeline orchestrator: snapshot -> generate -> monetize -> publish -> ledger."""

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from .config import PipelineConfig, load_pipeline_config
from .generator import CONTENT_TYPES, GeneratedContent, generate
from .ledger import ContentLedger
from .monetizer import monetize
from .publishers import PUBLISHERS, PublishResult
from .snapshot import MarketSnapshot, build_snapshot

log = logging.getLogger("content-pipeline")


@dataclass
class RunReport:
    snapshot: MarketSnapshot = None
    generated: List[GeneratedContent] = field(default_factory=list)
    results: Dict[str, List[PublishResult]] = field(default_factory=dict)
    preview_files: List[Path] = field(default_factory=list)

    def summary(self) -> str:
        lines = []
        if self.snapshot and self.snapshot.demo_mode:
            lines.append("⚠ Ran on DEMO data (no live feeds connected).")
        for c in self.generated:
            results = self.results.get(c.content_type, [])
            ok = [r.channel for r in results if r.ok]
            failed = [f"{r.channel} ({r.detail})" for r in results if not r.ok]
            line = f"{c.content_type} [{c.provider}]"
            if ok:
                line += f" → published: {', '.join(ok)}"
            if failed:
                line += f" → FAILED: {'; '.join(failed)}"
            if not results:
                line += " → generated only (dry run / no channels configured)"
            lines.append(line)
        if self.preview_files:
            lines.append(f"Previews saved to: {self.preview_files[0].parent}")
        return "\n".join(lines)


class ContentPipeline:
    def __init__(self, cfg: Optional[PipelineConfig] = None):
        self.cfg = cfg or load_pipeline_config()
        self.ledger = ContentLedger(self.cfg.ledger_path)

    def _due_content_types(self) -> List[str]:
        """Daily brief + social every run; newsletter only on its weekday."""
        types = ["daily_brief", "social_thread"]
        if date.today().weekday() == self.cfg.newsletter_weekday:
            types.append("newsletter")
        return types

    def _channels_for(self, content_type: str) -> List[str]:
        return getattr(self.cfg.channels, content_type, [])

    def _save_preview(self, content: GeneratedContent) -> Path:
        self.cfg.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.cfg.output_dir / f"{date.today().isoformat()}-{content.content_type}.md"
        path.write_text(f"<!-- provider: {content.provider} -->\n\n{content.body}\n")
        return path

    def run(
        self,
        content_types: Optional[List[str]] = None,
        dry_run: bool = False,
        offline: bool = False,
        force_provider: Optional[str] = None,
    ) -> RunReport:
        report = RunReport()
        report.snapshot = build_snapshot(offline=offline)
        log.info(
            "Snapshot ready: "
            + (report.snapshot.summary_lines()[1] if report.snapshot.demo_mode else report.snapshot.as_of)
        )

        types = content_types or self._due_content_types()
        for ct in types:
            if ct not in CONTENT_TYPES:
                log.warning(f"Skipping unknown content type '{ct}'")
                continue

            content = generate(ct, self.cfg, report.snapshot, force_provider)
            content = monetize(content, self.cfg.monetization)
            report.generated.append(content)
            report.preview_files.append(self._save_preview(content))

            results: List[PublishResult] = []
            for channel in self._channels_for(ct):
                publisher_cls = PUBLISHERS.get(channel)
                if not publisher_cls:
                    log.warning(f"Unknown channel '{channel}' for {ct}")
                    continue
                publisher = publisher_cls(self.cfg)
                if not publisher.is_configured():
                    log.info(f"  {channel}: not configured, skipping")
                    continue
                if dry_run:
                    log.info(f"  {channel}: [DRY RUN] would publish '{content.title}'")
                    self.ledger.record_publish(
                        ct, content.title, content.provider, channel, "dry_run", dry_run=True
                    )
                    results.append(PublishResult(channel, True, "dry_run"))
                    continue

                result = publisher.publish(content)
                results.append(result)
                self.ledger.record_publish(
                    ct,
                    content.title,
                    content.provider,
                    channel,
                    "ok" if result.ok else "failed",
                    detail=result.detail,
                )
                log.info(
                    f"  {channel}: {'✓ ' + result.detail if result.ok else '✗ ' + result.detail}"
                )

            report.results[ct] = results

        return report
