from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import update_breakout_calls as updater


def issue_item(
    number: int,
    call_number: int,
    date: str,
    body: str = "",
) -> dict[str, object]:
    return {
        "number": number,
        "title": f"L1-zkEVM breakout #{call_number:02d}, {date}",
        "body": body,
        "html_url": f"https://github.com/ethereum/pm/issues/{number}",
    }


def parsed_issue(
    number: int,
    call_number: int,
    date: dt.date,
    body: str = "",
) -> updater.PmIssue:
    return updater.PmIssue(
        number=number,
        call_number=call_number,
        date=date,
        title=(
            f"L1-zkEVM breakout #{call_number:02d}, "
            f"{updater.format_date(date)}"
        ),
        body=body,
        html_url=f"https://github.com/ethereum/pm/issues/{number}",
    )


def forkcast_call(
    issue: int,
    call_number: int,
    date: dt.date,
) -> updater.ForkcastCall:
    number = f"{call_number:03d}"
    return updater.ForkcastCall(
        issue=issue,
        number=number,
        date=date,
        path=f"zkevm/{number}",
    )


def ready_call(
    issue: int = 1900,
    call_number: int = 1,
    date: dt.date = dt.date(2026, 2, 11),
    body: str = "",
) -> updater.ReadyCall:
    return updater.ReadyCall(
        issue=parsed_issue(issue, call_number, date, body),
        forkcast=forkcast_call(issue, call_number, date),
    )


class FakeClient:
    def __init__(
        self,
        responses: dict[str, updater.HttpResponse] | None = None,
        json_responses: dict[str, object] | None = None,
        errors: dict[str, Exception] | None = None,
    ) -> None:
        self.responses = responses or {}
        self.json_responses = json_responses or {}
        self.errors = errors or {}
        self.requested: list[str] = []

    def get(self, url: str, *, accept: str = "*/*") -> updater.HttpResponse:
        self.requested.append(url)
        if url in self.errors:
            raise self.errors[url]
        if url not in self.responses:
            raise AssertionError(f"unexpected GET {url}")
        return self.responses[url]

    def get_json(self, url: str) -> object:
        self.requested.append(url)
        if url in self.errors:
            raise self.errors[url]
        if url in self.json_responses:
            return self.json_responses[url]
        for prefix, response in self.json_responses.items():
            if prefix.endswith("*") and url.startswith(prefix[:-1]):
                return response
        raise AssertionError(f"unexpected JSON GET {url}")


class FakeChrome:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.rendered: list[str] = []
        self.rendered_marp: list[tuple[str, bytes]] = []

    def render(self, url: str, destination: Path) -> None:
        self.rendered.append(url)
        if self.error:
            raise self.error
        destination.write_bytes(b"%PDF-1.4\nfake\n")

    def render_marp(
        self,
        url: str,
        document: bytes,
        destination: Path,
    ) -> None:
        self.rendered_marp.append((url, document))
        if self.error:
            raise self.error
        destination.write_bytes(b"%PDF-1.4\nfake\n")


def response(
    data: bytes,
    url: str,
    content_type: str = "application/octet-stream",
    **headers: str,
) -> updater.HttpResponse:
    return updater.HttpResponse(
        data=data,
        final_url=url,
        headers={"content-type": content_type, **headers},
        status=200,
    )


