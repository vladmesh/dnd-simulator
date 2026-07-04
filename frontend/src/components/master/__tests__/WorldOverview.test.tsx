import { render, screen, waitFor, within, fireEvent } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import "@/i18n"
import { WorldOverview } from "../WorldOverview"
import { api } from "@/transport/apiClient"
import type { WorldStateResponse } from "@/types/api"

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      patchNation: vi.fn(),
      patchSettlement: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api.master)

function makeWorldState(): WorldStateResponse {
  return {
    session_id: "s1",
    time: "Y1 M1 D1 08:00",
    regions: [
      {
        id: "north",
        name: "The North",
        latitude: 60,
        longitude: 10,
        elevation: 200,
        terrain: "tundra",
        water_proximity: 0.2,
        weather: { condition: "snow", temperature: -5 },
        temperature: -5,
      },
    ],
    nations: [
      {
        id: "kingdom",
        name: "Kingdom",
        regions: ["north"],
        wealth: 5,
        military: 3,
        stability: 70,
        leader: null,
      },
    ],
    settlements: [
      {
        id: "town",
        name: "Rivertown",
        region_id: "north",
        type: "town",
        population: 1200,
        prosperity: 50,
        defenses: 40,
      },
    ],
    entities: [],
  }
}

beforeEach(() => vi.clearAllMocks())

describe("WorldOverview", () => {
  it("renders region, nation and settlement rows", () => {
    render(<WorldOverview sessionId="s1" worldState={makeWorldState()} />)
    // region name appears in the region table and again as the settlement's region
    expect(screen.getAllByText("The North").length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText(/snow, -5/)).toBeInTheDocument()
    expect(screen.getByText("tundra")).toBeInTheDocument()
    expect(screen.getByText("Kingdom")).toBeInTheDocument()
    expect(screen.getByText("Rivertown")).toBeInTheDocument()
  })

  it("edits a nation and patches with parsed numbers", async () => {
    mockApi.patchNation.mockResolvedValue({ message: "ok" })
    render(<WorldOverview sessionId="s1" worldState={makeWorldState()} />)

    const nationRow = screen.getByText("Kingdom").closest("tr")!
    fireEvent.click(within(nationRow).getByRole("button", { name: "Edit" }))

    const inputs = within(nationRow).getAllByRole("spinbutton")
    fireEvent.change(inputs[0], { target: { value: "9" } })
    // save = first actions button (Check), cancel = second (✕)
    fireEvent.click(within(nationRow).getAllByRole("button")[0])

    await waitFor(() => {
      expect(mockApi.patchNation).toHaveBeenCalledWith("s1", "kingdom", {
        wealth: 9,
        military: 3,
        stability: 70,
      })
    })
  })

  it("reverts to edit mode when nation patch is rejected", async () => {
    mockApi.patchNation.mockRejectedValue(new Error("boom"))
    render(<WorldOverview sessionId="s1" worldState={makeWorldState()} />)

    const nationRow = screen.getByText("Kingdom").closest("tr")!
    fireEvent.click(within(nationRow).getByRole("button", { name: "Edit" }))
    fireEvent.click(within(nationRow).getAllByRole("button")[0])

    // after rejection, inputs remain (still editing)
    await waitFor(() => {
      expect(within(nationRow).getAllByRole("spinbutton").length).toBeGreaterThan(0)
    })
  })

  it("edits a settlement and patches population as integer", async () => {
    mockApi.patchSettlement.mockResolvedValue({ message: "ok" })
    render(<WorldOverview sessionId="s1" worldState={makeWorldState()} />)

    const row = screen.getByText("Rivertown").closest("tr")!
    fireEvent.click(within(row).getByRole("button", { name: "Edit" }))
    const inputs = within(row).getAllByRole("spinbutton")
    fireEvent.change(inputs[0], { target: { value: "1500" } })
    fireEvent.click(within(row).getAllByRole("button")[0])

    await waitFor(() => {
      expect(mockApi.patchSettlement).toHaveBeenCalledWith("s1", "town", {
        population: 1500,
        prosperity: 50,
        defenses: 40,
      })
    })
  })
})
