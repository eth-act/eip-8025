#!/usr/bin/env python3
"""Synchronize zkEVM breakout-call archives and Markdown indexes."""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Sequence


PM_SEARCH_API = "https://api.github.com/search/issues"
FORKCAST_CALLS_URL = (
    "https://raw.githubusercontent.com/ethereum/forkcast/"
    "main/src/data/protocol-calls.generated.json"
)
FORKCAST_BASE_URL = "https://forkcast.org/calls"
PM_ISSUE_BASE_URL = "https://github.com/ethereum/pm/issues"
PROGRESS_HEADING = "## Coordination: zkEVM breakout calls"
PROGRESS_END_HEADING = "## Further reading"
ISSUE_TITLE_RE = re.compile(
    r"^L1-zkEVM breakout #(?P<number>\d+),\s*(?P<date>.+?)\s*$",
    re.IGNORECASE,
)
MARKDOWN_LINK_RE = re.compile(
    r"\[([^\]]+)\]\((https://[^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)"
)
AGENDA_HEADING_RE = re.compile(r"^#{2,4}\s+Agenda\b", re.IGNORECASE)
CALL_SERIES_HEADING_RE = re.compile(
    r"^#{2,4}\s+Call Series\b", re.IGNORECASE
)
PRESENTATION_CONTEXT_RE = re.compile(
    r"\b(slides?|presentations?|projects?|work[\s-]?streams?|updates?)\b",
    re.IGNORECASE,
)
SUPPORTED_DIRECT_EXTENSIONS = {".pdf", ".html", ".htm", ".ppt", ".pptx"}
SUPPORTED_KINDS = {
    "auto",
    "download",
    "github-directory",
    "google-drive",
    "google-slides",
    "marp-web-pdf",
    "unavailable",
    "web-pdf",
}
CHROME_CANDIDATES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
)


class SyncError(RuntimeError):
    """A configuration or upstream-data error."""


class TransientArchiveError(SyncError):
    """A retryable network or browser failure."""


class PermanentArchiveError(SyncError):
    """A presentation that cannot be archived automatically."""


@dataclasses.dataclass(frozen=True)
class HttpResponse:
    data: bytes
    final_url: str
    headers: Mapping[str, str]
    status: int


@dataclasses.dataclass(frozen=True)
class PmIssue:
    number: int
    call_number: int
    date: dt.date
    title: str
    body: str
    html_url: str


@dataclasses.dataclass(frozen=True)
class ForkcastCall:
    issue: int
    number: str
    date: dt.date
    path: str


@dataclasses.dataclass(frozen=True)
class ReadyCall:
    issue: PmIssue
    forkcast: ForkcastCall

    @property
    def number(self) -> str:
        return self.forkcast.number

    @property
    def date(self) -> dt.date:
        return self.forkcast.date

    @property
    def forkcast_url(self) -> str:
        return f"{FORKCAST_BASE_URL}/{self.forkcast.path}"


@dataclasses.dataclass(frozen=True)
class Presentation:
    title: str
    url: str
    filename: str | None = None
    kind: str = "auto"
    reason: str | None = None


@dataclasses.dataclass(frozen=True)
class ArchivedPresentation:
    presentation: Presentation
    filename: str | None
    label: str | None
    unavailable_reason: str | None