class MetadataTests(unittest.TestCase):
    def test_parse_issue_title_accepts_abbreviated_month(self) -> None:
        parsed = updater.parse_pm_issue(
            issue_item(1900, 1, "Feb 11, 2026")
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.call_number, 1)
        self.assertEqual(parsed.date, dt.date(2026, 2, 11))

    def test_parse_issue_rejects_unrelated_search_result(self) -> None:
        self.assertIsNone(
            updater.parse_pm_issue(
                {
                    "number": 2000,
                    "title": "All Core Devs - Execution #230",
                }
            )
        )

    def test_join_calls_sorts_newest_first_and_reports_lag(self) -> None:
        first_date = dt.date(2026, 2, 11)
        second_date = dt.date(2026, 3, 11)
        third_date = dt.date(2026, 4, 8)
        issues = [
            parsed_issue(1900, 1, first_date),
            parsed_issue(1960, 2, second_date),
            parsed_issue(2005, 3, third_date),
        ]
        calls = [
            forkcast_call(1900, 1, first_date),
            forkcast_call(1960, 2, second_date),
        ]
        ready, lagging = updater.join_calls(issues, calls)
        self.assertEqual([call.number for call in ready], ["002", "001"])
        self.assertEqual([issue.number for issue in lagging], [2005])

    def test_join_calls_rejects_date_mismatch(self) -> None:
        issue = parsed_issue(1900, 1, dt.date(2026, 2, 11))
        call = forkcast_call(1900, 1, dt.date(2026, 2, 12))
        with self.assertRaisesRegex(updater.SyncError, "date mismatch"):
            updater.join_calls([issue], [call])

    def test_join_calls_rejects_duplicate_call_number(self) -> None:
        issues = [
            parsed_issue(1900, 1, dt.date(2026, 2, 11)),
            parsed_issue(1901, 1, dt.date(2026, 2, 12)),
        ]
        with self.assertRaisesRegex(updater.SyncError, "duplicate PM call"):
            updater.join_calls(issues, [])


