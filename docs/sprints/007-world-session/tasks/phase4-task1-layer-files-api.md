# Task: Layer Files Read/Write API

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 4 — Layer Editor

## Description

Add API endpoints to read and write individual YAML files within a world's layer directory. Only custom (forked) layers are writable — library layers are read-only. Service methods in GameService, routes in routes_master.py.

Endpoints:
- `GET /api/master/worlds/{world_id}/layers/{layer_type}/files` — list data files with contents (excludes metadata.yaml)
- `GET /api/master/worlds/{world_id}/layers/{layer_type}/files/{filename}` — read single file content
- `PUT /api/master/worlds/{world_id}/layers/{layer_type}/files/{filename}` — write file content (custom layers only)

Security: validate filename is a bare name (no `/`, no `..`, must end with `.yaml`). Reject anything else with 400.

Validation on write: parse YAML to confirm it's syntactically valid. Return 422 with parse error details if invalid.

## Tests First

Unit tests in `tests/unit/test_layer_files_api.py`:

1. **Read files from custom layer** — fork a layer to custom in a temp world, call get_layer_files → returns dict of filename→content for all .yaml files except metadata.yaml.
2. **Read single file** — get_layer_file returns the raw YAML string for a specific file.
3. **Read files from library layer** — works fine (read is allowed for both sources), returns file contents.
4. **Write file to custom layer** — update_layer_file writes new content, re-read confirms change persisted.
5. **Write file to library layer rejected** — update_layer_file raises ValueError for library layers.
6. **Write invalid YAML rejected** — update_layer_file raises ValueError with parse error for malformed YAML.
7. **Path traversal rejected** — filenames like `../evil.yaml`, `foo/bar.yaml`, `.hidden` raise ValueError.
8. **File not found** — reading a nonexistent file raises FileNotFoundError.

## Implementation

Service methods in `game_service.py` (or a new `commands_content.py` mixin if game_service is already large):
- `get_layer_files(world_id, layer_type) -> dict[str, str]` — resolve manifest → get layer path → list .yaml files (skip metadata.yaml) → read each → return {name: content}
- `get_layer_file(world_id, layer_type, filename) -> str` — same resolution, read single file
- `update_layer_file(world_id, layer_type, filename, content) -> None` — check source is custom, validate filename, parse YAML, write

Routes in `routes_master.py` under the existing worlds section.

Schemas: `LayerFilesResponse(files: dict[str, str])`, `LayerFileResponse(filename: str, content: str)`, `UpdateLayerFileRequest(content: str)`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Library layers readable but not writable
- [ ] Path traversal attempts return 400
- [ ] Invalid YAML returns 422 with error details

## Status

`done`

## Developer Notes

Service methods added directly to GameService (alongside existing world/manifest/fork methods — same abstraction level, no need for a separate mixin). Three methods: `get_layer_files`, `get_layer_file`, `update_layer_file` plus helpers `_resolve_layer_path` and `_validate_filename`.

API routes added to routes_master.py: GET files list, GET single file, PUT single file. Invalid YAML returns 422, path traversal returns 400, library write returns 400.

10 unit tests cover: read custom/library, write custom, reject library write, reject invalid YAML, reject path traversal (both read and write), file not found, world not found.
