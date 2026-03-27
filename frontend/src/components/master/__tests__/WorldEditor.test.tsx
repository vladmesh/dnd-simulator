import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { WorldEditor } from "../WorldEditor"
import { api } from "@/transport/apiClient"

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      getWorldManifest: vi.fn(),
      forkLayer: vi.fn(),
      createEntity: vi.fn(),
      listEntities: vi.fn(),
      getSchema: vi.fn(),
      getRefs: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api.master)

const layers = [
  { layer_type: "geography", source: "custom", template: null },
  { layer_type: "politics", source: "custom", template: null },
  { layer_type: "settlements", source: "custom", template: null },
  { layer_type: "ecology", source: "library", template: "default_ecology" },
  { layer_type: "entities", source: "custom", template: null },
]

function setup() {
  mockApi.getWorldManifest.mockResolvedValue({ layers })
  mockApi.listEntities.mockResolvedValue([])
  mockApi.getSchema.mockResolvedValue({ type: "object", properties: {} })
  mockApi.getRefs.mockResolvedValue([])

  return render(<WorldEditor worldId="sword_vale" onClose={() => {}} />)
}

/** Wait for stepper buttons to appear (layers loaded) */
async function waitForStepper() {
  // Stepper buttons are plain <button> elements in a flex container
  await waitFor(() => {
    // All 5 layer names appear as stepper buttons
    const buttons = screen.getAllByRole("button")
    const stepperLabels = buttons.map((b) => b.textContent).filter(Boolean)
    expect(stepperLabels).toEqual(expect.arrayContaining(["geography", "politics", "settlements", "ecology", "entities"]))
  })
}

describe("WorldEditor stepper", () => {
  beforeEach(() => vi.clearAllMocks())

  it("shows 5 layer steps", async () => {
    setup()
    await waitForStepper()
  })

  it("navigates forward and back through steps", async () => {
    const user = userEvent.setup()
    setup()
    await waitForStepper()

    // Should start at geography — entity list loads region, location
    expect(mockApi.listEntities).toHaveBeenCalledWith("sword_vale", "region")
    expect(mockApi.listEntities).toHaveBeenCalledWith("sword_vale", "location")

    const nextBtn = screen.getByRole("button", { name: /next/i })
    await user.click(nextBtn)

    // Now on politics — listEntities called for nation
    await waitFor(() => {
      expect(mockApi.listEntities).toHaveBeenCalledWith("sword_vale", "nation")
    })

    const backBtn = screen.getByRole("button", { name: /back/i })
    await user.click(backBtn)

    // Back on geography — listEntities called again for region
    await waitFor(() => {
      // region was called at start and again now
      const regionCalls = mockApi.listEntities.mock.calls.filter(([, t]) => t === "region")
      expect(regionCalls.length).toBeGreaterThanOrEqual(2)
    })
  })

  it("shows fork button for library layers", async () => {
    const user = userEvent.setup()
    setup()
    await waitForStepper()

    // Navigate to ecology (step 4, index 3)
    const nextBtn = screen.getByRole("button", { name: /next/i })
    await user.click(nextBtn) // politics
    await user.click(nextBtn) // settlements
    await user.click(nextBtn) // ecology

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /fork/i })).toBeInTheDocument()
    })
  })

  it("renders CatalogPicker button on ecology step when custom", async () => {
    // Override ecology to be custom so catalog picker shows
    const customLayers = layers.map((l) =>
      l.layer_type === "ecology" ? { ...l, source: "custom", template: null } : l,
    )
    mockApi.getWorldManifest.mockResolvedValue({ layers: customLayers })
    mockApi.listEntities.mockResolvedValue([])
    mockApi.getSchema.mockResolvedValue({ type: "object", properties: {} })
    mockApi.getRefs.mockResolvedValue([])

    const user = userEvent.setup()
    render(<WorldEditor worldId="sword_vale" onClose={() => {}} />)
    await waitForStepper()

    // Navigate to ecology
    const nextBtn = screen.getByRole("button", { name: /next/i })
    await user.click(nextBtn) // politics
    await user.click(nextBtn) // settlements
    await user.click(nextBtn) // ecology

    await waitFor(() => {
      expect(screen.getByText(/pick from catalog/i)).toBeInTheDocument()
    })
  })
})
