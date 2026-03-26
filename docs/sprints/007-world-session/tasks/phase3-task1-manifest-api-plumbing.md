# Task: World Manifest API + TS Types + Client Methods

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 3 — Fork UI + World Inspector

## Description

Add a backend endpoint that exposes the manifest structure for a world — which layers are library vs custom, what template each uses, version info. Add corresponding TS types and two new client methods: `getWorldManifest()` and `forkLayer()`.

Currently `GET /worlds/{id}` returns world content (regions, NPCs, etc.) — not manifest metadata. The frontend needs to know layer sources to render the inspector and fork buttons.

### Endpoint: `GET /api/master/worlds/{world_id}/manifest`

Response shape:
```json
{
  "world_id": "sword_vale",
  "name": "Sword Vale",
  "layers": [
    {
      "layer_type": "geography",
      "source": "library",
      "template": "sword_vale",
      "version": "1.0"
    },
    {
      "layer_type": "entities",
      "source": "custom",
      "template": null,
      "version": null
    }
  ]
}
```

### TS Types

- `WorldManifest` — world_id, name, layers[]
- `LayerInfo` — layer_type, source ("library" | "custom"), template (string | null), version (string | null)

### Client Methods

- `api.master.getWorldManifest(worldId)` → `WorldManifest`
- `api.master.forkLayer(worldId, layerType)` → `MessageResponse`

## Tests First

1. **Unit test — manifest endpoint returns layer sources correctly for a world with mixed library/custom layers.** Create a world via `assemble_world`, fork one layer, then `GET /manifest` and assert: 4 layers show `source: library` with template slug, 1 shows `source: custom` with null template.
2. **Unit test — manifest endpoint returns 404 for nonexistent world.**
3. **Unit test — all 5 layer types are always present in response, in canonical order.**

## Implementation

1. Add `get_world_manifest(world_id, lang)` to `GameService` — reads manifest.yaml, returns structured dict with layer info.
2. Add Pydantic response models: `LayerInfo`, `WorldManifestResponse`.
3. Add `GET /api/master/worlds/{world_id}/manifest` route in `routes_master.py`.
4. Add TS types `WorldManifest`, `LayerInfo` to `api.ts`.
5. Add `getWorldManifest()` and `forkLayer()` to `apiClient.ts` master section.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Manifest returns correct source/template/version for all 5 layers
- [ ] Fork client method calls `POST /worlds/{id}/fork/{layer_type}` correctly
- [ ] TS types match backend response schema

## Status

`pending`
