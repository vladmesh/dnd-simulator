import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { api } from "@/transport/apiClient"
import type { CreatureResponse } from "@/types/api"
import i18n from "@/i18n"

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      getCreatures: vi.fn(),
      deleteCreature: vi.fn(),
      setBrain: vi.fn(),
      setCreatureActivation: vi.fn(),
      setActivationTrigger: vi.fn(),
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
    gm_activation_override: "automatic",
    activation_triggers: [],
    ...overrides,
  }
}

describe("CreatureList — brain toggle warning", () => {
  beforeEach(async () => { vi.clearAllMocks(); await i18n.changeLanguage("en") })

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

describe("CreatureList — activation controls", () => {
  beforeEach(async () => { vi.clearAllMocks(); await i18n.changeLanguage("en") })

  it("changes a dormant creature override and refreshes the factual state", async () => {
    const user = userEvent.setup()
    const { CreatureList } = await import("../CreatureList")
    const dormant = makeCreature({ active: false })
    const forcedActive = makeCreature({ active: true, gm_activation_override: "active" })
    mockApi.getCreatures
      .mockResolvedValueOnce([dormant])
      .mockResolvedValueOnce([forcedActive])
    mockApi.setCreatureActivation.mockResolvedValue(forcedActive)

    render(<CreatureList sessionId="sess-1" />)

    await user.click(await screen.findByRole("button", { name: "Activate" }))

    expect(mockApi.setCreatureActivation).toHaveBeenCalledWith(
      "sess-1",
      "goblin_1",
      { override: "active" },
    )
    await waitFor(() => expect(mockApi.getCreatures).toHaveBeenCalledTimes(2))
    expect(screen.getByText("Actually active")).toBeInTheDocument()
    expect(screen.getByText("Manual: active")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Automatic" })).toBeEnabled()
    expect(screen.getByRole("button", { name: "Make dormant" })).toBeEnabled()
  })

  it("updates one trigger by stable id and keeps server state on an API error", async () => {
    const user = userEvent.setup()
    const { CreatureList } = await import("../CreatureList")
    const creature = makeCreature({
      activation_triggers: [
        { id: "war_duty", armed: true, active: true },
        { id: "bell", armed: true, active: false },
      ],
    })
    const refreshed = makeCreature({
      activation_triggers: [
        { id: "war_duty", armed: false, active: true },
        { id: "bell", armed: true, active: false },
      ],
    })
    mockApi.getCreatures
      .mockResolvedValueOnce([creature])
      .mockResolvedValueOnce([refreshed])
    mockApi.setActivationTrigger
      .mockResolvedValueOnce({ id: "war_duty", armed: false, active: true })
      .mockRejectedValueOnce(new Error("network"))

    render(<CreatureList sessionId="sess-1" />)

    await user.click(await screen.findByRole("button", { name: "Disarm war_duty" }))

    expect(mockApi.setActivationTrigger).toHaveBeenCalledWith(
      "sess-1",
      "goblin_1",
      "war_duty",
      { armed: false },
    )
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Arm war_duty" })).toBeEnabled()
    })
    expect(screen.getByRole("button", { name: "Disarm bell" })).toBeEnabled()

    await user.click(screen.getByRole("button", { name: "Disarm bell" }))

    await waitFor(() => expect(toastMock.error).toHaveBeenCalled())
    expect(screen.getByRole("button", { name: "Disarm bell" })).toBeEnabled()
    expect(mockApi.getCreatures).toHaveBeenCalledTimes(2)
  })

  it("renders localized factual and manual states independently", async () => {
    const { CreatureList } = await import("../CreatureList")
    await i18n.changeLanguage("ru")
    mockApi.getCreatures.mockResolvedValue([
      makeCreature({ active: true, gm_activation_override: "dormant" }),
    ])

    render(<CreatureList sessionId="sess-1" />)

    expect(await screen.findByText("Фактически активно")).toBeInTheDocument()
    expect(screen.getByText("Ручной режим: погашено")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Активировать" })).toBeEnabled()
    expect(screen.getByRole("button", { name: "Погасить" })).toBeDisabled()
  })
})
