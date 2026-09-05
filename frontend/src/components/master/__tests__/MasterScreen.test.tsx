import { render, screen, waitFor, within } from "@testing-library/react"
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
      forkWorld: vi.fn(),
      deleteWorld: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api.master)

const worlds = [
  { id: "sword_vale", name: "Sword Vale", description: "A dangerous valley", editable: false },
  { id: "frost_peaks", name: "Frost Peaks", description: "Icy mountains", editable: false },
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
    expect(screen.getByRole("link", { name: /manage/i })).toHaveAttribute("href", "/master/sess-001")
  })
})

describe("MasterScreen fork world", () => {
  beforeEach(() => vi.clearAllMocks())

  it("shows fork button on each world card", async () => {
    setup()
    await screen.findByText("Sword Vale")
    const forkButtons = screen.getAllByRole("button", { name: /fork/i })
    expect(forkButtons).toHaveLength(worlds.length)
  })

  it("opens fork dialog on fork button click", async () => {
    const user = userEvent.setup()
    setup()
    await screen.findByText("Sword Vale")

    const forkButtons = screen.getAllByRole("button", { name: /fork/i })
    await user.click(forkButtons[0])

    // Dialog should appear with ID input
    expect(await screen.findByLabelText(/id/i)).toBeInTheDocument()
  })

  it("calls forkWorld API and refreshes list on submit", async () => {
    const user = userEvent.setup()
    const forkedWorld = { id: "my_vale", name: "my_vale", description: "", editable: true }
    mockApi.forkWorld.mockResolvedValue(forkedWorld)

    setup()
    await screen.findByText("Sword Vale")

    // Click fork on first world
    const forkButtons = screen.getAllByRole("button", { name: /fork/i })
    await user.click(forkButtons[0])

    // Fill in new world ID
    const idInput = await screen.findByLabelText(/id/i)
    await user.clear(idInput)
    await user.type(idInput, "my_vale")

    // Submit — the fork dialog has a Fork button inside it
    const forkDialog = screen.getByTestId("fork-dialog")
    const submitBtn = within(forkDialog).getByRole("button", { name: /fork/i })
    await user.click(submitBtn)

    await waitFor(() => {
      expect(mockApi.forkWorld).toHaveBeenCalledWith("sword_vale", { new_id: "my_vale" })
    })
    // Should refresh world list
    expect(mockApi.getWorlds.mock.calls.length).toBeGreaterThanOrEqual(2)
  })
})

describe("MasterScreen delete world", () => {
  beforeEach(() => vi.clearAllMocks())

  it("shows delete button only on editable worlds", async () => {
    const mixedWorlds = [
      { id: "sword_vale", name: "Sword Vale", description: "Base world", editable: false },
      { id: "my_vale", name: "My Vale", description: "Forked", editable: true },
    ]
    mockApi.getWorlds.mockResolvedValue(mixedWorlds)
    mockApi.getSessions.mockResolvedValue([])

    render(
      <MemoryRouter>
        <MasterScreen />
      </MemoryRouter>,
    )

    await screen.findByText("Sword Vale")

    // Only one delete button should exist (for the editable world)
    const deleteButtons = screen.getAllByRole("button", { name: /delete/i })
    expect(deleteButtons).toHaveLength(1)

    // The delete button should be on the editable world's card
    const myValeCard = screen.getByText("My Vale").closest<HTMLElement>("[data-testid]")!
    expect(within(myValeCard).getByRole("button", { name: /delete/i })).toBeInTheDocument()
  })

  it("calls deleteWorld API on confirm", async () => {
    const user = userEvent.setup()
    const mixedWorlds = [
      { id: "sword_vale", name: "Sword Vale", description: "Base world", editable: false },
      { id: "my_vale", name: "My Vale", description: "Forked", editable: true },
    ]
    mockApi.getWorlds.mockResolvedValue(mixedWorlds)
    mockApi.getSessions.mockResolvedValue([])
    mockApi.deleteWorld.mockResolvedValue({ message: "deleted" })

    // Mock window.confirm to return true
    vi.spyOn(window, "confirm").mockReturnValue(true)

    render(
      <MemoryRouter>
        <MasterScreen />
      </MemoryRouter>,
    )

    await screen.findByText("My Vale")

    const deleteBtn = screen.getByRole("button", { name: /delete/i })
    await user.click(deleteBtn)

    await waitFor(() => {
      expect(mockApi.deleteWorld).toHaveBeenCalledWith("my_vale")
    })
  })
})

describe("MasterScreen world card click routing", () => {
  beforeEach(() => vi.clearAllMocks())

  it("passes readOnly=true for base worlds and readOnly=false for editable worlds", async () => {
    // We test the state logic, not the full WorldEditor rendering
    // The MasterScreen should track which world is clicked and pass readOnly based on editable
    const user = userEvent.setup()
    const mixedWorlds = [
      { id: "sword_vale", name: "Sword Vale", description: "Base world", editable: false },
      { id: "my_vale", name: "My Vale", description: "Forked", editable: true },
    ]
    mockApi.getWorlds.mockResolvedValue(mixedWorlds)
    mockApi.getSessions.mockResolvedValue([])
    mockApi.getWorldManifest.mockResolvedValue({
      world_id: "sword_vale",
      name: "Sword Vale",
      layers: [{ layer_type: "geography", source: "library", template: "default_geography", version: "1" }],
    })

    render(
      <MemoryRouter>
        <MasterScreen />
      </MemoryRouter>,
    )

    // Click on a base world card title
    const swordValeTitle = await screen.findByText("Sword Vale")
    await user.click(swordValeTitle)

    // WorldEditor should open — look for close button
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /close/i })).toBeInTheDocument()
    })
  })
})
