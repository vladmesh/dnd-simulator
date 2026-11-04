import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { Toaster } from "sonner"
import { api, ApiError } from "@/transport/apiClient"
import type { CreatureResponse, MessageResponse } from "@/types/api"
import i18n from "@/i18n"
import { CreatureForm } from "../CreatureForm"

vi.mock("@/transport/apiClient", async () => {
  const { ApiError } = await vi.importActual<typeof import("@/transport/apiClient")>("@/transport/apiClient")
  return {
    ApiError,
    api: {
      master: {
        patchCreature: vi.fn(),
        spawnCreature: vi.fn(),
        getCreature: vi.fn(),
        giveItem: vi.fn(),
      },
    },
  }
})

const mockApi = vi.mocked(api.master)

function makeCreature(overrides: Partial<CreatureResponse> = {}): CreatureResponse {
  return {
    id: "goblin_1",
    name: "Goblin",
    location_id: "tavern",
    active: true,
    hp: 8,
    max_hp: 10,
    ac: 12,
    entity_type: "monster",
    ai_type: "rule_based",
    gold: 5,
    role: "guard",
    personality: "aggressive",
    settlement_id: "town_1",
    conditions: [],
    inventory: [],
    gm_activation_override: "automatic",
    activation_triggers: [],
    ...overrides,
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

function renderForm(creature: CreatureResponse | null = null) {
  const onClose = vi.fn()
  const onSaved = vi.fn()
  render(
    <>
      <CreatureForm sessionId="sess-1" creature={creature} onClose={onClose} onSaved={onSaved} />
      <Toaster />
    </>,
  )
  return { onClose, onSaved }
}

function change(input: HTMLElement, value: string) {
  fireEvent.change(input, { target: { value } })
}

// Most labels are not associated with their inputs; follow the existing test's
// role-based ordering for those controls rather than depending on CSS or markup.
describe("CreatureForm — remaining branches", () => {
  beforeEach(async () => {
    vi.resetAllMocks()
    await i18n.changeLanguage("en")
  })

  it("starts with an empty, disabled spawn form and submits the edited fields only once while saving", async () => {
    const pending = deferred<CreatureResponse>()
    mockApi.spawnCreature.mockReturnValue(pending.promise)
    const { onSaved, onClose } = renderForm()
    const spawn = screen.getByRole("button", { name: "Spawn Creature" })
    const [id, name, location, personality, settlement] = screen.getAllByRole("textbox")
    const [hp, ac, speed, gold] = screen.getAllByRole("spinbutton")
    const [kind, brain] = screen.getAllByRole("combobox")

    expect(screen.getByRole("dialog", { name: "Spawn Creature" })).toBeVisible()
    expect(spawn).toBeDisabled()
    expect(id).toHaveValue("")
    expect(hp).toHaveValue(10)
    expect(ac).toHaveValue(10)
    expect(speed).toHaveValue(30)
    expect(gold).toHaveValue(0)
    expect(kind).toHaveValue("npc")
    expect(brain).toHaveValue("rule_based")
    expect(screen.queryByRole("spinbutton", { name: "Max HP" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Give Item" })).not.toBeInTheDocument()
    expect(mockApi.getCreature).not.toHaveBeenCalled()
    fireEvent.click(spawn)
    expect(mockApi.spawnCreature).not.toHaveBeenCalled()

    change(id, "wolf_1")
    expect(spawn).toBeEnabled()
    change(name, "Wolf")
    change(kind, "monster")
    change(brain, "llm")
    change(hp, "24")
    change(ac, "14")
    change(speed, "40")
    change(location, "forest")
    change(personality, "wary")
    change(settlement, "village")
    fireEvent.click(spawn)

    expect(mockApi.spawnCreature).toHaveBeenCalledExactlyOnceWith("sess-1", {
      id: "wolf_1", name: "Wolf", entity_type: "monster", hp: 24, ac: 14,
      speed: 40, start_location: "forest", role: "commoner", personality: "wary",
      settlement_id: "village", ai: "llm",
    })
    expect(spawn).toBeDisabled()
    expect(onSaved).not.toHaveBeenCalled()
    fireEvent.click(spawn)
    expect(mockApi.spawnCreature).toHaveBeenCalledTimes(1)

    await act(async () => { pending.resolve(makeCreature()) })
    expect(await screen.findByText("Creature spawned.")).toBeVisible()
    expect(onSaved).toHaveBeenCalledTimes(1)
    expect(onClose).not.toHaveBeenCalled()
    expect(spawn).toBeEnabled()
  })

  it("uses zero for cleared spawn numeric fields and preserves empty optional strings", async () => {
    mockApi.spawnCreature.mockResolvedValue(makeCreature())
    renderForm()
    change(screen.getAllByRole("textbox")[0], "empty_npc")
    for (const input of screen.getAllByRole("spinbutton")) {
      change(input, "")
      expect(input).toHaveValue(0)
    }
    fireEvent.click(screen.getByRole("button", { name: "Spawn Creature" }))
    expect(mockApi.spawnCreature).toHaveBeenCalledExactlyOnceWith("sess-1", {
      id: "empty_npc", name: "", entity_type: "npc", hp: 0, ac: 0, speed: 0,
      start_location: "", role: "commoner", personality: "", settlement_id: "", ai: "rule_based",
    })
    expect(await screen.findByText("Creature spawned.")).toBeVisible()
  })

  it("renders equipped inventory, locks identity fields, and saves changed details and toggled conditions", async () => {
    mockApi.patchCreature.mockResolvedValue({ message: "ok" })
    const { onSaved } = renderForm(makeCreature({
      conditions: ["poisoned", "blinded"],
      inventory: [{ id: "potion_1", name: "Healing draught", item_type: "potion" }],
      equipped_weapon: { weapon_id: "sword", attack_name: "Slash", damage: "1d8" },
    }))
    expect(screen.getByRole("dialog", { name: "Edit Creature" })).toBeVisible()
    const [name, location, personality] = screen.getAllByRole("textbox")
    expect(name).toHaveValue("Goblin")
    expect(name).toBeDisabled()
    expect(screen.getByRole("combobox", { name: "Role" })).toBeDisabled()
    expect(location).toHaveValue("tavern")
    expect(personality).toHaveValue("aggressive")
    expect(screen.getByText("Healing draught")).toBeVisible()
    expect(screen.getByText("Slash (1d8)")).toBeVisible()
    expect(screen.queryByText("No items.")).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Spawn Creature" })).not.toBeInTheDocument()

    change(location, "keep")
    change(personality, "friendly")
    const [, , ac, gold] = screen.getAllByRole("spinbutton")
    change(ac, "16")
    change(gold, "27")
    fireEvent.click(screen.getByRole("button", { name: "Poisoned" }))
    fireEvent.click(screen.getByRole("button", { name: "Stunned" }))
    fireEvent.click(screen.getByRole("button", { name: "Save" }))
    expect(mockApi.patchCreature).toHaveBeenCalledExactlyOnceWith("sess-1", "goblin_1", {
      current_hp: 8, max_hp: 10, ac: 16, gold: 27, location_id: "keep",
      personality: "friendly", conditions: ["blinded", "stunned"],
    })
    expect(await screen.findByText("Creature updated.")).toBeVisible()
    expect(onSaved).toHaveBeenCalledTimes(1)
  })

  it("handles missing optional creature data and clears edit fields to their minimum or null values", async () => {
    mockApi.patchCreature.mockResolvedValue({ message: "ok" })
    renderForm(makeCreature({
      inventory: undefined, conditions: undefined, gold: undefined,
      role: undefined, settlement_id: undefined, entity_type: "container", ai_type: "legacy",
    }))
    expect(screen.getByText("No items.")).toBeVisible()
    expect(screen.queryByText("Equipped weapon:")).not.toBeInTheDocument()
    expect(screen.getByRole("combobox", { name: "Role" })).toHaveValue("commoner")
    const [, location, personality] = screen.getAllByRole("textbox")
    change(location, "")
    change(personality, "")
    const [hp, maxHp, ac, gold] = screen.getAllByRole("spinbutton")
    change(hp, "")
    change(maxHp, "")
    change(ac, "")
    change(gold, "")
    expect(maxHp).toHaveValue(1)
    expect(gold).toHaveValue(0)
    fireEvent.click(screen.getByRole("button", { name: "Save" }))
    expect(mockApi.patchCreature).toHaveBeenCalledExactlyOnceWith("sess-1", "goblin_1", {
      current_hp: 0, max_hp: 1, ac: 0, gold: 0,
      location_id: null, personality: null, conditions: [],
    })
    expect(await screen.findByText("Creature updated.")).toBeVisible()
  })

  it("shows API error details, clears the error on retry, and restores saving after failure", async () => {
    const retry = deferred<MessageResponse>()
    mockApi.patchCreature
      .mockRejectedValueOnce(new ApiError(422, { detail: "Creature is unavailable" }))
      .mockReturnValueOnce(retry.promise)
    const { onSaved, onClose } = renderForm(makeCreature())
    const save = screen.getByRole("button", { name: "Save" })
    fireEvent.click(save)
    expect(await screen.findByText("Creature is unavailable")).toBeVisible()
    expect(save).toBeEnabled()
    expect(onSaved).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
    expect(screen.queryByText("Creature updated.")).not.toBeInTheDocument()

    fireEvent.click(save)
    expect(screen.queryByText("Creature is unavailable")).not.toBeInTheDocument()
    expect(save).toBeDisabled()
    await act(async () => { retry.resolve({ message: "ok" }) })
    expect(await screen.findByText("Creature updated.")).toBeVisible()
    expect(onSaved).toHaveBeenCalledTimes(1)
    expect(mockApi.patchCreature).toHaveBeenCalledTimes(2)
    expect(save).toBeEnabled()
  })

  it.each([
    { error: new Error("Spawn failed"), message: "Spawn failed" },
    { error: "Service unavailable", message: "Service unavailable" },
  ])("shows non-API spawn failures: $message", async ({ error, message }) => {
    mockApi.spawnCreature.mockRejectedValue(error)
    const { onSaved } = renderForm()
    change(screen.getAllByRole("textbox")[0], "new_npc")
    const spawn = screen.getByRole("button", { name: "Spawn Creature" })
    fireEvent.click(spawn)
    expect(await screen.findByText(message)).toBeVisible()
    expect(spawn).toBeEnabled()
    expect(onSaved).not.toHaveBeenCalled()
    expect(screen.queryByText("Creature spawned.")).not.toBeInTheDocument()
  })

  it.each(["Cancel", "Close"])("dismisses with %s without saving", (name) => {
    const { onClose, onSaved } = renderForm()
    fireEvent.click(screen.getByRole("button", { name }))
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(onSaved).not.toHaveBeenCalled()
    expect(mockApi.spawnCreature).not.toHaveBeenCalled()
    expect(mockApi.patchCreature).not.toHaveBeenCalled()
  })

  it("cancels giving an item without closing the form, then refreshes inventory after a successful gift", async () => {
    const refresh = deferred<CreatureResponse>()
    mockApi.giveItem.mockResolvedValue({ item_id: "potion_1", name: "Healing draught" })
    mockApi.getCreature.mockReturnValue(refresh.promise)
    const { onClose, onSaved } = renderForm(makeCreature({ inventory: [] }))
    expect(screen.getByText("No items.")).toBeVisible()
    fireEvent.click(screen.getByRole("button", { name: "Give Item" }))
    let gift = screen.getByRole("dialog", { name: "Give Item" })
    fireEvent.click(within(gift).getByRole("button", { name: "Cancel" }))
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Give Item" })).not.toBeInTheDocument())
    expect(screen.getByRole("dialog", { name: "Edit Creature" })).toBeVisible()
    expect(onClose).not.toHaveBeenCalled()
    expect(mockApi.getCreature).not.toHaveBeenCalled()
    expect(mockApi.giveItem).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole("button", { name: "Give Item" }))
    gift = screen.getByRole("dialog", { name: "Give Item" })
    expect(within(gift).getByRole("button", { name: "Give Item" })).toBeDisabled()
    fireEvent.click(within(gift).getByRole("button", { name: "Potion" }))
    change(within(gift).getAllByRole("textbox")[0], "Healing draught")
    fireEvent.click(within(gift).getByRole("button", { name: "Give Item" }))
    expect(mockApi.giveItem).toHaveBeenCalledExactlyOnceWith("sess-1", "goblin_1", {
      name: "Healing draught", type: "potion", heal_dice: "2d4+2",
    })
    await waitFor(() => expect(mockApi.getCreature).toHaveBeenCalledExactlyOnceWith("sess-1", "goblin_1"))
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Give Item" })).not.toBeInTheDocument())
    expect(screen.getByText("No items.")).toBeVisible()
    await act(async () => {
      refresh.resolve(makeCreature({
        inventory: [{ id: "potion_1", name: "Healing draught", item_type: "potion" }],
        equipped_weapon: { weapon_id: "spear", attack_name: "Thrust", damage: "1d6" },
      }))
    })
    expect(await screen.findByText("Healing draught")).toBeVisible()
    expect(screen.getByText("Thrust (1d6)")).toBeVisible()
    expect(screen.queryByText("No items.")).not.toBeInTheDocument()
    expect(onSaved).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
  })
})
