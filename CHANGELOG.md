# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-04-07

### Added

- Static AST-based import analysis — no runtime execution needed
- Internal import graph across an entire Python project
- Cloud SDK detection: AWS (`boto3`), GCP (`google.cloud`, `firebase_admin`), Azure (`azure.*`)
- HTTP client detection: `requests`, `httpx`, `aiohttp`, `urllib3` and more
- Circular dependency highlighting (red edges)
- Interactive HTML output via `pyvis`
- Static SVG/PNG output via `graphviz`
- Rich terminal output with live progress and color-coded summary
- TUI with ego-graph explorer — 3-column layout, searchable sidebar
