import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { CatalogBrowser } from "../CatalogBrowser"

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

// ---------------------------------------------------------------------------

describe("CatalogBrowser", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListCatalog.mockResolvedValue(monsterEntries)
    mockGetSchema.mockResolvedValue(monsterSchema)
  })

  it("loads and displays catalog entries in a table", async () => {
    render(<CatalogBrowser catalogType="monster_catalog" />)

    expect(await screen.findByText("goblin")).toBeInTheDocument()
    expect(screen.getByText("orc")).toBeInTheDocument()
    expect(mockListCatalog).toHaveBeenCalledWith("monster_catalog")
  })

  it("shows entry detail when clicked", async () => {
    const user = userEvent.setup()
    render(<CatalogBrowser catalogType="monster_catalog" />)

    await screen.findByText("goblin")
    const viewButtons = screen.getAllByRole("button", { name: /view/i })
    await user.click(viewButtons[0])

    // Detail view should show the entry data
    expect(await screen.findByText(/Goblin/)).toBeInTheDocument()
  })
})
