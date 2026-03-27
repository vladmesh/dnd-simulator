import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { MemoryRouter } from "react-router"
import { MasterScreen } from "../MasterScreen"
import { api } from "@/transport/apiClient"

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
    },
  },
}))

const mockApi = vi.mocked(api.master)

const worlds = [
  { id: "sword_vale", name: "Sword Vale", description: "A dangerous valley" },
  { id: "frost_peaks", name: "Frost Peaks", description: "Icy mountains" },
]

const sessions = [
  { session_id: "sess-001", player_name: "Gandalf", player_location: "Town", time: "Day 1", world_name: "sword_vale" },
]

function setup(initialRoute = "/master") {
  mockApi.getWorlds.mockResolvedValue(worlds)
  mockApi.getSessions.mockResolvedValue(sessions)

  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <MasterScreen />
    </MemoryRouter>,
  )
}

describe("MasterScreen tabs", () => {
  beforeEach(() => vi.clearAllMocks())

  it("renders Worlds and Sessions tabs", async () => {
    setup()
    expect(await screen.findByRole("tab", { name: /worlds/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /sessions/i })).toBeInTheDocument()
  })

  it("shows Worlds tab content by default", async () => {
    setup()
    // World cards should be visible
    expect(await screen.findByText("Sword Vale")).toBeInTheDocument()
    expect(screen.getByText("Frost Peaks")).toBeInTheDocument()
  })

  it("switches to Sessions tab and shows session list", async () => {
    const user = userEvent.setup()
    setup()
    await screen.findByText("Sword Vale")

    await user.click(screen.getByRole("tab", { name: /sessions/i }))

    await waitFor(() => {
      expect(screen.getByText(/sess-001/)).toBeInTheDocument()
    })
  })
})
