import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { CatalogPicker } from "../CatalogPicker"

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockListCatalog = vi.fn()
const mockGetSchema = vi.fn()

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      listCatalog: (...args: unknown[]) => mockListCatalog(...args),
      getSchema: (...args: unknown[]) => mockGetSchema(...args),
    },
  },
}))

const monsterEntries = [
  { id: "goblin", data: { name: { en: "Goblin" }, hp: 7, ac: 15 } },
  { id: "orc", data: { name: { en: "Orc" }, hp: 15, ac: 13 } },
]

const monsterSchema = {
  type: "object" as const,
  properties: {
    name: { type: "object" as const, title: "Name", additionalProperties: { type: "string" as const } },
    hp: { type: "integer" as const, title: "HP" },
    ac: { type: "integer" as const, title: "AC" },
  },
}

describe("CatalogPicker", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListCatalog.mockResolvedValue(monsterEntries)
    mockGetSchema.mockResolvedValue(monsterSchema)
  })

  it("calls onPick with selected catalog entry id", async () => {
    const user = userEvent.setup()
    const onPick = vi.fn()

    render(<CatalogPicker catalogType="monster_catalog" onPick={onPick} />)

    // Wait for catalog to load
    await screen.findByText("goblin")

    // Click pick button for goblin
    const pickButtons = screen.getAllByRole("button", { name: /pick/i })
    await user.click(pickButtons[0])

    await waitFor(() => {
      expect(onPick).toHaveBeenCalledWith("goblin")
    })
  })
})
