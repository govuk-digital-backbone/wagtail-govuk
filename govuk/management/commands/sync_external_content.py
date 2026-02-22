from django.core.management.base import BaseCommand, CommandError

from govuk.content_discovery import ContentDiscoveryError, sync_content_discovery_source
from govuk.models import ContentDiscoverySource


class Command(BaseCommand):
    help = (
        "Fetch configured content discovery sources and upsert external content items "
        "(Atom and RSS XML feeds)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-id",
            action="append",
            type=int,
            dest="source_ids",
            help="Limit sync to one or more source IDs.",
        )
        parser.add_argument(
            "--site-id",
            type=int,
            help="Limit sync to sources on a specific Wagtail site ID.",
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=15.0,
            help="HTTP timeout in seconds when fetching each source (default: 15).",
        )

    def handle(self, *args, **options):
        sources = ContentDiscoverySource.objects.select_related("settings__site").order_by(
            "id"
        )
        source_ids = options.get("source_ids") or []
        if source_ids:
            sources = sources.filter(id__in=source_ids)
        if options.get("site_id"):
            sources = sources.filter(settings__site_id=options["site_id"])

        source_list = list(sources)
        if not source_list:
            raise CommandError("No content discovery sources matched the provided filters.")

        timeout = options["timeout"]
        totals = {"entries": 0, "created": 0, "updated": 0, "skipped": 0}
        failures: list[str] = []

        for source in source_list:
            source_label = source.name or source.url
            self.stdout.write(f"Syncing source {source.id}: {source_label}")
            try:
                result = sync_content_discovery_source(source, timeout=timeout)
            except ContentDiscoveryError as exc:
                failures.append(f"{source.id} ({source_label}): {exc}")
                self.stderr.write(
                    self.style.ERROR(f"  Failed source {source.id}: {exc}")
                )
                continue

            totals["entries"] += result.total_entries
            totals["created"] += result.created
            totals["updated"] += result.updated
            totals["skipped"] += result.skipped
            self.stdout.write(
                self.style.SUCCESS(
                    "  "
                    + (
                        f"Processed {result.total_entries}, created {result.created}, "
                        f"updated {result.updated}, skipped {result.skipped}"
                    )
                )
            )

        summary = (
            f"Completed {len(source_list) - len(failures)} of {len(source_list)} sources. "
            f"Processed {totals['entries']} entries, created {totals['created']}, "
            f"updated {totals['updated']}, skipped {totals['skipped']}."
        )
        if failures:
            self.stderr.write(self.style.ERROR(summary))
            for failure in failures:
                self.stderr.write(self.style.ERROR(f"  {failure}"))
            raise CommandError(f"{len(failures)} source(s) failed during sync.")

        self.stdout.write(self.style.SUCCESS(summary))