class AgendaParsingTests(unittest.TestCase):
    HISTORICAL_SHAPES = {
        "call 1": (
            """
### Agenda
Planning doc: https://github.com/eth-act/planning/blob/main/projects.md
- Kev (introduction and overview)
  - [slides](https://github.com/user-attachments/files/1/breakout.html)
**Project 1 and 2**
- Ignacio (@jsign, Context on guest program and EEST)
  - [slides](https://docs.google.com/presentation/d/one/edit)
- George (formalization)
  - No slides: [Blog post](https://example.com/blog)
### Call Series
L1-zkEVM Breakout
""",
            2,
        ),
        "call 2": (
            """
### Agenda
- Tamago update
  - [Slides](https://github.com/example/repo/tree/master/slides)
- Project updates from all projects
  - [Project 1, 2 and 6](https://docs.google.com/presentation/d/two/edit)
  - [Project 3](https://github.com/user-attachments/files/2/deck.pdf)
### Call Series
""",
            3,
        ),
        "call 3": (
            """
### Agenda
- Update on evm-asm
- Project updates from all workstreams
- [Projects 1,2,6](https://docs.google.com/presentation/d/three/edit)
- [Project 4](https://example.com/optional-proofs/)
### Call Series
""",
            2,
        ),
        "call 4": (
            """
### Agenda (incl links to slides)
- [Update from Manu](https://docs.google.com/presentation/d/four/edit) on Prysm
- Project updates:
-- [Project 1) 2) 6)](https://docs.google.com/presentation/d/five/edit) [Ignacio]
-- [Project 3)](https://drive.google.com/file/d/six/view) [Marcin]
### Call Series
""",
            3,
        ),
        "call 5": (
            """
### Agenda
Project / work-stream updates:
- [Project 4)](https://example.com/optional-proofs/) [Francesco]
More updates:
- [Update from Ben](https://docs.google.com/presentation/d/seven/edit) on input deserialization
- Update from Peter on Blocks-in-Blobs
### Call Series
""",
            2,
        ),
        "call 6": (
            """
### Agenda
Project / work-stream updates:
- [Project 5)](https://docs.google.com/presentation/d/eight/edit) [Han]
More updates:
- [Update from Ben](https://docs.google.com/presentation/d/nine/edit)
### Call Series
""",
            2,
        ),
    }

    def test_historical_agenda_shapes(self) -> None:
        for name, (body, expected_count) in self.HISTORICAL_SHAPES.items():
            with self.subTest(name=name):
                presentations, _ = updater.extract_presentations(body)
                self.assertEqual(len(presentations), expected_count)

    def test_generic_slides_use_previous_speaker_context(self) -> None:
        body = """
### Agenda
- Kev (introduction and overview)
  - [slides](https://example.com/deck.pdf)
### Call Series
"""
        presentations, _ = updater.extract_presentations(body)
        self.assertEqual(
            presentations[0].title,
            "Kev — introduction and overview",
        )

    def test_presenter_suffix_is_moved_before_project(self) -> None:
        body = """
### Agenda
- [Project 1) 2) 6)](https://example.com/deck.pdf) [Ignacio]
### Call Series
"""
        presentations, _ = updater.extract_presentations(body)
        self.assertEqual(
            presentations[0].title,
            "Ignacio — projects 1, 2, and 6",
        )

    def test_no_slides_link_is_ignored(self) -> None:
        body = """
### Agenda
- Project 7
  - No slides: [Blog post](https://example.com/post)
### Call Series
"""
        presentations, ignored = updater.extract_presentations(body)
        self.assertEqual(presentations, [])
        self.assertEqual(ignored, ["https://example.com/post"])

    def test_override_fully_replaces_automatic_discovery(self) -> None:
        call = ready_call(
            body="""
### Agenda
- [Project 1](https://example.com/auto.pdf)
### Call Series
"""
        )
        replacement = updater.Presentation(
            title="Curated title",
            url="https://example.com/curated.pdf",
        )
        presentations, ignored = updater.presentations_for_call(
            call, {1900: [replacement]}
        )
        self.assertEqual(presentations, [replacement])
        self.assertEqual(ignored, [])

    def test_override_manifest_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overrides.json"
            path.write_text(
                json.dumps(
                    {
                        "1900": {
                            "presentations": [
                                {
                                    "title": "Restricted",
                                    "url": "https://example.com/deck",
                                    "kind": "unavailable",
                                    "reason": "access restricted",
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            overrides = updater.load_overrides(path)
        self.assertEqual(overrides[1900][0].reason, "access restricted")


class AcquisitionTests(unittest.TestCase):
    def test_google_slides_exports_pdf(self) -> None:
        source = "https://docs.google.com/presentation/d/deck-id/edit?usp=sharing"
        export = "https://docs.google.com/presentation/d/deck-id/export/pdf"
        client = FakeClient(
            responses={
                export: response(b"%PDF-1.4\nslides\n", export, "application/pdf")
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            result = updater.archive_presentation(
                updater.Presentation("Ignacio update", source),
                1,
                Path(directory),
                client,  # type: ignore[arg-type]
                FakeChrome(),  # type: ignore[arg-type]
            )
            self.assertTrue((Path(directory) / "01-ignacio-update.pdf").is_file())
        self.assertEqual(result.label, "PDF")
        self.assertEqual(client.requested, [export])

    def test_google_drive_detects_pdf_by_signature(self) -> None:
        source = "https://drive.google.com/file/d/file-id/view"
        download = "https://drive.google.com/uc?export=download&id=file-id"
        client = FakeClient(
            responses={
                download: response(
                    b"%PDF-1.7\ndrive\n",
                    download,
                    "application/octet-stream",
                )
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            result = updater.archive_presentation(
                updater.Presentation("Marcin update", source),
                2,
                Path(directory),
                client,  # type: ignore[arg-type]
                FakeChrome(),  # type: ignore[arg-type]
            )
        self.assertEqual(result.filename, "02-marcin-update.pdf")

    def test_direct_html_attachment_is_preserved(self) -> None:
        source = "https://github.com/user-attachments/files/1/breakout.html"
        client = FakeClient(
            responses={
                source: response(
                    b"<!DOCTYPE html><html></html>",
                    source,
                    "text/html",
                )
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            result = updater.archive_presentation(
                updater.Presentation("Kev overview", source),
                1,
                Path(directory),
                client,  # type: ignore[arg-type]
                FakeChrome(),  # type: ignore[arg-type]
            )
            data = (Path(directory) / "01-kev-overview.html").read_bytes()
        self.assertTrue(data.startswith(b"<!DOCTYPE html>"))
        self.assertEqual(result.label, "HTML")

    def test_github_directory_requires_one_presentation(self) -> None:
        source = "https://github.com/example/slides/tree/main/decks"
        api = "https://api.github.com/repos/example/slides/contents/decks?ref=main"
        raw = "https://raw.githubusercontent.com/example/slides/main/decks/talk.pdf"
        client = FakeClient(
            json_responses={
                api: [
                    {
                        "type": "file",
                        "name": "talk.pdf",
                        "download_url": raw,
                    },
                    {
                        "type": "file",
                        "name": "notes.md",
                        "download_url": "https://example.com/notes",
                    },
                ]
            },
            responses={
                raw: response(b"%PDF-1.4\ngithub\n", raw, "application/pdf")
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            result = updater.archive_presentation(
                updater.Presentation("TamaGo", source),
                1,
                Path(directory),
                client,  # type: ignore[arg-type]
                FakeChrome(),  # type: ignore[arg-type]
            )
        self.assertEqual(result.filename, "01-tamago.pdf")

    def test_ambiguous_github_directory_is_recorded_unavailable(self) -> None:
        source = "https://github.com/example/slides/tree/main/decks"
        api = "https://api.github.com/repos/example/slides/contents/decks?ref=main"
        client = FakeClient(
            json_responses={
                api: [
                    {
                        "type": "file",
                        "name": "one.pdf",
                        "download_url": "https://example.com/one.pdf",
                    },
                    {
                        "type": "file",
                        "name": "two.pdf",
                        "download_url": "https://example.com/two.pdf",
                    },
                ]
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            result = updater.archive_presentation(
                updater.Presentation("Ambiguous", source),
                1,
                Path(directory),
                client,  # type: ignore[arg-type]
                FakeChrome(),  # type: ignore[arg-type]
            )
        self.assertIn("contains 2 presentation files", result.unavailable_reason or "")

    def test_web_deck_is_preflighted_and_rendered(self) -> None:
        source = "https://slides.example.com/deck/"
        client = FakeClient(
            responses={
                source: response(b"<html>deck</html>", source, "text/html")
            }
        )
        chrome = FakeChrome()
        with tempfile.TemporaryDirectory() as directory:
            result = updater.archive_presentation(
                updater.Presentation("Web deck", source),
                3,
                Path(directory),
                client,  # type: ignore[arg-type]
                chrome,  # type: ignore[arg-type]
            )
        self.assertEqual(chrome.rendered, [source])
        self.assertEqual(result.filename, "03-web-deck.pdf")

    def test_marp_deck_uses_overlay_safe_renderer(self) -> None:
        source = "https://slides.example.com/deck/"
        document = b"<html><head></head><body>deck</body></html>"
        client = FakeClient(
            responses={source: response(document, source, "text/html")}
        )
        chrome = FakeChrome()
        with tempfile.TemporaryDirectory() as directory:
            result = updater.archive_presentation(
                updater.Presentation(
                    "Marp deck",
                    source,
                    kind="marp-web-pdf",
                ),
                3,
                Path(directory),
                client,  # type: ignore[arg-type]
                chrome,  # type: ignore[arg-type]
            )
        self.assertEqual(chrome.rendered, [])
        self.assertEqual(chrome.rendered_marp, [(source, document)])
        self.assertEqual(result.filename, "03-marp-deck.pdf")

    def test_permanent_failure_is_recorded_unavailable(self) -> None:
        source = "https://example.com/restricted.pdf"
        client = FakeClient(
            errors={
                source: updater.PermanentArchiveError("HTTP 403 fetching source")
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            result = updater.archive_presentation(
                updater.Presentation("Restricted", source),
                1,
                Path(directory),
                client,  # type: ignore[arg-type]
                FakeChrome(),  # type: ignore[arg-type]
            )
        self.assertEqual(result.unavailable_reason, "HTTP 403 fetching source")

    def test_transient_failure_aborts(self) -> None:
        source = "https://example.com/deck.pdf"
        client = FakeClient(
            errors={
                source: updater.TransientArchiveError("temporary HTTP 503")
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(updater.TransientArchiveError):
                updater.archive_presentation(
                    updater.Presentation("Retry later", source),
                    1,
                    Path(directory),
                    client,  # type: ignore[arg-type]
                    FakeChrome(),  # type: ignore[arg-type]
                )

    def test_malformed_pdf_is_recorded_unavailable(self) -> None:
        source = "https://example.com/deck.pdf"
        client = FakeClient(
            responses={
                source: response(b"<html>login</html>", source, "text/html")
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            result = updater.archive_presentation(
                updater.Presentation(
                    "Deck",
                    source,
                    filename="01-deck.pdf",
                    kind="download",
                ),
                1,
                Path(directory),
                client,  # type: ignore[arg-type]
                FakeChrome(),  # type: ignore[arg-type]
            )
        self.assertIn("filename extension", result.unavailable_reason or "")


class MarkdownTests(unittest.TestCase):
    def test_progress_section_generation_and_replacement(self) -> None:
        calls = [
            ready_call(1960, 2, dt.date(2026, 3, 11)),
            ready_call(1900, 1, dt.date(2026, 2, 11)),
        ]
        section = updater.render_progress_section(calls, {"001"})
        self.assertIn("https://forkcast.org/calls/zkevm/002", section)
        self.assertNotIn("breakout-calls/002/", section)
        self.assertIn("breakout-calls/001/", section)

        original = (
            "# Before\n\n"
            f"{updater.PROGRESS_HEADING}\n\nold\n\n"
            f"{updater.PROGRESS_END_HEADING}\n\nafter\n"
        )
        updated = updater.replace_heading_section(
            original,
            updater.PROGRESS_HEADING,
            updater.PROGRESS_END_HEADING,
            section,
        )
        self.assertTrue(updated.startswith("# Before\n\n"))
        self.assertTrue(updated.endswith("## Further reading\n\nafter\n"))

    def test_replace_table_preserves_surrounding_content(self) -> None:
        original = (
            "intro\n\n"
            "| Call | Date | Slides |\n"
            "| ---: | --- | --- |\n"
            "| 1 | old | old |\n"
            "\nfooter\n"
        )
        table = (
            "| Call | Date | Slides |\n"
            "| ---: | --- | --- |\n"
            "| 2 | new | new |"
        )
        updated = updater.replace_table(
            original, "| Call | Date | Slides |", table
        )
        self.assertEqual(
            updated,
            "intro\n\n"
            "| Call | Date | Slides |\n"
            "| ---: | --- | --- |\n"
            "| 2 | new | new |\n"
            "\nfooter\n",
        )

    def test_rendered_call_readme_records_unavailable_source(self) -> None:
        presentation = updater.Presentation(
            "Restricted", "https://example.com/deck"
        )
        archived = updater.ArchivedPresentation(
            presentation=presentation,
            filename=None,
            label=None,
            unavailable_reason="access restricted",
        )
        readme = updater.render_call_readme(ready_call(), [archived])
        self.assertIn("Unavailable (access restricted)", readme)
        self.assertIn("[Source](https://example.com/deck)", readme)

    def test_breakout_index_is_idempotent_without_new_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            call_dir = root / "001"
            call_dir.mkdir()
            (call_dir / "README.md").write_text(
                "# Call\n\nFebruary 11, 2026 · links\n", encoding="utf-8"
            )
            original = (
                "# Slides\n\n"
                "The snapshots were retrieved on July 16, 2026.\n\n"
                "| Call | Date | Slides |\n"
                "| ---: | --- | --- |\n"
                "| 1 | February 11, 2026 | [Call #1](001/) |\n"
            )
            updated = updater.render_breakout_index(
                original,
                root,
                [ready_call()],
                {"001"},
                retrieval_date=None,
            )
        self.assertEqual(updated, original)


class SyncIntegrationTests(unittest.TestCase):
    def make_repo(self, root: Path) -> None:
        (root / "scripts").mkdir()
        (root / "scripts" / "breakout-call-overrides.json").write_text(
            "{}\n", encoding="utf-8"
        )
        (root / "breakout-calls").mkdir()
        (root / "breakout-calls" / "README.md").write_text(
            "# zkEVM breakout call slides\n\n"
            "The snapshots were retrieved on July 16, 2026.\n\n"
            "| Call | Date | Slides |\n"
            "| ---: | --- | --- |\n",
            encoding="utf-8",
        )
        (root / "PROGRESS.md").write_text(
            "# Progress\n\n"
            f"{updater.PROGRESS_HEADING}\n\n"
            "| Call | Date | Resources |\n"
            "| ---: | --- | --- |\n\n"
            f"{updater.PROGRESS_END_HEADING}\n\nText\n",
            encoding="utf-8",
        )

    def metadata_client(
        self,
        issues: list[dict[str, object]],
        calls: list[dict[str, object]],
        *,
        responses: dict[str, updater.HttpResponse] | None = None,
        errors: dict[str, Exception] | None = None,
    ) -> FakeClient:
        return FakeClient(
            responses=responses,
            errors=errors,
            json_responses={
                f"{updater.PM_SEARCH_API}*": {"items": issues},
                updater.FORKCAST_CALLS_URL: calls,
            },
        )

    def test_default_sync_archives_and_then_check_passes(self) -> None:
        body = """
### Agenda
- [Project 1](https://example.com/deck.pdf)
### Call Series
"""
        issues = [issue_item(1900, 1, "February 11, 2026", body)]
        calls = [
            {
                "type": "zkevm",
                "issue": 1900,
                "number": "001",
                "date": "2026-02-11",
                "path": "zkevm/001",
            }
        ]
        source = "https://example.com/deck.pdf"
        client = self.metadata_client(
            issues,
            calls,
            responses={
                source: response(b"%PDF-1.4\nslide\n", source, "application/pdf")
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            result = updater.synchronize(
                root,
                check=False,
                chrome_binary=None,
                client=client,  # type: ignore[arg-type]
                today=dt.date(2026, 7, 27),
            )
            self.assertEqual(result, 0)
            self.assertTrue(
                (root / "breakout-calls" / "001" / "01-project-1.pdf").is_file()
            )
            self.assertIn(
                "The snapshots were retrieved on July 27, 2026.",
                (root / "breakout-calls" / "README.md").read_text(),
            )
            check_client = self.metadata_client(issues, calls)
            check_result = updater.synchronize(
                root,
                check=True,
                chrome_binary=None,
                client=check_client,  # type: ignore[arg-type]
                today=dt.date(2026, 7, 28),
            )
            self.assertEqual(check_result, 0)

    def test_check_reports_missing_archive_without_writing(self) -> None:
        issues = [issue_item(1900, 1, "February 11, 2026")]
        calls = [
            {
                "type": "zkevm",
                "issue": 1900,
                "number": "001",
                "date": "2026-02-11",
                "path": "zkevm/001",
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            before = (root / "PROGRESS.md").read_bytes()
            result = updater.synchronize(
                root,
                check=True,
                chrome_binary=None,
                client=self.metadata_client(issues, calls),  # type: ignore[arg-type]
            )
            self.assertEqual(result, 1)
            self.assertEqual((root / "PROGRESS.md").read_bytes(), before)
            self.assertFalse((root / "breakout-calls" / "001").exists())

    def test_transient_archive_failure_leaves_repo_unchanged(self) -> None:
        source = "https://example.com/deck.pdf"
        body = f"""
### Agenda
- [Project 1]({source})
### Call Series
"""
        issues = [issue_item(1900, 1, "February 11, 2026", body)]
        calls = [
            {
                "type": "zkevm",
                "issue": 1900,
                "number": "001",
                "date": "2026-02-11",
                "path": "zkevm/001",
            }
        ]
        client = self.metadata_client(
            issues,
            calls,
            errors={source: updater.TransientArchiveError("temporary HTTP 503")},
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            progress_before = (root / "PROGRESS.md").read_bytes()
            index_before = (root / "breakout-calls" / "README.md").read_bytes()
            with self.assertRaises(updater.TransientArchiveError):
                updater.synchronize(
                    root,
                    check=False,
                    chrome_binary=None,
                    client=client,  # type: ignore[arg-type]
                )
            self.assertEqual((root / "PROGRESS.md").read_bytes(), progress_before)
            self.assertEqual(
                (root / "breakout-calls" / "README.md").read_bytes(),
                index_before,
            )
            self.assertFalse((root / "breakout-calls" / "001").exists())
            self.assertEqual(
                list((root / "breakout-calls").glob(".breakout-stage-*")),
                [],
            )

    def test_existing_call_directory_is_not_rewritten(self) -> None:
        issues = [issue_item(1900, 1, "February 11, 2026")]
        calls = [
            {
                "type": "zkevm",
                "issue": 1900,
                "number": "001",
                "date": "2026-02-11",
                "path": "zkevm/001",
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            call_dir = root / "breakout-calls" / "001"
            call_dir.mkdir()
            readme = call_dir / "README.md"
            readme.write_text(
                "# Hand-curated\n\nFebruary 11, 2026 · links\n",
                encoding="utf-8",
            )
            before = readme.read_bytes()
            updater.synchronize(
                root,
                check=False,
                chrome_binary=None,
                client=self.metadata_client(issues, calls),  # type: ignore[arg-type]
                today=dt.date(2026, 7, 27),
            )
            self.assertEqual(readme.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
