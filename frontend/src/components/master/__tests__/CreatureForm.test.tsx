import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { api } from "@/transport/apiClient"
import type { CreatureResponse } from "@/types/api"
import i18n from "@/i18n"

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      patchCreature: vi.fn(),
      spawnCreature: vi.fn(),
      getCreature: vi.fn(),
    },
  },
}))

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
    conditions: [],
    entity_type: "monster",
    ai_type: "rule_based",
    gold: 5,
    role: "guard",
    personality: "aggressive",
    settlement_id: "town_1",
    gm_activation_override: "automatic",
    activation_triggers: [],
    ...overrides,
  }
}

describe("CreatureForm — HP current/max fields", () => {
  beforeEach(async () => { vi.clearAllMocks(); await i18n.changeLanguage("en") })

  it("shows separate current_hp and max_hp inputs in edit mode", async () => {
    const { CreatureForm } = await import("../CreatureForm")
    const creature = makeCreature({ hp: 8, max_hp: 10 })

    render(
      <CreatureForm
        sessionId="sess-1"
        creature={creature}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    )

    const currentHpInput = screen.getByLabelText(/current.*hp/i)
    const maxHpInput = screen.getByLabelText(/max.*hp/i)

    expect(currentHpInput).toBeTruthy()
    expect(maxHpInput).toBeTruthy()
    expect(currentHpInput).toHaveValue(8)
    expect(maxHpInput).toHaveValue(10)
  })

  it("submits both current_hp and max_hp in patch payload", async () => {
    const user = userEvent.setup()
    const { CreatureForm } = await import("../CreatureForm")
    const creature = makeCreature({ hp: 8, max_hp: 10 })
    mockApi.patchCreature.mockResolvedValue({ message: "ok" })

    render(
      <CreatureForm
        sessionId="sess-1"
        creature={creature}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    )

    const currentHpInput = screen.getByLabelText(/current.*hp/i)
    const maxHpInput = screen.getByLabelText(/max.*hp/i)

    await user.tripleClick(currentHpInput)
    await user.keyboard("5")
    await user.tripleClick(maxHpInput)
    await user.keyboard("12")

    const saveButton = screen.getByRole("button", { name: /save/i })
    await user.click(saveButton)

    const call = mockApi.patchCreature.mock.calls[0]
    expect(call[0]).toBe("sess-1")
    expect(call[1]).toBe("goblin_1")
    expect(call[2]).toMatchObject({ current_hp: 5, max_hp: 12 })
  })
})

describe("CreatureForm — spawn role", () => {
  beforeEach(async () => { vi.clearAllMocks(); await i18n.changeLanguage("en") })

  it("offers every supported NPC role with friendly labels", async () => {
    const { CreatureForm } = await import("../CreatureForm")

    render(
      <CreatureForm
        sessionId="sess-1"
        creature={null}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    )

    const role = screen.getByLabelText("Role")
    expect(role).toHaveValue("commoner")
    expect(screen.getByRole("option", { name: "Commoner" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "Blacksmith" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "Tavern Keeper" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "Guard" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "Merchant" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "Farmer" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "Gladiator" })).toBeInTheDocument()
  })

  it("submits the selected enum value", async () => {
    const user = userEvent.setup()
    const { CreatureForm } = await import("../CreatureForm")
    mockApi.spawnCreature.mockResolvedValue(makeCreature({ id: "innkeeper_1", role: "tavern_keeper" }))

    render(
      <CreatureForm
        sessionId="sess-1"
        creature={null}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    )

    await user.type(screen.getAllByRole("textbox")[0], "innkeeper_1")
    await user.selectOptions(screen.getByLabelText("Role"), "tavern_keeper")
    await user.click(screen.getByRole("button", { name: /spawn/i }))

    expect(mockApi.spawnCreature).toHaveBeenCalledWith(
      "sess-1",
      expect.objectContaining({ role: "tavern_keeper" }),
    )
  })
})

describe("CreatureForm — condition translations", () => {
  beforeEach(async () => { vi.clearAllMocks(); await i18n.changeLanguage("ru") })

  it("distinguishes deafened from stunned in Russian", async () => {
    const { CreatureForm } = await import("../CreatureForm")

    render(
      <CreatureForm
        sessionId="sess-1"
        creature={makeCreature()}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    )

    expect(screen.getByRole("button", { name: "Оглохший" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Оглушён" })).toBeInTheDocument()
  })
})