class HttpClient:
    """Small authenticated HTTP client built on urllib."""

    def __init__(self, token: str | None = None, timeout: int = 60) -> None:
        self.token = token
        self.timeout = timeout

    def get(
        self,
        url: str,
        *,
        accept: str = "*/*",
    ) -> HttpResponse:
        validate_https_url(url)
        headers = {
            "Accept": accept,
            "User-Agent": "eip-8025-breakout-call-updater/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            headers["X-GitHub-Api-Version"] = "2022-11-28"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                final_url = response.geturl()
                validate_https_url(final_url)
                return HttpResponse(
                    data=response.read(),
                    final_url=final_url,
                    headers={key.lower(): value for key, value in response.headers.items()},
                    status=response.status,
                )
        except urllib.error.HTTPError as exc:
            rate_limited = (
                exc.code == 403
                and exc.headers.get("x-ratelimit-remaining") == "0"
            )
            if rate_limited or exc.code in {408, 425, 429} or 500 <= exc.code <= 599:
                raise TransientArchiveError(
                    f"temporary HTTP {exc.code} fetching {url}"
                ) from exc
            raise PermanentArchiveError(
                f"HTTP {exc.code} fetching {url}"
            ) from exc
        except (TimeoutError, urllib.error.URLError) as exc:
            raise TransientArchiveError(f"network error fetching {url}: {exc}") from exc

    def get_json(self, url: str) -> Any:
        response = self.get(url, accept="application/vnd.github+json")
        try:
            return json.loads(response.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SyncError(f"invalid JSON from {url}") from exc


class ChromeRenderer:
    """Render web-native slide decks with sandboxed headless Chrome."""

    def __init__(
        self,
        binary: str | None = None,
        *,
        timeout: int = 120,
    ) -> None:
        self.binary = binary
        self.timeout = timeout

    def resolve_binary(self) -> str:
        if self.binary:
            resolved = shutil.which(self.binary) if os.sep not in self.binary else self.binary
            if resolved and Path(resolved).is_file():
                return str(resolved)
            raise SyncError(f"Chrome binary not found: {self.binary}")
        for candidate in CHROME_CANDIDATES:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        raise SyncError(
            "a Chrome/Chromium binary is required to archive web-native slides; "
            "pass --chrome-binary PATH"
        )

    def _render_target(
        self,
        target: str,
        destination: Path,
        *,
        extra_args: Sequence[str] = (),
    ) -> None:
        binary = self.resolve_binary()
        with tempfile.TemporaryDirectory(prefix="breakout-chrome-") as profile:
            command = [
                binary,
                "--headless=new",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--run-all-compositor-stages-before-draw",
                "--virtual-time-budget=10000",
                f"--user-data-dir={profile}",
                f"--print-to-pdf={destination}",
                "--no-pdf-header-footer",
                *extra_args,
                target,
            ]
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=self.timeout,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise TransientArchiveError(
                    f"Chrome failed while rendering {target}: {exc}"
                ) from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip().splitlines()
            suffix = f": {detail[-1]}" if detail else ""
            raise TransientArchiveError(
                f"Chrome exited {completed.returncode} while rendering {target}{suffix}"
            )
        validate_file(destination, ".pdf")

    def render(self, url: str, destination: Path) -> None:
        validate_https_url(url)
        self._render_target(url, destination)

    def render_marp(
        self,
        url: str,
        document: bytes,
        destination: Path,
    ) -> None:
        """Render Marp HTML without repeating its animated lead background."""
        validate_https_url(url)
        try:
            source = document.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PermanentArchiveError("Marp deck is not UTF-8 HTML") from exc
        head = re.search(r"<head(?:\s[^>]*)?>", source, re.IGNORECASE)
        if head is None:
            raise PermanentArchiveError("Marp deck does not contain an HTML head")
        injection = f"""
<base href="{html.escape(url, quote=True)}">
<style>
@media print {{
  body > div[style*="position: fixed"][style*="z-index: 0"] {{
    display: none !important;
  }}
  section.lead {{
    background: var(--heading, #062873) !important;
  }}
}}
</style>
"""
        printable = source[: head.end()] + injection + source[head.end() :]
        with tempfile.TemporaryDirectory(prefix="breakout-marp-") as directory:
            source_path = Path(directory) / "deck.html"
            source_path.write_text(printable, encoding="utf-8")
            self._render_target(
                source_path.as_uri(),
                destination,
                extra_args=("--allow-file-access-from-files",),
            )


def validate_https_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SyncError(f"only absolute HTTPS URLs are supported: {url}")
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        raise SyncError(f"local URLs are not supported: {url}")


def parse_issue_date(value: str) -> dt.date:
    for date_format in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return dt.datetime.strptime(value.strip(), date_format).date()
        except ValueError:
            continue
    raise SyncError(f"unrecognized call date in issue title: {value}")


def parse_pm_issue(item: Mapping[str, Any]) -> PmIssue | None:
    title = str(item.get("title", ""))
    match = ISSUE_TITLE_RE.fullmatch(title)
    if not match:
        return None
    number = require_int(item, "number", "PM issue")
    call_number = int(match.group("number"))
    html_url = str(item.get("html_url") or f"{PM_ISSUE_BASE_URL}/{number}")
    validate_https_url(html_url)
    return PmIssue(
        number=number,
        call_number=call_number,
        date=parse_issue_date(match.group("date")),
        title=title,
        body=str(item.get("body") or ""),
        html_url=html_url,
    )


def fetch_pm_issues(client: HttpClient) -> list[PmIssue]:
    query = 'repo:ethereum/pm is:issue is:closed in:title "L1-zkEVM breakout"'
    issues: list[PmIssue] = []
    page = 1
    while True:
        params = urllib.parse.urlencode(
            {
                "q": query,
                "sort": "created",
                "order": "desc",
                "per_page": 100,
                "page": page,
            }
        )
        payload = client.get_json(f"{PM_SEARCH_API}?{params}")
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise SyncError("GitHub issue search returned an unexpected payload")
        items = payload["items"]
        for item in items:
            if not isinstance(item, dict):
                raise SyncError("GitHub issue search returned a non-object item")
            parsed = parse_pm_issue(item)
            if parsed:
                issues.append(parsed)
        if len(items) < 100:
            break
        page += 1
        if page > 10:
            raise SyncError("GitHub issue search exceeded its 1,000-result limit")
    return issues


def fetch_forkcast_calls(client: HttpClient) -> list[ForkcastCall]:
    payload = client.get_json(FORKCAST_CALLS_URL)
    if not isinstance(payload, list):
        raise SyncError("Forkcast call data must be a JSON array")
    calls: list[ForkcastCall] = []
    for item in payload:
        if not isinstance(item, dict) or item.get("type") != "zkevm":
            continue
        issue = require_int(item, "issue", "Forkcast call")
        number = str(item.get("number") or "")
        path = str(item.get("path") or "")
        if not re.fullmatch(r"\d{3,}", number):
            raise SyncError(f"invalid Forkcast call number for issue {issue}: {number}")
        if path != f"zkevm/{number}":
            raise SyncError(f"invalid Forkcast path for issue {issue}: {path}")
        try:
            call_date = dt.date.fromisoformat(str(item.get("date")))
        except ValueError as exc:
            raise SyncError(f"invalid Forkcast date for issue {issue}") from exc
        calls.append(
            ForkcastCall(issue=issue, number=number, date=call_date, path=path)
        )
    return calls


def require_int(item: Mapping[str, Any], key: str, context: str) -> int:
    value = item.get(key)
    if isinstance(value, bool):
        raise SyncError(f"{context} has invalid {key}: {value}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise SyncError(f"{context} has invalid {key}: {value}") from exc


def join_calls(
    issues: Sequence[PmIssue],
    forkcast_calls: Sequence[ForkcastCall],
) -> tuple[list[ReadyCall], list[PmIssue]]:
    issue_by_id: dict[int, PmIssue] = {}
    issue_by_call: dict[int, PmIssue] = {}
    for issue in issues:
        if issue.number in issue_by_id:
            raise SyncError(f"duplicate PM issue number: {issue.number}")
        if issue.call_number in issue_by_call:
            previous = issue_by_call[issue.call_number]
            raise SyncError(
                f"duplicate PM call #{issue.call_number}: "
                f"issues {previous.number} and {issue.number}"
            )
        issue_by_id[issue.number] = issue
        issue_by_call[issue.call_number] = issue

    forkcast_by_issue: dict[int, ForkcastCall] = {}
    forkcast_by_number: dict[str, ForkcastCall] = {}
    for call in forkcast_calls:
        if call.issue in forkcast_by_issue:
            raise SyncError(f"duplicate Forkcast issue number: {call.issue}")
        if call.number in forkcast_by_number:
            previous = forkcast_by_number[call.number]
            raise SyncError(
                f"duplicate Forkcast call #{call.number}: "
                f"issues {previous.issue} and {call.issue}"
            )
        forkcast_by_issue[call.issue] = call
        forkcast_by_number[call.number] = call

    ready: list[ReadyCall] = []
    lagging: list[PmIssue] = []
    for issue in issues:
        forkcast = forkcast_by_issue.get(issue.number)
        if forkcast is None:
            lagging.append(issue)
            continue
        if int(forkcast.number) != issue.call_number:
            raise SyncError(
                f"call-number mismatch for issue {issue.number}: "
                f"PM #{issue.call_number}, Forkcast #{forkcast.number}"
            )
        if forkcast.date != issue.date:
            raise SyncError(
                f"date mismatch for issue {issue.number}: "
                f"PM {issue.date.isoformat()}, Forkcast {forkcast.date.isoformat()}"
            )
        ready.append(ReadyCall(issue=issue, forkcast=forkcast))
    ready.sort(key=lambda call: (call.date, int(call.number)), reverse=True)
    lagging.sort(key=lambda issue: (issue.date, issue.call_number), reverse=True)
    return ready, lagging


def strip_markdown(value: str) -> str:
    value = MARKDOWN_LINK_RE.sub(lambda match: match.group(1), value)
    value = re.sub(r"^\s*[-*+]\s+", "", value)
    value = value.replace("**", "").replace("__", "").replace("`", "")
    return re.sub(r"\s+", " ", value).strip(" \t:-")


def normalize_project_title(value: str) -> str:
    match = re.fullmatch(
        r"Projects?\s+(\d+)\)?(?:\s*,?\s*(\d+)\)?)?(?:\s*(?:and)?\s*(\d+)\)?)?",
        value.strip(),
        re.IGNORECASE,
    )
    if not match:
        numbers = re.findall(r"\d+", value)
        if value.lower().startswith("project") and numbers:
            if len(numbers) == 1:
                return f"project {numbers[0]}"
            return f"projects {', '.join(numbers[:-1])}, and {numbers[-1]}"
        return value.strip()
    numbers = [number for number in match.groups() if number]
    if len(numbers) == 1:
        return f"project {numbers[0]}"
    return f"projects {', '.join(numbers[:-1])}, and {numbers[-1]}"


def derive_presentation_title(
    line: str,
    label: str,
    previous_line: str,
) -> str:
    plain_line = strip_markdown(line)
    generic_label = bool(re.fullmatch(r"slides?|presentation", label.strip(), re.I))
    if generic_label:
        candidate = strip_markdown(previous_line) or label.strip()
        speaker_match = re.match(r"([^(@,]+)\s*\((?:@[^,)]*,?\s*)?(.+)\)$", candidate)
        if speaker_match:
            speaker = speaker_match.group(1).strip()
            description = speaker_match.group(2).strip()
            description = re.sub(r"^Context on\s+", "", description, flags=re.I)
            return f"{speaker} — {description}"
        return candidate

    presenter_tokens = re.findall(r"\[([^\]]+)\](?!\()", line)
    presenter = presenter_tokens[-1].strip() if presenter_tokens else ""
    candidate = plain_line
    if presenter:
        candidate = candidate.replace(f"[{presenter}]", "").strip()
        candidate = re.sub(rf"\b{re.escape(presenter)}\b\s*$", "", candidate).strip()

    update_match = re.match(
        r"Update from\s+([^ ]+)(?:\s+(.*))?$", candidate, re.IGNORECASE
    )
    if update_match:
        person = update_match.group(1).strip()
        detail = (update_match.group(2) or "").strip()
        return f"{person} — update{(' ' + detail) if detail else ''}"

    normalized = normalize_project_title(label)
    if presenter:
        return f"{presenter} — {normalized}"
    return candidate or label.strip()


def extract_presentations(body: str) -> tuple[list[Presentation], list[str]]:
    in_agenda = False
    previous_line = ""
    presentations: list[Presentation] = []
    ignored_urls: list[str] = []
    seen_urls: set[str] = set()

    for line in body.splitlines():
        if AGENDA_HEADING_RE.match(line):
            in_agenda = True
            previous_line = ""
            continue
        if in_agenda and CALL_SERIES_HEADING_RE.match(line):
            break
        if not in_agenda:
            continue

        links = list(MARKDOWN_LINK_RE.finditer(line))
        for match in links:
            label, url = match.group(1).strip(), match.group(2)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            context = f"{label} {line} {previous_line}"
            if "no slides" in line.lower() or not PRESENTATION_CONTEXT_RE.search(context):
                ignored_urls.append(url)
                continue
            presentations.append(
                Presentation(
                    title=derive_presentation_title(line, label, previous_line),
                    url=url,
                )
            )
        if strip_markdown(line):
            previous_line = line
    return presentations, ignored_urls


def load_overrides(path: Path) -> dict[int, list[Presentation]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SyncError(f"override manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SyncError(f"invalid JSON in override manifest: {path}") from exc
    if not isinstance(payload, dict):
        raise SyncError("override manifest must contain a JSON object")

    overrides: dict[int, list[Presentation]] = {}
    for issue_key, entry in payload.items():
        try:
            issue_number = int(issue_key)
        except ValueError as exc:
            raise SyncError(f"override issue key is not numeric: {issue_key}") from exc
        if not isinstance(entry, dict) or not isinstance(
            entry.get("presentations"), list
        ):
            raise SyncError(
                f"override for issue {issue_number} must contain presentations[]"
            )
        parsed: list[Presentation] = []
        for index, item in enumerate(entry["presentations"], start=1):
            if not isinstance(item, dict):
                raise SyncError(
                    f"override {issue_number} presentation {index} must be an object"
                )
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            kind = str(item.get("kind") or "auto")
            filename_value = item.get("filename")
            filename = str(filename_value) if filename_value is not None else None
            reason_value = item.get("reason")
            reason = str(reason_value) if reason_value is not None else None
            if not title:
                raise SyncError(
                    f"override {issue_number} presentation {index} needs a title"
                )
            if not url:
                raise SyncError(
                    f"override {issue_number} presentation {index} needs a URL"
                )
            if kind not in SUPPORTED_KINDS:
                raise SyncError(
                    f"override {issue_number} presentation {index} "
                    f"has unsupported kind: {kind}"
                )
            validate_https_url(url)
            if kind == "unavailable" and not reason:
                raise SyncError(
                    f"unavailable override {issue_number} presentation {index} "
                    "needs a reason"
                )
            if filename is not None and (
                Path(filename).name != filename or filename in {"", ".", ".."}
            ):
                raise SyncError(
                    f"override {issue_number} presentation {index} "
                    f"has unsafe filename: {filename}"
                )
            parsed.append(
                Presentation(
                    title=title,
                    url=url,
                    filename=filename,
                    kind=kind,
                    reason=reason,
                )
            )
        overrides[issue_number] = parsed
    return overrides


def presentations_for_call(
    call: ReadyCall,
    overrides: Mapping[int, Sequence[Presentation]],
) -> tuple[list[Presentation], list[str]]:
    if call.issue.number in overrides:
        return list(overrides[call.issue.number]), []
    return extract_presentations(call.issue.body)


def detect_kind(presentation: Presentation) -> str:
    if presentation.kind != "auto":
        return presentation.kind
    parsed = urllib.parse.urlparse(presentation.url)
    host = (parsed.hostname or "").lower()
    path = parsed.path
    if host == "docs.google.com" and re.match(r"^/presentation/d/[^/]+", path):
        return "google-slides"
    if host == "drive.google.com" and re.match(r"^/file/d/[^/]+", path):
        return "google-drive"
    if host == "github.com" and "/tree/" in path:
        return "github-directory"
    suffix = Path(path).suffix.lower()
    if host == "github.com" and path.startswith("/user-attachments/"):
        return "download"
    if suffix in SUPPORTED_DIRECT_EXTENSIONS:
        return "download"
    return "web-pdf"


def google_slides_export_url(url: str) -> str:
    match = re.match(
        r"^https://docs\.google\.com/presentation/d/([^/]+)", url
    )
    if not match:
        raise PermanentArchiveError("not a recognized Google Slides URL")
    return f"https://docs.google.com/presentation/d/{match.group(1)}/export/pdf"


def google_drive_download_url(url: str) -> str:
    match = re.match(r"^https://drive\.google\.com/file/d/([^/]+)", url)
    if not match:
        raise PermanentArchiveError("not a recognized Google Drive file URL")
    query = urllib.parse.urlencode({"export": "download", "id": match.group(1)})
    return f"https://drive.google.com/uc?{query}"


def github_directory_download_url(url: str, client: HttpClient) -> str:
    parsed = urllib.parse.urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 5 or parts[2] != "tree":
        raise PermanentArchiveError("not a recognized GitHub directory URL")
    owner, repository, ref = parts[0], parts[1], parts[3]
    directory = "/".join(parts[4:])
    api_path = "/".join(
        urllib.parse.quote(part, safe="") for part in (owner, repository)
    )
    quoted_directory = urllib.parse.quote(directory, safe="/")
    query = urllib.parse.urlencode({"ref": ref})
    api_url = (
        f"https://api.github.com/repos/{api_path}/contents/{quoted_directory}?{query}"
    )
    payload = client.get_json(api_url)
    if not isinstance(payload, list):
        raise PermanentArchiveError("GitHub directory did not return a file listing")
    candidates = [
        item
        for item in payload
        if isinstance(item, dict)
        and item.get("type") == "file"
        and Path(str(item.get("name") or "")).suffix.lower()
        in SUPPORTED_DIRECT_EXTENSIONS
        and isinstance(item.get("download_url"), str)
    ]
    if len(candidates) != 1:
        raise PermanentArchiveError(
            f"GitHub directory contains {len(candidates)} presentation files; "
            "add an override"
        )
    download_url = str(candidates[0]["download_url"])
    validate_https_url(download_url)
    return download_url


def content_disposition_filename(headers: Mapping[str, str]) -> str | None:
    disposition = headers.get("content-disposition", "")
    utf_match = re.search(r"filename\*=UTF-8''([^;]+)", disposition, re.I)
    if utf_match:
        return urllib.parse.unquote(utf_match.group(1)).strip('"')
    basic_match = re.search(r'filename="?([^";]+)"?', disposition, re.I)
    return basic_match.group(1).strip() if basic_match else None


def detect_extension(response: HttpResponse) -> str:
    if response.data.startswith(b"%PDF-"):
        return ".pdf"
    if response.data.startswith(b"PK\x03\x04"):
        return ".pptx"
    prefix = response.data[:1024].lstrip().lower()
    if prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html"):
        return ".html"

    filename = content_disposition_filename(response.headers)
    candidates = [
        Path(filename).suffix.lower() if filename else "",
        Path(urllib.parse.urlparse(response.final_url).path).suffix.lower(),
    ]
    for suffix in candidates:
        if suffix in SUPPORTED_DIRECT_EXTENSIONS:
            return ".html" if suffix == ".htm" else suffix
    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
    by_type = {
        "application/pdf": ".pdf",
        "application/vnd.ms-powerpoint": ".ppt",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
        "text/html": ".html",
    }
    if content_type in by_type:
        return by_type[content_type]
    raise PermanentArchiveError(
        f"unsupported downloaded content type: {content_type or 'unknown'}"
    )


def validate_file(path: Path, extension: str) -> None:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise TransientArchiveError(f"could not read archived file {path}: {exc}") from exc
    if not data:
        raise PermanentArchiveError("downloaded file is empty")
    normalized = ".html" if extension == ".htm" else extension.lower()
    if normalized == ".pdf" and not data.startswith(b"%PDF-"):
        raise PermanentArchiveError("download did not produce a PDF")
    if normalized == ".pptx" and not data.startswith(b"PK\x03\x04"):
        raise PermanentArchiveError("download did not produce a PPTX file")
    if normalized == ".html":
        prefix = data[:1024].lstrip().lower()
        if not (prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html")):
            raise PermanentArchiveError("download did not produce an HTML document")


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug or "presentation"


def choose_filename(
    presentation: Presentation,
    index: int,
    extension: str,
) -> str:
    extension = ".html" if extension == ".htm" else extension.lower()
    if presentation.filename:
        supplied = presentation.filename
        if Path(supplied).suffix.lower() != extension:
            raise PermanentArchiveError(
                f"override filename extension does not match archived {extension} file"
            )
        return supplied
    return f"{index:02d}-{slugify(presentation.title)}{extension}"


def write_download(
    response: HttpResponse,
    presentation: Presentation,
    index: int,
    destination: Path,
) -> tuple[str, str]:
    extension = detect_extension(response)
    filename = choose_filename(presentation, index, extension)
    output = destination / filename
    temporary = destination / f".{filename}.part"
    try:
        temporary.write_bytes(response.data)
        validate_file(temporary, extension)
        os.replace(temporary, output)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return filename, extension_label(extension)


def extension_label(extension: str) -> str:
    extension = extension.lstrip(".").upper()
    return "HTML" if extension == "HTM" else extension


def archive_presentation(
    presentation: Presentation,
    index: int,
    destination: Path,
    client: HttpClient,
    chrome: ChromeRenderer,
) -> ArchivedPresentation:
    kind = detect_kind(presentation)
    if kind == "unavailable":
        return ArchivedPresentation(
            presentation=presentation,
            filename=None,
            label=None,
            unavailable_reason=presentation.reason or "unavailable",
        )

    try:
        if kind in {"marp-web-pdf", "web-pdf"}:
            # Fail on HTTP status before Chrome can turn an error page into a PDF.
            response = client.get(
                presentation.url,
                accept="text/html,application/xhtml+xml",
            )
            filename = choose_filename(presentation, index, ".pdf")
            if kind == "marp-web-pdf":
                chrome.render_marp(
                    presentation.url,
                    response.data,
                    destination / filename,
                )
            else:
                chrome.render(presentation.url, destination / filename)
            return ArchivedPresentation(
                presentation=presentation,
                filename=filename,
                label="PDF",
                unavailable_reason=None,
            )

        url = presentation.url
        if kind == "google-slides":
            url = google_slides_export_url(url)
        elif kind == "google-drive":
            url = google_drive_download_url(url)
        elif kind == "github-directory":
            url = github_directory_download_url(url, client)
        elif kind != "download":
            raise PermanentArchiveError(f"unsupported acquisition kind: {kind}")
        response = client.get(url)
        filename, label = write_download(
            response, presentation, index, destination
        )
        return ArchivedPresentation(
            presentation=presentation,
            filename=filename,
            label=label,
            unavailable_reason=None,
        )
    except PermanentArchiveError as exc:
        return ArchivedPresentation(
            presentation=presentation,
            filename=None,
            label=None,
            unavailable_reason=str(exc),
        )


def markdown_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def render_call_readme(
    call: ReadyCall,
    archived: Sequence[ArchivedPresentation],
) -> str:
    call_number = int(call.number)
    lines = [
        f"# zkEVM breakout call #{call_number}",
        "",
        (
            f"{format_date(call.date)} · "
            f"[Recording and notes]({call.forkcast_url}) · "
            f"[Agenda]({call.issue.html_url})"
        ),
        "",
    ]
    if not archived:
        lines.extend(["No presentation links were found in the agenda.", ""])
        return "\n".join(lines)

    lines.extend(
        [
            "| Presentation | Local copy | Original source |",
            "| --- | --- | --- |",
        ]
    )
    for item in archived:
        title = markdown_escape(item.presentation.title)
        source = f"[Source]({item.presentation.url})"
        if item.filename and item.label:
            local = f"[{item.label}]({item.filename})"
        else:
            reason = markdown_escape(item.unavailable_reason or "unavailable")
            local = f"Unavailable ({reason})"
        lines.append(f"| {title} | {local} | {source} |")
    lines.append("")
    return "\n".join(lines)


def archive_call(
    call: ReadyCall,
    presentations: Sequence[Presentation],
    destination: Path,
    client: HttpClient,
    chrome: ChromeRenderer,
) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    archived: list[ArchivedPresentation] = []
    filenames: set[str] = set()
    for index, presentation in enumerate(presentations, start=1):
        result = archive_presentation(
            presentation, index, destination, client, chrome
        )
        if result.filename:
            if result.filename in filenames:
                raise SyncError(
                    f"duplicate archive filename for call #{int(call.number)}: "
                    f"{result.filename}"
                )
            filenames.add(result.filename)
        archived.append(result)
    (destination / "README.md").write_text(
        render_call_readme(call, archived), encoding="utf-8"
    )


def format_date(value: dt.date) -> str:
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def render_progress_section(
    calls: Sequence[ReadyCall],
    local_numbers: set[str],
) -> str:
    lines = [
        PROGRESS_HEADING,
        "",
        "| Call | Date | Resources |",
        "| ---: | --- | --- |",
    ]
    for call in calls:
        resources = f"[Recording & notes]({call.forkcast_url})"
        if call.number in local_numbers:
            resources += f" · [Slides](breakout-calls/{call.number}/)"
        lines.append(
            f"| {int(call.number)} | {format_date(call.date)} | {resources} |"
        )
    return "\n".join(lines) + "\n\n"


def replace_heading_section(
    document: str,
    start_heading: str,
    end_heading: str,
    replacement: str,
) -> str:
    start_matches = list(
        re.finditer(rf"(?m)^{re.escape(start_heading)}\s*$", document)
    )
    end_matches = list(
        re.finditer(rf"(?m)^{re.escape(end_heading)}\s*$", document)
    )
    if len(start_matches) != 1 or len(end_matches) != 1:
        raise SyncError(
            f"expected exactly one {start_heading!r} and one {end_heading!r}"
        )
    start = start_matches[0].start()
    end = end_matches[0].start()
    if end <= start:
        raise SyncError(f"{end_heading!r} must follow {start_heading!r}")
    return document[:start] + replacement + document[end:]


def local_call_numbers(breakout_root: Path) -> set[str]:
    numbers: set[str] = set()
    for entry in breakout_root.iterdir():
        if not entry.is_dir() or not re.fullmatch(r"\d{3,}", entry.name):
            continue
        if not (entry / "README.md").is_file():
            raise SyncError(f"existing call directory has no README: {entry}")
        numbers.add(entry.name)
    return numbers


def parse_local_call_date(readme: Path) -> dt.date:
    text = readme.read_text(encoding="utf-8")
    for line in text.splitlines():
        match = re.match(r"^([A-Z][a-z]+ \d{1,2}, \d{4})\s+·", line)
        if match:
            return parse_issue_date(match.group(1))
    raise SyncError(f"could not find call date in {readme}")


def render_breakout_index(
    existing: str,
    breakout_root: Path,
    calls: Sequence[ReadyCall],
    available_numbers: set[str],
    *,
    retrieval_date: dt.date | None,
    staged_root: Path | None = None,
) -> str:
    ready_by_number = {call.number: call for call in calls}
    rows: list[tuple[dt.date, str]] = []
    for number in available_numbers:
        call = ready_by_number.get(number)
        if call:
            call_date = call.date
        else:
            base = (
                staged_root / number
                if staged_root is not None and (staged_root / number).is_dir()
                else breakout_root / number
            )
            call_date = parse_local_call_date(base / "README.md")
        rows.append((call_date, number))
    rows.sort(key=lambda item: (item[0], int(item[1])), reverse=True)

    table_lines = [
        "| Call | Date | Slides |",
        "| ---: | --- | --- |",
    ]
    for call_date, number in rows:
        call_number = int(number)
        table_lines.append(
            f"| {call_number} | {format_date(call_date)} | "
            f"[Call #{call_number}]({number}/) |"
        )
    table = "\n".join(table_lines)
    updated = replace_table(existing, "| Call | Date | Slides |", table)
    if retrieval_date is not None:
        updated, count = re.subn(
            r"The snapshots were retrieved on [A-Z][a-z]+ \d{1,2}, \d{4}\.",
            f"The snapshots were retrieved on {format_date(retrieval_date)}.",
            updated,
        )
        if count != 1:
            raise SyncError("could not update breakout-call retrieval date")
    return updated


def replace_table(document: str, header: str, replacement: str) -> str:
    lines = document.splitlines(keepends=True)
    header_indexes = [
        index for index, line in enumerate(lines) if line.rstrip("\r\n") == header
    ]
    if len(header_indexes) != 1:
        raise SyncError(f"expected exactly one Markdown table header {header!r}")
    start = header_indexes[0]
    end = start
    while end < len(lines) and lines[end].lstrip().startswith("|"):
        end += 1
    newline = "\r\n" if lines[start].endswith("\r\n") else "\n"
    replacement_lines = [line + newline for line in replacement.splitlines()]
    return "".join(lines[:start] + replacement_lines + lines[end:])


def atomic_write(path: Path, content: str) -> None:
    encoded = content.encode("utf-8")
    if path.read_bytes() == encoded:
        return
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            os.fchmod(handle.fileno(), path.stat().st_mode & 0o777)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def short_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def synchronize(
    repo_root: Path,
    *,
    check: bool,
    chrome_binary: str | None,
    client: HttpClient | None = None,
    today: dt.date | None = None,
) -> int:
    repo_root = repo_root.resolve()
    progress_path = repo_root / "PROGRESS.md"
    breakout_root = repo_root / "breakout-calls"
    override_path = repo_root / "scripts" / "breakout-call-overrides.json"
    for required in (progress_path, breakout_root / "README.md", override_path):
        if not required.exists():
            raise SyncError(f"required path does not exist: {required}")

    client = client or HttpClient(token=os.environ.get("GITHUB_TOKEN"))
    today = today or dt.date.today()
    issues = fetch_pm_issues(client)
    forkcast_calls = fetch_forkcast_calls(client)
    calls, lagging = join_calls(issues, forkcast_calls)
    if not calls:
        raise SyncError("no completed zkEVM calls were found in both sources")
    for issue in lagging:
        print(
            f"info: PM issue {issue.number} (call #{issue.call_number}) "
            "is not in Forkcast yet",
            file=sys.stderr,
        )

    overrides = load_overrides(override_path)
    existing_numbers = local_call_numbers(breakout_root)
    ready_numbers = {call.number for call in calls}
    missing_calls = [call for call in calls if call.number not in existing_numbers]

    progress_original = progress_path.read_text(encoding="utf-8")
    index_path = breakout_root / "README.md"
    index_original = index_path.read_text(encoding="utf-8")

    if check:
        progress_expected = replace_heading_section(
            progress_original,
            PROGRESS_HEADING,
            PROGRESS_END_HEADING,
            render_progress_section(calls, existing_numbers),
        )
        index_expected = render_breakout_index(
            index_original,
            breakout_root,
            calls,
            existing_numbers,
            retrieval_date=None,
        )
        problems: list[str] = []
        if missing_calls:
            problems.append(
                "missing call archives: "
                + ", ".join(f"#{int(call.number)}" for call in missing_calls)
            )
        if progress_expected != progress_original:
            problems.append("PROGRESS.md coordination table is stale")
        if index_expected != index_original:
            problems.append("breakout-calls/README.md table is stale")
        if problems:
            for problem in problems:
                print(f"check failed: {problem}", file=sys.stderr)
            return 1
        print(
            f"breakout calls are current ({len(calls)} calls, "
            f"PROGRESS {short_digest(progress_original)})"
        )
        return 0

    chrome = ChromeRenderer(chrome_binary)
    with tempfile.TemporaryDirectory(
        prefix=".breakout-stage-", dir=breakout_root
    ) as stage_name:
        stage_root = Path(stage_name)
        for call in reversed(missing_calls):
            presentations, ignored = presentations_for_call(call, overrides)
            for url in ignored:
                print(
                    f"info: ignored non-presentation agenda link for "
                    f"call #{int(call.number)}: {url}",
                    file=sys.stderr,
                )
            print(f"archiving call #{int(call.number)} ({len(presentations)} links)")
            archive_call(
                call,
                presentations,
                stage_root / call.number,
                client,
                chrome,
            )

        available_numbers = existing_numbers | {
            call.number for call in missing_calls
        }
        progress_updated = replace_heading_section(
            progress_original,
            PROGRESS_HEADING,
            PROGRESS_END_HEADING,
            render_progress_section(calls, available_numbers),
        )
        index_updated = render_breakout_index(
            index_original,
            breakout_root,
            calls,
            available_numbers,
            retrieval_date=today if missing_calls else None,
            staged_root=stage_root,
        )

        for call in reversed(missing_calls):
            source = stage_root / call.number
            destination = breakout_root / call.number
            if destination.exists():
                raise SyncError(
                    f"refusing to overwrite existing call directory: {destination}"
                )
            source.rename(destination)
        atomic_write(index_path, index_updated)
        atomic_write(progress_path, progress_updated)

    changed_files = int(index_updated != index_original) + int(
        progress_updated != progress_original
    )
    print(
        f"synchronized {len(calls)} calls; archived {len(missing_calls)} new calls; "
        f"updated {changed_files} Markdown files"
    )
    extra_local = existing_numbers - ready_numbers
    if extra_local:
        print(
            "info: retained local-only call directories: "
            + ", ".join(sorted(extra_local)),
            file=sys.stderr,
        )
    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Archive completed zkEVM breakout-call slides and update Markdown indexes."
        )
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report stale archives or Markdown without writing files",
    )
    parser.add_argument(
        "--chrome-binary",
        help="Chrome/Chromium executable used for web-native slide decks",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return synchronize(
            args.repo_root,
            check=args.check,
            chrome_binary=args.chrome_binary,
        )
    except SyncError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
