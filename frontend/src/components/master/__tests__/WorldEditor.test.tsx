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
  { layer_type: "ecology", source: "custom", template: null },
  { layer_type: "entities", source: "custom", template: null },
]

function setup(overrides: { readOnly?: boolean } = {}) {
  mockApi.getWorldManifest.mockResolvedValue({ layers })
  mockApi.listEntities.mockResolvedValue([])
  mockApi.getSchema.mockResolvedValue({ type: "object", properties: {} })
  mockApi.getRefs.mockResolvedValue([])

  return render(
    <WorldEditor
      worldId="sword_vale"
      readOnly={overrides.readOnly ?? false}
      onClose={() => {}}
    />,
  )
}

/** Wait for stepper buttons to appear (layers loaded) */
async function waitForStepper() {
  await waitFor(() => {
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

    await waitFor(() => {
      expect(mockApi.listEntities).toHaveBeenCalledWith("sword_vale", "region")
      expect(mockApi.listEntities).toHaveBeenCalledWith("sword_vale", "location")
    })

    const nextBtn = screen.getByRole("button", { name: /next/i })
    await user.click(nextBtn)

    await waitFor(() => {
      expect(mockApi.listEntities).toHaveBeenCalledWith("sword_vale", "nation")
    })

    const backBtn = screen.getByRole("button", { name: /back/i })
    await user.click(backBtn)

    await waitFor(() => {
      const regionCalls = mockApi.listEntities.mock.calls.filter(([, t]) => t === "region")
      expect(regionCalls.length).toBeGreaterThanOrEqual(2)
    })
  })

  it("never shows a fork button", async () => {
    const user = userEvent.setup()
    // Even with library layers, no fork button should appear
    const libraryLayers = layers.map((l) =>
      l.layer_type === "ecology" ? { ...l, source: "library", template: "default_ecology" } : l,
    )
    mockApi.getWorldManifest.mockResolvedValue({ layers: libraryLayers })
    mockApi.listEntities.mockResolvedValue([])
    mockApi.getSchema.mockResolvedValue({ type: "object", properties: {} })
    mockApi.getRefs.mockResolvedValue([])

    render(<WorldEditor worldId="sword_vale" readOnly={false} onClose={() => {}} />)
    await waitForStepper()

    // Navigate to ecology (library layer)
    const nextBtn = screen.getByRole("button", { name: /next/i })
    await user.click(nextBtn) // politics
    await user.click(nextBtn) // settlements
    await user.click(nextBtn) // ecology

    // No fork button anywhere
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /fork/i })).not.toBeInTheDocument()
    })
  })

  it("renders CatalogPicker button on ecology step when editable", async () => {
    const user = userEvent.setup()
    setup()
    await waitForStepper()

    const nextBtn = screen.getByRole("button", { name: /next/i })
    await user.click(nextBtn) // politics
    await user.click(nextBtn) // settlements
    await user.click(nextBtn) // ecology

    await waitFor(() => {
      expect(screen.getByText(/pick from catalog/i)).toBeInTheDocument()
    })
  })
})

describe("WorldEditor readOnly", () => {
  beforeEach(() => vi.clearAllMocks())

  it("hides catalog picker on ecology step when readOnly", async () => {
    const user = userEvent.setup()
    setup({ readOnly: true })
    await waitForStepper()

    const nextBtn = screen.getByRole("button", { name: /next/i })
    await user.click(nextBtn) // politics
    await user.click(nextBtn) // settlements
    await user.click(nextBtn) // ecology

    await waitFor(() => {
      expect(screen.queryByText(/pick from catalog/i)).not.toBeInTheDocument()
    })
  })

  it("does not show source badges", async () => {
    // Library layer present but no badge shown
    const libraryLayers = layers.map((l) =>
      l.layer_type === "ecology" ? { ...l, source: "library", template: "default_ecology" } : l,
    )
    mockApi.getWorldManifest.mockResolvedValue({ layers: libraryLayers })
    mockApi.listEntities.mockResolvedValue([])
    mockApi.getSchema.mockResolvedValue({ type: "object", properties: {} })
    mockApi.getRefs.mockResolvedValue([])

    render(<WorldEditor worldId="sword_vale" readOnly={true} onClose={() => {}} />)
    await waitForStepper()

    expect(screen.queryByText(/library/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/custom/i)).not.toBeInTheDocument()
  })
})
