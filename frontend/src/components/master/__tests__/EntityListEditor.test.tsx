import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { EntityListEditor } from "../EntityListEditor"
import { api } from "@/transport/apiClient"

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      listEntities: vi.fn(),
      createEntity: vi.fn(),
      updateEntity: vi.fn(),
      deleteEntity: vi.fn(),
      getSchema: vi.fn(),
      getRefs: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api.master)

// Minimal NPC schema for tests
const npcSchema = {
  type: "object" as const,
  properties: {
    name: { type: "object" as const, title: "Name", additionalProperties: { type: "string" as const } },
    role: { type: "string" as const, title: "Role", enum: ["commoner", "guard"] },
    hp: { type: "integer" as const, title: "HP", default: 10 },
  },
  required: ["name"],
}

const npcEntities = [
  { id: "edgar", data: { name: { en: "Edgar" }, role: "guard", hp: 20 } },
  { id: "marta", data: { name: { en: "Marta" }, role: "commoner", hp: 10 } },
]

// ---------------------------------------------------------------------------

function setup(overrides: { readOnly?: boolean } = {}) {
  mockApi.getSchema.mockResolvedValue(npcSchema)
  mockApi.listEntities.mockResolvedValue(npcEntities)
  mockApi.getRefs.mockResolvedValue([])

  return render(
    <EntityListEditor
      worldId="test_world"
      entityType="npc"
      readOnly={overrides.readOnly ?? false}
    />,
  )
}

/** Wait for the form fields to appear after opening the inline editor. */
async function waitForForm() {
  // The SchemaForm needs a render cycle after the panel opens
  await waitFor(() => {
    expect(document.querySelector("form")).toBeInTheDocument()
  })
  // Wait for the labels/inputs to render (base-ui primitives)
  await waitFor(() => {
    expect(screen.getByText("Save")).toBeInTheDocument()
  })
}

describe("EntityListEditor", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("loads and shows entity table with id and name columns", async () => {
    setup()
    expect(await screen.findByText("edgar")).toBeInTheDocument()
    expect(screen.getByText("marta")).toBeInTheDocument()
    expect(mockApi.listEntities).toHaveBeenCalledWith("test_world", "npc")
    expect(mockApi.getSchema).toHaveBeenCalledWith("npc")
  })

  it("opens create panel on Add click and calls createEntity on save", async () => {
    const user = userEvent.setup()
    setup()
    await screen.findByText("edgar")

    await user.click(screen.getByRole("button", { name: /add/i }))
    await waitForForm()

    // Fill the ID field (plain Input, not inside SchemaForm)
    const idInput = screen.getByPlaceholderText("unique_id")
    await user.type(idInput, "new_npc")

    // Fill the Name field (localized text rendered as text input by SchemaForm)
    // Use getByRole to avoid label query issues with base-ui primitives
    const form = document.querySelector("form")!
    const textInputs = form.querySelectorAll<HTMLInputElement>("input[type='text'], input:not([type])")
    // First text input in form is "name" (localized text)
    const nameInput = textInputs[0]
    await user.type(nameInput, "New NPC")

    mockApi.createEntity.mockResolvedValue({ id: "new_npc", data: { name: { en: "New NPC" } } })
    mockApi.listEntities.mockResolvedValue([
      ...npcEntities,
      { id: "new_npc", data: { name: { en: "New NPC" } } },
    ])

    await user.click(screen.getByRole("button", { name: /save/i }))

    await waitFor(() => {
      expect(mockApi.createEntity).toHaveBeenCalledWith(
        "test_world",
        "npc",
        "new_npc",
        expect.objectContaining({ name: { en: "New NPC" } }),
      )
    })
  })

  it("opens edit panel on Edit click and calls updateEntity on save", async () => {
    const user = userEvent.setup()
    setup()
    await screen.findByText("edgar")

    const editButtons = screen.getAllByRole("button", { name: /edit/i })
    await user.click(editButtons[0])
    await waitForForm()

    // The form's first text input should be pre-filled with "Edgar"
    const form = document.querySelector("form")!
    const textInputs = form.querySelectorAll<HTMLInputElement>("input[type='text'], input:not([type])")
    const nameInput = textInputs[0]
    expect(nameInput.value).toBe("Edgar")

    await user.clear(nameInput)
    await user.type(nameInput, "Edgar the Bold")

    mockApi.updateEntity.mockResolvedValue({ id: "edgar", data: { name: { en: "Edgar the Bold" } } })

    await user.click(screen.getByRole("button", { name: /save/i }))

    await waitFor(() => {
      expect(mockApi.updateEntity).toHaveBeenCalledWith(
        "test_world",
        "npc",
        "edgar",
        expect.objectContaining({ name: { en: "Edgar the Bold" } }),
      )
    })
  })

  it("deletes entity after confirmation", async () => {
    const user = userEvent.setup()
    vi.spyOn(window, "confirm").mockReturnValue(true)

    setup()
    await screen.findByText("edgar")

    mockApi.deleteEntity.mockResolvedValue({ message: "deleted" })
    mockApi.listEntities.mockResolvedValue([npcEntities[1]])

    const deleteButtons = screen.getAllByRole("button", { name: /delete/i })
    await user.click(deleteButtons[0])

    await waitFor(() => {
      expect(mockApi.deleteEntity).toHaveBeenCalledWith("test_world", "npc", "edgar")
    })
  })

  it("does not delete when confirmation is cancelled", async () => {
    const user = userEvent.setup()
    vi.spyOn(window, "confirm").mockReturnValue(false)

    setup()
    await screen.findByText("edgar")

    const deleteButtons = screen.getAllByRole("button", { name: /delete/i })
    await user.click(deleteButtons[0])

    expect(mockApi.deleteEntity).not.toHaveBeenCalled()
  })

  it("hides add/edit/delete buttons in read-only mode", async () => {
    setup({ readOnly: true })
    await screen.findByText("edgar")

    expect(screen.queryByRole("button", { name: /add/i })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument()
  })
})
