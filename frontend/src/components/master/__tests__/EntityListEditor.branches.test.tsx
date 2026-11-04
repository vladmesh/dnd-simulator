import { act, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { api } from "@/transport/apiClient"
import type { EntityEntry, JsonSchema } from "@/types/api"
import { EntityListEditor } from "../EntityListEditor"

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      listEntities: vi.fn(),
      getSchema: vi.fn(),
      getRefs: vi.fn(),
      createEntity: vi.fn(),
      updateEntity: vi.fn(),
      deleteEntity: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api.master)
const schema: JsonSchema = {
  type: "object",
  properties: { name: { type: "string", title: "Name" } },
}
const entity = { id: "guard", data: { name: "Gatekeeper" } }

function setup(readOnly = false) {
  return render(
    <EntityListEditor worldId="test_world" entityType="npc" readOnly={readOnly} />,
  )
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

describe("EntityListEditor uncovered branches", () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mockApi.listEntities.mockResolvedValue([entity])
    mockApi.getSchema.mockResolvedValue(schema)
    mockApi.getRefs.mockResolvedValue([])
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("keeps the table and controls hidden until both initial requests finish", async () => {
    const entitiesRequest = deferred<EntityEntry[]>()
    const schemaRequest = deferred<JsonSchema>()
    mockApi.listEntities.mockReturnValue(entitiesRequest.promise)
    mockApi.getSchema.mockReturnValue(schemaRequest.promise)
    setup()

    expect(mockApi.listEntities).toHaveBeenCalledWith("test_world", "npc")
    expect(mockApi.getSchema).toHaveBeenCalledWith("npc")
    expect(screen.queryByRole("table")).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Add" })).not.toBeInTheDocument()
    expect(screen.queryByText("No entities")).not.toBeInTheDocument()

    await act(async () => { entitiesRequest.resolve([entity]) })
    expect(screen.queryByRole("table")).not.toBeInTheDocument()

    await act(async () => { schemaRequest.resolve(schema) })
    expect(await screen.findByRole("table")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Add" })).toBeEnabled()
  })

  it("renders fallback names for localized, flat, numeric, and unnamed entries", async () => {
    mockApi.listEntities.mockResolvedValue([
      { id: "french", data: { name: { fr: "Garde" } } },
      { id: "empty_translation", data: { name: {} } },
      { id: "blank_english", data: { name: { en: "", fr: "Ignored" } } },
      { id: "data_id", data: { id: "Fallback ID" } },
      { id: "flat", name: "Flat Name" },
      { id: "id_only", data: null },
      { id: "unnamed", data: {} },
      { id: "numeric", data: { name: 0 } },
      { id: "null_name", data: { name: null, id: "Null fallback" } },
    ])
    setup(true)

    await screen.findByRole("table")
    for (const name of ["french Garde", "data_id Fallback ID", "flat Flat Name", "id_only id_only", "numeric 0", "null_name Null fallback"]) {
      expect(screen.getByRole("row", { name })).toBeInTheDocument()
    }
    for (const id of ["empty_translation", "blank_english", "unnamed"]) {
      const row = screen.getByRole("row", { name: id })
      expect(within(row).getAllByRole("cell")[1]).toBeEmptyDOMElement()
    }
  })

  it.each(["listEntities", "getSchema"] as const)(
    "shows a load error when %s fails and recovers on a prop change",
    async (method) => {
      mockApi[method].mockRejectedValueOnce(new Error("unavailable"))
      const { rerender } = setup()

      expect(await screen.findByText("Failed to load entities")).toBeInTheDocument()
      expect(screen.queryByRole("table")).not.toBeInTheDocument()
      expect(screen.queryByRole("button", { name: "Add" })).not.toBeInTheDocument()

      rerender(<EntityListEditor worldId="other_world" entityType="monster" readOnly={false} />)

      expect(await screen.findByText("Gatekeeper")).toBeInTheDocument()
      expect(screen.queryByText("Failed to load entities")).not.toBeInTheDocument()
      expect(mockApi.listEntities).toHaveBeenLastCalledWith("other_world", "monster")
      expect(mockApi.getSchema).toHaveBeenLastCalledWith("monster")
    },
  )

  it.each([false, true])("shows an empty table with readOnly=%s", async (readOnly) => {
    mockApi.listEntities.mockResolvedValue([])
    setup(readOnly)

    expect(await screen.findByRole("cell", { name: "No entities" })).toBeInTheDocument()
    expect(screen.getAllByRole("row")).toHaveLength(2)
    expect(screen.getAllByRole("columnheader")).toHaveLength(readOnly ? 2 : 3)
    if (readOnly) {
      expect(screen.queryByRole("button")).not.toBeInTheDocument()
    } else {
      expect(screen.getByRole("button", { name: "Add" })).toBeEnabled()
      expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument()
      expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument()
    }
  })

  it("retains create inputs after an error and clears the error after a successful retry", async () => {
    const user = userEvent.setup()
    mockApi.createEntity.mockRejectedValueOnce(new Error("Create denied"))
    setup()
    await user.click(await screen.findByRole("button", { name: "Add" }))
    await user.type(screen.getByRole("textbox", { name: "ID" }), "new_guard")
    await user.type(screen.getByRole("textbox", { name: "Name" }), "New Guard")
    await user.click(screen.getByRole("button", { name: "Save" }))

    expect(await screen.findByText("Error: Create denied")).toBeInTheDocument()
    expect(screen.getByRole("textbox", { name: "ID" })).toHaveValue("new_guard")
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue("New Guard")
    expect(mockApi.createEntity).toHaveBeenCalledWith("test_world", "npc", "new_guard", { name: "New Guard" })
    expect(mockApi.listEntities).toHaveBeenCalledTimes(1)

    const created = { id: "new_guard", data: { name: "New Guard" } }
    mockApi.createEntity.mockResolvedValueOnce(created)
    mockApi.listEntities.mockResolvedValueOnce([entity, created])
    await user.click(screen.getByRole("button", { name: "Save" }))

    expect(await screen.findByText("New Guard")).toBeInTheDocument()
    expect(screen.queryByText("Error: Create denied")).not.toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "Add npc" })).not.toBeInTheDocument()
    expect(mockApi.createEntity).toHaveBeenCalledTimes(2)
    expect(mockApi.updateEntity).not.toHaveBeenCalled()
  })

  it("shows an update error without replacing the row or discarding the edited value", async () => {
    const user = userEvent.setup()
    mockApi.updateEntity.mockRejectedValueOnce(new Error("Update denied"))
    setup()
    await user.click(await screen.findByRole("button", { name: "Edit" }))
    const name = screen.getByRole("textbox", { name: "Name" })
    await user.clear(name)
    await user.type(name, "Changed Guard")
    await user.click(screen.getByRole("button", { name: "Save" }))

    expect(await screen.findByText("Error: Update denied")).toBeInTheDocument()
    expect(screen.getByText("Gatekeeper")).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Edit guard" })).toBeInTheDocument()
    expect(name).toHaveValue("Changed Guard")
    expect(mockApi.updateEntity).toHaveBeenCalledWith("test_world", "npc", "guard", { name: "Changed Guard" })
    expect(mockApi.createEntity).not.toHaveBeenCalled()
    expect(mockApi.listEntities).toHaveBeenCalledTimes(1)
  })

  it("keeps a row after a delete error and clears the error on retry", async () => {
    const user = userEvent.setup()
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true)
    mockApi.deleteEntity.mockRejectedValueOnce(new Error("Delete denied"))
    setup()
    await user.click(await screen.findByRole("button", { name: "Delete" }))

    expect(await screen.findByText("Error: Delete denied")).toBeInTheDocument()
    expect(screen.getByText("Gatekeeper")).toBeInTheDocument()
    expect(confirm).toHaveBeenCalledWith("Delete guard?")
    expect(mockApi.deleteEntity).toHaveBeenCalledWith("test_world", "npc", "guard")
    expect(mockApi.listEntities).toHaveBeenCalledTimes(1)

    mockApi.deleteEntity.mockResolvedValueOnce({ message: "deleted" })
    mockApi.listEntities.mockResolvedValueOnce([])
    await user.click(screen.getByRole("button", { name: "Delete" }))

    expect(await screen.findByText("No entities")).toBeInTheDocument()
    expect(screen.queryByText("Error: Delete denied")).not.toBeInTheDocument()
    expect(screen.queryByText("Gatekeeper")).not.toBeInTheDocument()
    expect(mockApi.deleteEntity).toHaveBeenCalledTimes(2)
  })

  it("closes an unsaved create panel and resets its ID when reopened", async () => {
    const user = userEvent.setup()
    setup()
    await user.click(await screen.findByRole("button", { name: "Add" }))
    await user.type(screen.getByRole("textbox", { name: "ID" }), "discarded")
    await user.type(screen.getByRole("textbox", { name: "Name" }), "Unsaved")
    // The icon-only close button currently has no accessible name.
    await user.click(screen.getByRole("button", { name: "" }))

    expect(screen.queryByRole("heading", { name: "Add npc" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument()
    expect(mockApi.createEntity).not.toHaveBeenCalled()
    expect(mockApi.updateEntity).not.toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: "Add" }))
    expect(screen.getByRole("textbox", { name: "ID" })).toHaveValue("")
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue("")
  })

  it("reports a failed refresh after a successful deletion alongside the previous table", async () => {
    const user = userEvent.setup()
    vi.spyOn(window, "confirm").mockReturnValue(true)
    mockApi.deleteEntity.mockResolvedValueOnce({ message: "deleted" })
    setup()
    await screen.findByText("Gatekeeper")
    mockApi.listEntities.mockRejectedValueOnce(new Error("Refresh unavailable"))
    await user.click(screen.getByRole("button", { name: "Delete" }))

    expect(await screen.findByText("Failed to load entities")).toBeInTheDocument()
    expect(screen.getByRole("table")).toBeInTheDocument()
    expect(screen.getByText("Gatekeeper")).toBeInTheDocument()
    expect(mockApi.deleteEntity).toHaveBeenCalledWith("test_world", "npc", "guard")
    await waitFor(() => { expect(mockApi.listEntities).toHaveBeenCalledTimes(2) })
  })
})
