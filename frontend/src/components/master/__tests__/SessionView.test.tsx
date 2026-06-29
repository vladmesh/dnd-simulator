import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { MemoryRouter, Routes, Route } from "react-router"
import "@/i18n"

import { SessionView } from "../SessionView"
import { api } from "@/transport/apiClient"
import { useGameStore } from "@/store/gameStore"
import type { CreatureResponse, WorldStateResponse } from "@/types/api"

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      getSession: vi.fn(),
      getCreatures: vi.fn(),
      deleteCreature: vi.fn(),
      setBrain: vi.fn(),
    },
  },
}))

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }))

const mockApi = vi.mocked(api.master)

const emptyWorld: WorldStateResponse = {
  session_id: "sess-1",
  time: "Day 1",
  regions: [],
  nations: [],
  settlements: [],
  entities: [],
}

function makeCreature(overrides: Partial<CreatureResponse> = {}): CreatureResponse {
  return {
    id: "g1",
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

function renderView() {
  return render(
    <MemoryRouter initialEntries={["/master/sess-1"]}>
      <Routes>
        <Route path="/master/:sessionId" element={<SessionView />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  useGameStore.setState({ userId: null, role: null })
})

describe("SessionView — admin observe mode", () => {
  it("hides write-only tabs and creature write controls but keeps observation panes", async () => {
    const user = userEvent.setup()
    useGameStore.setState({ userId: "root", role: "admin" })
    mockApi.getSession.mockResolvedValue(emptyWorld)
    mockApi.getCreatures.mockResolvedValue([makeCreature({ name: "Goblin" })])

    renderView()

    await screen.findByText(/Day 1/)
    // time-advance + save panels are write controls — hidden in observe mode
    expect(screen.queryByRole("button", { name: /^time$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /^saves$/i })).not.toBeInTheDocument()

    // observation panes remain
    await user.click(screen.getByRole("button", { name: /creatures/i }))
    await waitFor(() => expect(screen.getByText("Goblin")).toBeInTheDocument())
    // creature hot-controls hidden
    expect(screen.queryByRole("button", { name: /spawn/i })).not.toBeInTheDocument()
    expect(screen.queryByTitle(/brain/i)).not.toBeInTheDocument()
  })
})

describe("SessionView — DM keeps write controls", () => {
  it("shows the time and saves tabs for a DM", async () => {
    useGameStore.setState({ userId: "dana", role: "dm" })
    mockApi.getSession.mockResolvedValue(emptyWorld)
    mockApi.getCreatures.mockResolvedValue([])

    renderView()

    await screen.findByText(/Day 1/)
    expect(screen.getByRole("button", { name: /^time$/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /^saves$/i })).toBeInTheDocument()
  })
})
