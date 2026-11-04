import { act, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import "@/i18n"
import i18n from "@/i18n"
import { api } from "@/transport/apiClient"
import type { EntityEntry, LayerInfo, WorldManifestResponse } from "@/types/api"
import { WorldEditor } from "../WorldEditor"

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      getWorldManifest: vi.fn(),
      createEntity: vi.fn(),
      listEntities: vi.fn(),
      getSchema: vi.fn(),
      getRefs: vi.fn(),
      listCatalog: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api.master)

function manifest(...layerTypes: string[]): WorldManifestResponse {
  return {
    world_id: "sword_vale",
    name: "Sword Vale",
    layers: layerTypes.map<LayerInfo>((layer_type) => ({
      layer_type,
      source: "custom",
      template: null,
      version: null,
    })),
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function renderEditor(readOnly = false, onClose = vi.fn()) {
  return render(<WorldEditor worldId="sword_vale" readOnly={readOnly} onClose={onClose} />)
}

describe("WorldEditor uncovered branches", () => {
  beforeEach(async () => {
    vi.resetAllMocks()
    await i18n.changeLanguage("en")
    mockApi.getWorldManifest.mockResolvedValue(manifest("ecology"))
    mockApi.listEntities.mockResolvedValue([])
    mockApi.getSchema.mockResolvedValue({ type: "object", properties: {} })
    mockApi.getRefs.mockResolvedValue([])
    mockApi.listCatalog.mockResolvedValue([{ id: "goblin", name: "Goblin scout" }])
    mockApi.createEntity.mockResolvedValue({ id: "goblin", base: "goblin" })
  })

  it("waits for the manifest before showing controls and renders the returned entity data", async () => {
    const pending = deferred<WorldManifestResponse>()
    mockApi.getWorldManifest.mockReturnValue(pending.promise)
    mockApi.listEntities.mockImplementation(async (_worldId, entityType) =>
      entityType === "region" ? [{ id: "north", name: "Northern Reach" }] : [],
    )
    renderEditor(true)

    // The loading spinner has no accessible label; controls must stay unavailable until loaded.
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(screen.queryByRole("heading")).not.toBeInTheDocument()
    expect(mockApi.listEntities).not.toHaveBeenCalled()
    expect(mockApi.getWorldManifest).toHaveBeenCalledExactlyOnceWith("sword_vale", "en")

    await act(async () => pending.resolve(manifest("geography")))

    expect(await screen.findByRole("cell", { name: "Northern Reach" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Geography" })).toBeInTheDocument()
    expect(screen.getByText("No entities")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Back" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled()
  })

  it("leaves the editor empty when the manifest request fails", async () => {
    const pending = deferred<WorldManifestResponse>()
    mockApi.getWorldManifest.mockReturnValue(pending.promise)
    renderEditor()

    await act(async () => pending.reject(new Error("Manifest unavailable")))

    // Manifest failures are intentionally swallowed; no editor actions are available.
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(screen.queryByRole("heading")).not.toBeInTheDocument()
    expect(mockApi.listEntities).not.toHaveBeenCalled()
    expect(mockApi.createEntity).not.toHaveBeenCalled()
  })

  it("uses the layer name as a fallback for an unmapped layer and can close the editor", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    mockApi.getWorldManifest.mockResolvedValue(manifest("history"))
    renderEditor(false, onClose)

    expect(await screen.findByRole("heading", { name: "history" })).toBeInTheDocument()
    expect(screen.queryByRole("table")).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Pick from catalog" })).not.toBeInTheDocument()
    expect(mockApi.listEntities).not.toHaveBeenCalled()
    await user.click(screen.getByRole("button", { name: "Close" }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("selects settlement and NPC editors directly from the stepper", async () => {
    const user = userEvent.setup()
    mockApi.getWorldManifest.mockResolvedValue(manifest("politics", "settlements", "entities"))
    mockApi.listEntities.mockImplementation(async (_worldId, entityType) => [
      { id: entityType, name: `${entityType} example` },
    ])
    renderEditor()

    await user.click(await screen.findByRole("button", { name: "Settlements" }))
    expect(await screen.findByRole("cell", { name: "settlement example" })).toBeInTheDocument()
    expect(mockApi.listEntities).toHaveBeenCalledWith("sword_vale", "settlement")
    expect(screen.getByRole("heading", { name: "Settlements", level: 3 })).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Entities" }))
    expect(await screen.findByRole("cell", { name: "npc example" })).toBeInTheDocument()
    expect(mockApi.listEntities).toHaveBeenCalledWith("sword_vale", "npc")
    expect(screen.getByRole("heading", { name: "npcs" })).toBeInTheDocument()
    expect(screen.queryByRole("cell", { name: "settlement example" })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled()
  })

  it("creates a monster template from a catalog pick and closes the picker only after success", async () => {
    const user = userEvent.setup()
    const pending = deferred<EntityEntry>()
    mockApi.createEntity.mockReturnValue(pending.promise)
    renderEditor()

    await user.click(await screen.findByRole("button", { name: "Pick from catalog" }))
    expect(await screen.findByRole("cell", { name: "Goblin scout" })).toBeInTheDocument()
    expect(mockApi.listCatalog).toHaveBeenCalledExactlyOnceWith("monster_catalog")
    expect(mockApi.getSchema).toHaveBeenCalledWith("monster_catalog")

    await user.click(screen.getByRole("button", { name: "Pick" }))
    expect(mockApi.createEntity).toHaveBeenCalledExactlyOnceWith(
      "sword_vale", "monster_template", "goblin", { base: "goblin" },
    )
    expect(screen.getByRole("heading", { name: "Pick from monster catalog" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Pick from catalog" })).not.toBeInTheDocument()

    await act(async () => pending.resolve({ id: "goblin", base: "goblin" }))

    expect(screen.getByRole("button", { name: "Pick from catalog" })).toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "Pick from monster catalog" })).not.toBeInTheDocument()
  })

  it("lets the user cancel and reopen an empty catalog without creating an entity", async () => {
    const user = userEvent.setup()
    mockApi.listCatalog.mockResolvedValue([])
    renderEditor()

    await user.click(await screen.findByRole("button", { name: "Pick from catalog" }))
    expect(await screen.findByText("No entries")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Pick" })).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Cancel" }))
    expect(screen.queryByText("No entries")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Pick from catalog" }))
    expect(await screen.findByText("No entries")).toBeInTheDocument()
    expect(mockApi.listCatalog).toHaveBeenCalledTimes(2)
    expect(mockApi.createEntity).not.toHaveBeenCalled()
  })

  it("shows a catalog loading error and allows cancellation without creating an entity", async () => {
    const user = userEvent.setup()
    mockApi.listCatalog.mockRejectedValue(new Error("Catalog unavailable"))
    renderEditor()

    await user.click(await screen.findByRole("button", { name: "Pick from catalog" }))
    expect(await screen.findByText("Failed to load catalog")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Cancel" }))
    expect(screen.queryByText("Failed to load catalog")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Pick from catalog" })).toBeInTheDocument()
    expect(mockApi.createEntity).not.toHaveBeenCalled()
  })

  it.each([
    { action: "Back", destination: "Geography" },
    { action: "Next", destination: "Entities" },
    { action: "Geography", destination: "Geography" },
  ])("resets the open catalog when navigating with $action", async ({ action, destination }) => {
    const user = userEvent.setup()
    mockApi.getWorldManifest.mockResolvedValue(manifest("geography", "ecology", "entities"))
    renderEditor()

    await user.click(await screen.findByRole("button", { name: "Ecology" }))
    await user.click(screen.getByRole("button", { name: "Pick from catalog" }))
    expect(await screen.findByRole("cell", { name: "Goblin scout" })).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: action }))
    expect(screen.getByRole("heading", { name: destination, level: 3 })).toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "Pick from monster catalog" })).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Ecology" }))
    expect(screen.getByRole("button", { name: "Pick from catalog" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument()
    expect(mockApi.createEntity).not.toHaveBeenCalled()
    await waitFor(() => expect(screen.getAllByText("No entities")).toHaveLength(2))
  })
})
