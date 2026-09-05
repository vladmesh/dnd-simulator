import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { MemoryRouter, Routes, Route } from "react-router"
import "@/i18n"
import { SetupScreen } from "../SetupScreen"
import { api } from "@/transport/apiClient"

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      getWorlds: vi.fn(),
      createSession: vi.fn(),
    },
    player: {
      getSetupConfig: vi.fn().mockResolvedValue({
        starting_gold: 100,
        point_buy_budget: 27,
      }),
      createCharacter: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api.master)

function setup() {
  mockApi.getWorlds.mockResolvedValue([
    { id: "sword_vale", name: "Sword Vale", description: "A test world", editable: false },
  ])

  return render(
    <MemoryRouter initialEntries={["/play"]}>
      <Routes>
        <Route path="/play" element={<SetupScreen />} />
        <Route path="/play/:sessionId" element={<div>GameScreen</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe("SetupScreen", () => {
  beforeEach(() => vi.clearAllMocks())

  it("does not show Build Custom World button", async () => {
    setup()
    await screen.findByText("Sword Vale")
    expect(screen.queryByText(/build custom world/i)).not.toBeInTheDocument()
  })

  it("picks a world and goes straight to character creation", async () => {
    const user = userEvent.setup()
    mockApi.createSession.mockResolvedValue({ session_id: "abc-123", player_name: "", player_location: "", time: "Y1490 M6 D1 10:00" })
    setup()

    const worldBtn = await screen.findByText("New Session")
    await user.click(worldBtn)

    await waitFor(() => {
      expect(screen.getByText(/create your character/i)).toBeInTheDocument()
    })
  })
})
