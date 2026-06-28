import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { api } from "@/transport/apiClient"
import type { CreatureResponse } from "@/types/api"

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
    ...overrides,
  }
}

describe("CreatureForm — HP current/max fields", () => {
  beforeEach(() => vi.clearAllMocks())

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
