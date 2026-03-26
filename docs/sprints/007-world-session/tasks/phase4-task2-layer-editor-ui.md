# Task: Layer Editor UI

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 4 — Layer Editor

## Description

Add an "Edit" button on custom layers in WorldInspector that opens a LayerEditor component. The editor shows a file picker (tabs or dropdown) and a YAML text editor with save functionality. Library layers show a read-only "View" option.

## Tests First

Frontend tests aren't in scope for this project's TDD approach (no frontend test infra). Verification is manual + E2E in task 3.

Behavioral contract to verify manually:
1. Custom layer row shows "Edit" button next to the "custom" badge.
2. Clicking "Edit" opens LayerEditor with file list loaded from API.
3. Selecting a file shows its YAML content in a textarea/editor.
4. Editing + Save calls PUT endpoint, shows success/error feedback.
5. Invalid YAML save shows the backend's parse error.
6. Library layer row shows "View" button (read-only editor, no save).
7. Editor can be closed to return to the layer list.

## Implementation

1. **API client methods** in `frontend/src/transport/apiClient.ts`:
   - `getLayerFiles(worldId, layerType)` → GET `/api/master/worlds/{id}/layers/{type}/files`
   - `getLayerFile(worldId, layerType, filename)` → GET `.../files/{filename}`
   - `updateLayerFile(worldId, layerType, filename, content)` → PUT `.../files/{filename}`

2. **TypeScript types** in `frontend/src/types/api.ts`:
   - `LayerFilesResponse { files: Record<string, string> }`
   - `UpdateLayerFileRequest { content: string }`

3. **LayerEditor component** (`frontend/src/components/master/LayerEditor.tsx`):
   - Props: `worldId, layerType, readOnly, onClose`
   - State: file list, selected file, editor content, dirty flag, saving, error
   - File tabs along the top (or sidebar) — one per .yaml file
   - Textarea with monospace font for YAML editing (keep it simple — no need for monaco/codemirror)
   - Save button (disabled when readOnly or not dirty)
   - Error display for validation failures

4. **WorldInspector integration**:
   - Add "Edit" button on custom layer rows, "View" on library rows
   - When clicked, render LayerEditor inline (below the layer row) or as a panel
   - Track which layer is being edited in state

5. **i18n**: Add translation keys for edit/view/save/close buttons, error messages.

## Acceptance Criteria

- [ ] "Edit" button appears on custom layers in WorldInspector
- [ ] "View" button appears on library layers (read-only mode)
- [ ] File picker shows all data files (no metadata.yaml)
- [ ] YAML content loads and displays correctly
- [ ] Save persists changes via PUT endpoint
- [ ] Validation errors from backend display clearly
- [ ] Existing tests still pass (`make check`)

## Status

`done`

## Developer Notes

Implemented as planned. LayerEditor is a standalone component in `master/LayerEditor.tsx` with file tabs, monospace textarea, save with error display. WorldInspector now shows "Edit" on custom layers and "View" (read-only) on library layers — clicking toggles an inline editor below the layer row. API client methods added for all 3 layer file endpoints. i18n keys added for both en/ru.
