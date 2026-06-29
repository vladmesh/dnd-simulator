import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { MemoryRouter, Routes, Route } from "react-router"
import "@/i18n"

import { MasterScreen } from "../MasterScreen"
import { LandingPage } from "@/components/LandingPage"
import { api } from "@/transport/apiClient"
import { useGameStore } from "@/store/gameStore"

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      getSessions: vi.fn(),
      getWorlds: vi.fn(),
      createSession: vi.fn(),
      deleteSession: vi.fn(),
      getWorldManifest: vi.fn(),
      forkWorld: vi.fn(),
      deleteWorld: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api.master)

const aliceWorlds = [
  { id: "alice_vale", name: "Alice Vale", description: "Alice's world", editable: true },
]

const danaWorlds = [
  { id: "dana_keep", name: "Dana Keep", description: "Dana's world", editable: true },
]

const danaSessions = [
  { session_id: "dana0001", player_name: "Hero", player_location: "Town", time: "Day 1", world_name: "dana_keep", created_by: "dana" },
  { session_id: "other999", player_name: "Villain", player_location: "Cave", time: "Day 2", world_name: "x", created_by: "someone_else" },
]

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  useGameStore.setState({ userId: null, role: null })
})

describe("MasterScreen — worldbuilder lens", () => {
  it("shows only own worlds (creator-scoped) and hides the Sessions tab", async () => {
    useGameStore.setState({ userId: "alice", role: "worldbuilder" })
    mockApi.getWorlds.mockResolvedValue(aliceWorlds)
    mockApi.getSessions.mockResolvedValue([])

    render(
      <MemoryRouter>
        <MasterScreen />
      </MemoryRouter>,
    )

    expect(await screen.findByText("Alice Vale")).toBeInTheDocument()
    // worlds fetched scoped to the creator
    expect(mockApi.getWorlds.mock.calls.some((c) => c[1] === "alice")).toBe(true)
    // no live sessions for a worldbuilder
    expect(screen.queryByRole("tab", { name: /sessions/i })).not.toBeInTheDocument()
  })
})

describe("MasterScreen — DM lens", () => {
  it("shows own worlds, only own sessions, and manage controls", async () => {
    const user = userEvent.setup()
    useGameStore.setState({ userId: "dana", role: "dm" })
    mockApi.getWorlds.mockResolvedValue(danaWorlds)
    mockApi.getSessions.mockResolvedValue(danaSessions)

    render(
      <MemoryRouter>
        <MasterScreen />
      </MemoryRouter>,
    )

    await screen.findByText("Dana Keep")
    expect(mockApi.getWorlds.mock.calls.some((c) => c[1] === "dana")).toBe(true)

    // both tabs present
    expect(screen.getByRole("tab", { name: /worlds/i })).toBeInTheDocument()
    await user.click(screen.getByRole("tab", { name: /sessions/i }))

    // session list filtered to created_by === "dana"
    await waitFor(() => expect(screen.getByText(/dana0001/)).toBeInTheDocument())
    expect(screen.queryByText(/other999/)).not.toBeInTheDocument()

    // full manage / new-session controls
    expect(screen.getByRole("button", { name: /new session/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /manage/i })).toBeInTheDocument()
  })
})

describe("MasterScreen — routing from landing", () => {
  it("a worldbuilder activating the master entry lands in the worldbuilder lens", async () => {
    const user = userEvent.setup()
    useGameStore.setState({ userId: "alice", role: "worldbuilder" })
    mockApi.getWorlds.mockResolvedValue(aliceWorlds)
    mockApi.getSessions.mockResolvedValue([])

    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/master" element={<MasterScreen />} />
        </Routes>
      </MemoryRouter>,
    )

    await user.click(screen.getByRole("link", { name: /dungeon master/i }))

    expect(await screen.findByText("Alice Vale")).toBeInTheDocument()
    expect(screen.queryByRole("tab", { name: /sessions/i })).not.toBeInTheDocument()
  })
})

describe("MasterScreen — fallback (no role)", () => {
  it("shows both tabs and all worlds unfiltered when role is null", async () => {
    mockApi.getWorlds.mockResolvedValue([
      { id: "w1", name: "World One", description: "", editable: false },
      { id: "w2", name: "World Two", description: "", editable: false },
    ])
    mockApi.getSessions.mockResolvedValue([])

    render(
      <MemoryRouter>
        <MasterScreen />
      </MemoryRouter>,
    )

    expect(await screen.findByText("World One")).toBeInTheDocument()
    expect(screen.getByText("World Two")).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /worlds/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /sessions/i })).toBeInTheDocument()
    // unfiltered fetch — no creator argument
    expect(mockApi.getWorlds.mock.calls.every((c) => c[1] === undefined)).toBe(true)
  })
})
