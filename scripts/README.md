# Maintenance scripts

## zkEVM breakout calls

Run the dependency-free updater after a zkEVM breakout call has closed and its
canonical entry is available in Forkcast:

```console
python3 scripts/update_breakout_calls.py
```

The updater archives presentations for new calls, refreshes
`breakout-calls/README.md`, and rewrites only the breakout-call section of
`PROGRESS.md`. Google Slides and Drive files are exported directly; web-native
decks require Google Chrome or Chromium. Set `GITHUB_TOKEN` to avoid GitHub's
anonymous API rate limit, and use `--chrome-binary PATH` when the browser is not
discoverable automatically.

Use `--check` for a read-only freshness check.

### Agenda overrides

If automatic agenda parsing needs curation, add an issue-number entry to
`breakout-call-overrides.json`:

```json
{
  "2175": {
    "presentations": [
      {
        "title": "Ignacio — projects 1, 2, and 6",
        "url": "https://docs.google.com/presentation/d/example/edit",
        "filename": "01-ignacio-projects-1-2-6.pdf",
        "kind": "google-slides"
      }
    ]
  }
}
```

The ordered `presentations` list replaces automatic discovery for that issue.
`filename` and `kind` are optional. Supported kinds are `auto`, `download`,
`github-directory`, `google-drive`, `google-slides`, `web-pdf`, and
`unavailable`; unavailable entries also require a `reason`.

Run the offline test suite with:

```console
python3 -m unittest discover -s scripts -p 'test_*.py'
```
