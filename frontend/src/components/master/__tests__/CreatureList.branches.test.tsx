import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { api } from "@/transport/apiClient"
import type { CreatureResponse, MessageResponse } from "@/types/api"
import i18n from "@/i18n"
import { CreatureList } from "../CreatureList"

vi.mock("@/transport/apiClient", async (importOriginal) => {
  const { ApiError } = await importOriginal<typeof import("@/transport/apiClient")>()
  return {
    ApiError,
    api: {
      master: {
        getCreatures: vi.fn(),
        deleteCreature: vi.fn(),
        setBrain: vi.fn(),
        patchCreature: vi.fn(),
        spawnCreature: vi.fn(),
        setCreatureActivation: vi.fn(),
        setActivationTrigger: vi.fn(),
      },
    },
  }
})

const toastMock = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }))
vi.mock("sonner", () => ({ toast: toastMock }))

const mockApi = vi.mocked(api.master)

function makeCreature(overrides: Partial<CreatureResponse> = {}): CreatureResponse {
  return {
    id: "goblin_1",
    name: "Goblin",
    location_id: "tavern",
    active: true,
    hp: 10,
    max_hp: 10,
    ac: 12,
    entity_type: "npc",
    ai_type: "rule_based",
    gm_activation_override: "automatic",
    activation_triggers: [],
    ...overrides,
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

function creatureRow(name = "Goblin") {
  return screen.getByRole("row", { name: new RegExp(name) })
}

// Delete is icon-only; scope its unnamed button to the creature's visible row.
function deleteButton(name = "Goblin") {
  return within(creatureRow(name)).getByRole("button", { name: "" })
}

describe("CreatureList — uncovered branches", () => {
  beforeEach(async () => {
    vi.resetAllMocks()
    await i18n.changeLanguage("en")
    mockApi.getCreatures.mockResolvedValue([makeCreature()])
  })

  afterEach(() => { vi.restoreAllMocks() })

  it("shows table headings while loading, then replaces the table with the empty state", async () => {
    const request = deferred<CreatureResponse[]>()
    mockApi.getCreatures.mockReturnValue(request.promise)

    render(<CreatureList sessionId="sess-1" />)

    const table = screen.getByRole("table")
    for (const name of ["Name", "Type", "HP", "AC", "Location", "AI", "Active", "Actions"]) {
      expect(within(table).getByRole("columnheader", { name })).toBeInTheDocument()
    }
    expect(screen.queryByText("No creatures.")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Spawn Creature" })).toBeEnabled()
    expect(mockApi.getCreatures).toHaveBeenCalledWith("sess-1", undefined)

    await act(async () => { request.resolve([]) })

    expect(await screen.findByText("No creatures.")).toBeInTheDocument()
    expect(screen.queryByRole("table")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "NPC" })).toBeEnabled()
  })

  it("requests NPC, monster and all filters and renders server data and missing-field defaults", async () => {
    const user = userEvent.setup()
    const npc = makeCreature({ entity_type: undefined, ai_type: undefined })
    const monster = makeCreature({
      id: "ogre_1", name: "Ogre", entity_type: "monster", hp: 7, max_hp: 30,
      ac: 15, location_id: "cave", ai_type: "llm",
    })
    mockApi.getCreatures
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([npc])
      .mockResolvedValueOnce([monster])
      .mockResolvedValueOnce([npc, monster])

    render(<CreatureList sessionId="sess-1" />)
    await screen.findByText("No creatures.")

    await user.click(screen.getByRole("button", { name: "NPC" }))
    await screen.findByRole("button", { name: "Goblin" })
    expect(mockApi.getCreatures).toHaveBeenLastCalledWith("sess-1", { entity_type: "npc" })
    const npcCells = within(creatureRow())
    expect(npcCells.getByRole("cell", { name: "npc" })).toBeInTheDocument()
    expect(npcCells.getByRole("cell", { name: "10/10" })).toBeInTheDocument()
    expect(npcCells.getByRole("cell", { name: "12" })).toBeInTheDocument()
    expect(npcCells.getByRole("cell", { name: "tavern" })).toBeInTheDocument()
    expect(npcCells.getByRole("button", { name: "rule_based" })).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Monster" }))
    await screen.findByRole("button", { name: "Ogre" })
    expect(mockApi.getCreatures).toHaveBeenLastCalledWith("sess-1", { entity_type: "monster" })
    const monsterCells = within(creatureRow("Ogre"))
    for (const name of ["monster", "7/30", "15", "cave"]) {
      expect(monsterCells.getByRole("cell", { name })).toBeInTheDocument()
    }
    expect(screen.queryByRole("button", { name: "Goblin" })).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "All" }))
    await screen.findByRole("button", { name: "Goblin" })
    expect(screen.getByRole("button", { name: "Ogre" })).toBeInTheDocument()
    expect(mockApi.getCreatures).toHaveBeenLastCalledWith("sess-1", undefined)
    expect(mockApi.getCreatures).toHaveBeenCalledTimes(4)
  })

  it("does not delete or refresh when the confirmation is cancelled", async () => {
    const user = userEvent.setup()
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false)
    render(<CreatureList sessionId="sess-1" />)
    await screen.findByRole("button", { name: "Goblin" })

    await user.click(deleteButton())

    expect(confirm).toHaveBeenCalledWith("Delete Goblin?")
    expect(mockApi.deleteCreature).not.toHaveBeenCalled()
    expect(mockApi.getCreatures).toHaveBeenCalledTimes(1)
    expect(screen.getByRole("button", { name: "Goblin" })).toBeInTheDocument()
    expect(deleteButton()).toBeEnabled()
    expect(toastMock.success).not.toHaveBeenCalled()
  })

  it("disables only the creature being deleted and refreshes after a successful deletion", async () => {
    const user = userEvent.setup()
    vi.spyOn(window, "confirm").mockReturnValue(true)
    const request = deferred<MessageResponse>()
    const guard = makeCreature({ id: "guard_1", name: "Guard" })
    mockApi.getCreatures.mockResolvedValueOnce([makeCreature(), guard]).mockResolvedValue([guard])
    mockApi.deleteCreature.mockReturnValue(request.promise)
    render(<CreatureList sessionId="sess-1" />)
    await screen.findByRole("button", { name: "Goblin" })

    await user.click(deleteButton())

    expect(mockApi.deleteCreature).toHaveBeenCalledWith("sess-1", "goblin_1")
    expect(deleteButton()).toBeDisabled()
    expect(deleteButton("Guard")).toBeEnabled()
    expect(mockApi.getCreatures).toHaveBeenCalledTimes(1)
    await user.click(deleteButton())
    expect(mockApi.deleteCreature).toHaveBeenCalledTimes(1)

    await act(async () => { request.resolve({ message: "Deleted" }) })

    await waitFor(() => expect(screen.queryByRole("button", { name: "Goblin" })).not.toBeInTheDocument())
    expect(screen.getByRole("button", { name: "Guard" })).toBeInTheDocument()
    expect(mockApi.getCreatures).toHaveBeenLastCalledWith("sess-1", undefined)
    expect(mockApi.getCreatures).toHaveBeenCalledTimes(2)
    expect(toastMock.success).toHaveBeenCalledWith("Delete")
    expect(toastMock.error).not.toHaveBeenCalled()
  })

  it("reports deletion failure, keeps the creature, and re-enables deletion", async () => {
    const user = userEvent.setup()
    vi.spyOn(window, "confirm").mockReturnValue(true)
    const request = deferred<MessageResponse>()
    mockApi.deleteCreature.mockReturnValue(request.promise)
    render(<CreatureList sessionId="sess-1" />)
    await screen.findByRole("button", { name: "Goblin" })

    await user.click(deleteButton())
    expect(deleteButton()).toBeDisabled()
    await act(async () => { request.reject(new Error("Delete unavailable")) })

    await waitFor(() => expect(deleteButton()).toBeEnabled())
    expect(mockApi.deleteCreature).toHaveBeenCalledWith("sess-1", "goblin_1")
    expect(toastMock.error).toHaveBeenCalledWith(i18n.t("common:error"))
    expect(toastMock.success).not.toHaveBeenCalled()
    expect(screen.getByRole("button", { name: "Goblin" })).toBeInTheDocument()
    expect(mockApi.getCreatures).toHaveBeenCalledTimes(1)
  })

  it("switches an LLM brain back to rule-based and displays the refreshed brain", async () => {
    const user = userEvent.setup()
    mockApi.getCreatures.mockResolvedValueOnce([makeCreature({ ai_type: "llm" })])
    mockApi.setBrain.mockResolvedValue({ message: "Brain set", brain_type: "rule_based" })
    render(<CreatureList sessionId="sess-1" />)

    await user.click(await screen.findByRole("button", { name: "llm" }))

    expect(mockApi.setBrain).toHaveBeenCalledWith("sess-1", "goblin_1", { type: "rule_based" })
    expect(await screen.findByRole("button", { name: "rule_based" })).toBeInTheDocument()
    expect(mockApi.getCreatures).toHaveBeenCalledTimes(2)
    expect(mockApi.getCreatures).toHaveBeenLastCalledWith("sess-1", undefined)
  })

  it("reports a brain API failure without refreshing or changing the fallback brain", async () => {
    const user = userEvent.setup()
    mockApi.getCreatures.mockResolvedValue([makeCreature({ ai_type: undefined })])
    mockApi.setBrain.mockRejectedValue(new Error("Brain unavailable"))
    render(<CreatureList sessionId="sess-1" />)

    await user.click(await screen.findByRole("button", { name: "rule_based" }))

    expect(mockApi.setBrain).toHaveBeenCalledWith("sess-1", "goblin_1", { type: "llm" })
    await waitFor(() => expect(toastMock.error).toHaveBeenCalledWith(i18n.t("common:error")))
    expect(screen.getByRole("button", { name: "rule_based" })).toBeInTheDocument()
    expect(mockApi.getCreatures).toHaveBeenCalledTimes(1)
    expect(toastMock.success).not.toHaveBeenCalled()
    expect(toastMock.warning).not.toHaveBeenCalled()
  })

  it("opens the selected creature for editing, saves it, closes the form and refreshes", async () => {
    mockApi.getCreatures.mockResolvedValueOnce([makeCreature()]).mockResolvedValue([makeCreature({ hp: 6 })])
    mockApi.patchCreature.mockResolvedValue({ message: "Updated" })
    render(<CreatureList sessionId="sess-1" />)

    fireEvent.click(await screen.findByRole("button", { name: "Goblin" }))
    const dialog = screen.getByRole("dialog", { name: "Edit Creature" })
    expect(within(dialog).getByDisplayValue("Goblin")).toBeDisabled()
    const hp = within(dialog).getByRole("spinbutton", { name: "Current HP" })
    expect(hp).toHaveValue(10)
    fireEvent.change(hp, { target: { value: "6" } })
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }))

    expect(mockApi.patchCreature).toHaveBeenCalledWith("sess-1", "goblin_1", {
      current_hp: 6, max_hp: 10, ac: 12, location_id: "tavern",
      gold: 0, personality: null, conditions: [],
    })
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    expect(await screen.findByRole("cell", { name: "6/10" })).toBeInTheDocument()
    expect(mockApi.getCreatures).toHaveBeenCalledTimes(2)
    expect(toastMock.success).toHaveBeenCalledWith("Creature updated.")
  })

  it("closes an edit without refreshing and opens a fresh spawn form with saving disabled", async () => {
    render(<CreatureList sessionId="sess-1" />)

    fireEvent.click(await screen.findByRole("button", { name: "Goblin" }))
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Spawn Creature" }))
    const dialog = screen.getByRole("dialog", { name: "Spawn Creature" })
    expect(within(dialog).queryByDisplayValue("Goblin")).not.toBeInTheDocument()
    expect(within(dialog).getByRole("button", { name: "Spawn Creature" })).toBeDisabled()
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }))

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(mockApi.getCreatures).toHaveBeenCalledTimes(1)
    expect(mockApi.patchCreature).not.toHaveBeenCalled()
    expect(mockApi.spawnCreature).not.toHaveBeenCalled()
  })
})
