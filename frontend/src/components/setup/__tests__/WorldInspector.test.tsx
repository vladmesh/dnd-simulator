import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import i18n from "@/i18n"
import { api } from "@/transport/apiClient"
import type { LayerInfo, MessageResponse, WorldManifestResponse } from "@/types/api"
import { WorldInspector } from "../WorldInspector"

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      getWorldManifest: vi.fn(),
      forkLayer: vi.fn(),
      createEntity: vi.fn(),
      listEntities: vi.fn(),
      getSchema: vi.fn(),
      getLayerFiles: vi.fn(),
      listCatalog: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api.master)
const worldId = "sword_vale"

function layer(layerType: string, source: LayerInfo["source"] = "custom"): LayerInfo {
  return {
    layer_type: layerType,
    source,
    template: source === "library" ? `${layerType}_template` : null,
    version: source === "library" ? "1" : null,
  }
}

function manifest(layers: LayerInfo[]): WorldManifestResponse {
  return { world_id: worldId, name: "Sword Vale", layers }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function renderLayers(layers: LayerInfo[]) {
  mockApi.getWorldManifest.mockResolvedValue(manifest(layers))
  return render(<WorldInspector worldId={worldId} />)
}

describe("WorldInspector", () => {
  beforeEach(async () => {
    vi.resetAllMocks()
    await i18n.changeLanguage("en")
    mockApi.listEntities.mockResolvedValue([])
    mockApi.getSchema.mockResolvedValue({})
    mockApi.getLayerFiles.mockResolvedValue({ files: { "notes.yaml": "description: Old lore" } })
    mockApi.listCatalog.mockResolvedValue([{ id: "goblin", name: "Goblin" }])
  })

  afterEach(() => vi.useRealTimers())

  it("waits for the manifest before showing layers and their source-specific actions", async () => {
    const request = deferred<WorldManifestResponse>()
    mockApi.getWorldManifest.mockReturnValue(request.promise)
    render(<WorldInspector worldId={worldId} />)

    expect(mockApi.getWorldManifest).toHaveBeenCalledWith(worldId, "en")
    // The loading spinner has no accessible label; no layer controls are available yet.
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(screen.queryByText("Geography")).not.toBeInTheDocument()

    await act(async () => {
      request.resolve(manifest([layer("geography", "library"), layer("ecology")]))
    })

    expect(await screen.findByText("Geography")).toBeVisible()
    expect(screen.getByText("Library: geography_template")).toBeVisible()
    expect(screen.getByText("Ecology")).toBeVisible()
    expect(screen.getByText("Custom")).toBeVisible()
    expect(screen.getByRole("button", { name: "View" })).toBeEnabled()
    expect(screen.getByRole("button", { name: "Fork" })).toBeEnabled()
    expect(screen.getByRole("button", { name: "Edit" })).toBeEnabled()
  })

  it("offers no editing or fork actions for an empty manifest", async () => {
    const request = deferred<WorldManifestResponse>()
    mockApi.getWorldManifest.mockReturnValue(request.promise)
    render(<WorldInspector worldId={worldId} />)
    await act(async () => request.resolve(manifest([])))

    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(screen.queryByRole("heading")).not.toBeInTheDocument()
    expect(screen.queryByText(/failed/i)).not.toBeInTheDocument()
    expect(mockApi.forkLayer).not.toHaveBeenCalled()
    expect(mockApi.listEntities).not.toHaveBeenCalled()
  })

  it("shows a translated error when the manifest cannot be loaded", async () => {
    mockApi.getWorldManifest.mockRejectedValue(new Error("offline"))
    render(<WorldInspector worldId={worldId} />)

    expect(await screen.findByText("Failed to load layer info")).toBeVisible()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
  })

  it("views library entity layers read-only and closes by toggling View or using Close", async () => {
    const user = userEvent.setup()
    renderLayers([layer("geography", "library"), layer("ecology", "library")])
    const views = await screen.findAllByRole("button", { name: "View" })
    await user.click(views[0])

    expect(await screen.findAllByText("No entities")).toHaveLength(2)
    expect(screen.getByRole("heading", { name: "regions" })).toBeVisible()
    expect(screen.getByRole("heading", { name: "locations" })).toBeVisible()
    expect(mockApi.listEntities).toHaveBeenCalledWith(worldId, "region")
    expect(mockApi.listEntities).toHaveBeenCalledWith(worldId, "location")
    expect(screen.queryByRole("button", { name: "Add" })).not.toBeInTheDocument()

    await user.click(views[0])
    expect(screen.queryByRole("heading", { name: "regions" })).not.toBeInTheDocument()
    await user.click(views[1])
    expect(await screen.findAllByText("No entities")).toHaveLength(2)
    expect(screen.getByRole("heading", { name: "monster templates" })).toBeVisible()
    expect(screen.queryByRole("button", { name: "Pick from catalog" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Add" })).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Close" }))
    expect(screen.queryByRole("heading")).not.toBeInTheDocument()
  })

  it("switches custom layers to their corresponding editable entity lists", async () => {
    const user = userEvent.setup()
    renderLayers([layer("politics"), layer("settlements"), layer("entities")])
    const edits = await screen.findAllByRole("button", { name: "Edit" })
    const cases = [
      { entityType: "nation", heading: "nations" },
      { entityType: "settlement", heading: "settlements" },
      { entityType: "npc", heading: "npcs" },
    ]

    for (const [index, { entityType, heading }] of cases.entries()) {
      await user.click(edits[index])
      expect(await screen.findByText("No entities")).toBeVisible()
      expect(screen.getByRole("heading", { name: heading })).toBeVisible()
      expect(screen.getAllByRole("heading")).toHaveLength(1)
      expect(screen.getByRole("button", { name: "Add" })).toBeEnabled()
      expect(mockApi.listEntities).toHaveBeenCalledWith(worldId, entityType)
    }
    await user.click(screen.getByRole("button", { name: "Close" }))
    expect(screen.queryByRole("table")).not.toBeInTheDocument()
  })

  it("uses the file editor for unmapped layers in read-only or editable mode", async () => {
    const user = userEvent.setup()
    renderLayers([layer("history", "library"), layer("magic")])
    await user.click(await screen.findByRole("button", { name: "View" }))

    expect(await screen.findByRole("textbox")).toHaveValue("description: Old lore")
    expect(screen.getByRole("textbox")).toHaveAttribute("readonly")
    expect(mockApi.getLayerFiles).toHaveBeenCalledWith(worldId, "history")
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument()
    // LayerEditor's icon-only close button has no accessible name.
    await user.click(screen.getByRole("button", { name: "" }))
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Edit" }))
    expect(await screen.findByRole("textbox")).not.toHaveAttribute("readonly")
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled()
    expect(mockApi.getLayerFiles).toHaveBeenCalledWith(worldId, "magic")
    expect(screen.getByText("magic")).toBeVisible()
  })

  it("disables all forks until the selected layer is forked and the manifest refreshed", async () => {
    const user = userEvent.setup()
    const fork = deferred<MessageResponse>()
    const refresh = deferred<WorldManifestResponse>()
    mockApi.forkLayer.mockReturnValue(fork.promise)
    renderLayers([layer("geography", "library"), layer("politics", "library")])
    const forks = await screen.findAllByRole("button", { name: "Fork" })
    mockApi.getWorldManifest.mockReturnValueOnce(refresh.promise)

    await user.click(forks[0])
    expect(mockApi.forkLayer).toHaveBeenCalledExactlyOnceWith(worldId, "geography")
    for (const button of forks) expect(button).toBeDisabled()
    await user.click(forks[1])
    expect(mockApi.forkLayer).toHaveBeenCalledTimes(1)

    await act(async () => fork.resolve({ message: "Forked" }))
    expect(mockApi.getWorldManifest).toHaveBeenLastCalledWith(worldId, "en")
    expect(mockApi.getWorldManifest).toHaveBeenCalledTimes(2)
    for (const button of forks) expect(button).toBeDisabled()
    await act(async () => {
      refresh.resolve(manifest([layer("geography"), layer("politics", "library")]))
    })

    expect(await screen.findByText("Custom")).toBeVisible()
    expect(screen.getByRole("button", { name: "Edit" })).toBeEnabled()
    expect(screen.getByRole("button", { name: "Fork" })).toBeEnabled()
    expect(screen.queryByText("Library: geography_template")).not.toBeInTheDocument()
  })

  it.each(["fork", "refresh"] as const)("shows an error when the %s request fails", async (failure) => {
    const user = userEvent.setup()
    mockApi.forkLayer.mockResolvedValue({ message: "Forked" })
    renderLayers([layer("geography", "library")])
    const forkButton = await screen.findByRole("button", { name: "Fork" })
    if (failure === "fork") {
      mockApi.forkLayer.mockRejectedValue(new Error("cannot fork"))
    } else {
      mockApi.getWorldManifest.mockRejectedValueOnce(new Error("cannot refresh"))
    }

    await user.click(forkButton)

    expect(await screen.findByText("Failed to fork layer")).toBeVisible()
    expect(mockApi.forkLayer).toHaveBeenCalledExactlyOnceWith(worldId, "geography")
    expect(mockApi.getWorldManifest).toHaveBeenCalledTimes(failure === "fork" ? 1 : 2)
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
  })

  it("opens and cancels the monster catalog, resetting it when another layer is opened", async () => {
    const user = userEvent.setup()
    renderLayers([layer("ecology"), layer("geography", "library")])
    await user.click(await screen.findByRole("button", { name: "Edit" }))
    await user.click(screen.getByRole("button", { name: "Pick from catalog" }))

    expect(await screen.findByText("Goblin")).toBeVisible()
    expect(mockApi.listCatalog).toHaveBeenCalledWith("monster_catalog")
    expect(mockApi.getSchema).toHaveBeenCalledWith("monster_catalog")
    await user.click(screen.getByRole("button", { name: "Cancel" }))
    expect(screen.queryByText("Goblin")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Pick from catalog" })).toBeEnabled()
    expect(mockApi.createEntity).not.toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: "Pick from catalog" }))
    await screen.findByText("Goblin")
    await user.click(screen.getByRole("button", { name: "View" }))
    expect(screen.queryByRole("heading", { name: "Pick from monster catalog" })).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Edit" }))
    expect(screen.getByRole("button", { name: "Pick from catalog" })).toBeVisible()
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument()
  })

  it("creates a picked monster and reloads the ecology lists after the zero-delay refresh", async () => {
    const user = userEvent.setup()
    const create = deferred<Record<string, unknown>>()
    mockApi.createEntity.mockReturnValue(create.promise)
    renderLayers([layer("ecology")])
    await user.click(await screen.findByRole("button", { name: "Edit" }))
    await screen.findAllByText("No entities")
    await user.click(screen.getByRole("button", { name: "Pick from catalog" }))
    await screen.findByText("Goblin")

    vi.useFakeTimers()
    fireEvent.click(screen.getByRole("button", { name: "Pick" }))
    expect(mockApi.createEntity).toHaveBeenCalledExactlyOnceWith(
      worldId, "monster_template", "goblin", { base: "goblin" },
    )
    expect(screen.getByRole("heading", { name: "Pick from monster catalog" })).toBeVisible()
    mockApi.listEntities.mockImplementation(async (_id, entityType) =>
      entityType === "monster_template" ? [{ id: "goblin", name: "Goblin" }] : [],
    )
    await act(async () => create.resolve({ id: "goblin" }))
    expect(screen.queryByRole("heading", { name: "Pick from monster catalog" })).not.toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "squads" })).not.toBeInTheDocument()

    await act(async () => { await vi.runOnlyPendingTimersAsync() })

    expect(screen.getByRole("heading", { name: "squads" })).toBeVisible()
    expect(screen.getByText("Goblin")).toBeVisible()
    expect(screen.getByRole("button", { name: "Pick from catalog" })).toBeEnabled()
    expect(mockApi.listEntities).toHaveBeenNthCalledWith(3, worldId, "squad")
    expect(mockApi.listEntities).toHaveBeenNthCalledWith(4, worldId, "monster_template")
  })

  // BUG: Catalog creation errors are swallowed; neither the inspector nor entity editor displays feedback.
  it.fails("shows an error when adding a catalog monster fails, while keeping the picker open", async () => {
    const user = userEvent.setup()
    mockApi.createEntity.mockRejectedValue(new Error("cannot create monster"))
    renderLayers([layer("ecology")])
    await user.click(await screen.findByRole("button", { name: "Edit" }))
    await user.click(screen.getByRole("button", { name: "Pick from catalog" }))
    await user.click(await screen.findByRole("button", { name: "Pick" }))

    await waitFor(() => {
      expect(mockApi.createEntity).toHaveBeenCalledExactlyOnceWith(
        worldId, "monster_template", "goblin", { base: "goblin" },
      )
    })
    expect(screen.getByRole("heading", { name: "Pick from monster catalog" })).toBeVisible()
    expect(screen.getByText(/failed|error|could not/i)).toBeVisible()
  })
})
