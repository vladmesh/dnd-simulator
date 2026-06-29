import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { api } from "@/transport/apiClient"
import type { CreatureResponse } from "@/types/api"

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      getCreatures: vi.fn(),
      deleteCreature: vi.fn(),
      setBrain: vi.fn(),
    },
  },
}))

// Mock sonner toast
const toastMock = { success: vi.fn(), error: vi.fn(), warning: vi.fn() }
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
    conditions: [],
    entity_type: "npc",
    ai_type: "rule_based",
    gold: 0,
    ...overrides,
  }
}

describe("CreatureList — brain toggle warning", () => {
  beforeEach(() => vi.clearAllMocks())

  it("shows warning toast when brain toggle response has warning", async () => {
    const user = userEvent.setup()
    const { CreatureList } = await import("../CreatureList")
    const creature = makeCreature({ ai_type: "rule_based" })
    mockApi.getCreatures.mockResolvedValue([creature])
    mockApi.setBrain.mockResolvedValue({
      message: "Brain set",
      brain_type: "rule_based",
      warning: "no_llm_key",
    })

    render(<CreatureList sessionId="sess-1" />)

    // Wait for creatures to load
    await waitFor(() => expect(screen.getByText("Goblin")).toBeTruthy())

    // Click the brain toggle button
    const brainButton = screen.getByTitle(/brain/i)
    await user.click(brainButton)

    await waitFor(() => {
      expect(toastMock.warning).toHaveBeenCalled()
      expect(toastMock.success).not.toHaveBeenCalled()
    })
  })

  it("shows success toast when brain toggle succeeds without warning", async () => {
    const user = userEvent.setup()
    const { CreatureList } = await import("../CreatureList")
    const creature = makeCreature({ ai_type: "rule_based" })
    mockApi.getCreatures.mockResolvedValue([creature])
    mockApi.setBrain.mockResolvedValue({
      message: "Brain set",
      brain_type: "llm",
    })

    render(<CreatureList sessionId="sess-1" />)

    await waitFor(() => expect(screen.getByText("Goblin")).toBeTruthy())

    const brainButton = screen.getByTitle(/brain/i)
    await user.click(brainButton)

    await waitFor(() => {
      expect(toastMock.success).toHaveBeenCalled()
      expect(toastMock.warning).not.toHaveBeenCalled()
    })
  })
})

describe("CreatureList — inline inventory", () => {
  beforeEach(() => vi.clearAllMocks())

  it("renders item names and the equipped weapon attack name inline in the row", async () => {
    const { CreatureList } = await import("../CreatureList")
    mockApi.getCreatures.mockResolvedValue([
      makeCreature({
        name: "Bandit",
        inventory: [
          { id: "potion_1", name: "Healing Potion", item_type: "potion" },
          { id: "dagger_1", name: "Dagger", item_type: "weapon" },
        ],
        equipped_weapon: { weapon_id: "longsword", attack_name: "Longsword", damage: "1d8" },
      }),
    ])

    render(<CreatureList sessionId="sess-1" />)

    await waitFor(() => expect(screen.getByText("Bandit")).toBeInTheDocument())
    expect(screen.getByText("Healing Potion")).toBeInTheDocument()
    expect(screen.getByText("Dagger")).toBeInTheDocument()
    expect(screen.getByText("Longsword")).toBeInTheDocument()
  })

  it("renders a creature with empty inventory without items and without error", async () => {
    const { CreatureList } = await import("../CreatureList")
    mockApi.getCreatures.mockResolvedValue([
      makeCreature({ name: "Pauper", inventory: [], equipped_weapon: null }),
    ])

    render(<CreatureList sessionId="sess-1" />)

    await waitFor(() => expect(screen.getByText("Pauper")).toBeInTheDocument())
  })
})

describe("CreatureList — observe mode", () => {
  beforeEach(() => vi.clearAllMocks())

  it("hides spawn / delete / brain write controls but keeps the observation list", async () => {
    const { CreatureList } = await import("../CreatureList")
    mockApi.getCreatures.mockResolvedValue([makeCreature({ name: "Watcher" })])

    render(<CreatureList sessionId="sess-1" observe />)

    await waitFor(() => expect(screen.getByText("Watcher")).toBeInTheDocument())
    expect(screen.queryByRole("button", { name: /spawn/i })).not.toBeInTheDocument()
    expect(screen.queryByTitle(/brain/i)).not.toBeInTheDocument()
  })
})
