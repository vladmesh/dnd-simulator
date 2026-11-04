import { act, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { CatalogEntry, JsonSchema } from "@/types/api"
import { CatalogBrowser } from "../CatalogBrowser"

const mockListCatalog = vi.fn<(catalogType: string) => Promise<CatalogEntry[]>>()
const mockGetSchema = vi.fn<(catalogType: string) => Promise<JsonSchema>>()

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      listCatalog: (...args: [string]) => mockListCatalog(...args),
      getSchema: (...args: [string]) => mockGetSchema(...args),
    },
  },
}))

const schema: JsonSchema = {
  type: "object",
  properties: {
    name: { type: "string", title: "Name" },
    hp: { type: "integer", title: "HP" },
  },
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

describe("CatalogBrowser uncovered branches", () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mockListCatalog.mockResolvedValue([])
    mockGetSchema.mockResolvedValue(schema)
  })

  it("withholds the table and actions until both requests finish", async () => {
    const catalog = deferred<CatalogEntry[]>()
    const schemaRequest = deferred<JsonSchema>()
    mockListCatalog.mockReturnValue(catalog.promise)
    mockGetSchema.mockReturnValue(schemaRequest.promise)

    render(<CatalogBrowser catalogType="weapon_catalog" />)

    // The loading spinner has no accessible label; assert the unavailable content.
    expect(screen.queryByRole("table")).not.toBeInTheDocument()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(screen.queryByText("No entries")).not.toBeInTheDocument()
    expect(mockListCatalog).toHaveBeenCalledExactlyOnceWith("weapon_catalog")
    expect(mockGetSchema).toHaveBeenCalledExactlyOnceWith("weapon_catalog")

    await act(async () => {
      catalog.resolve([{ id: "spear", data: { name: "Spear" } }])
    })
    expect(screen.queryByRole("table")).not.toBeInTheDocument()
    expect(screen.queryByText("Spear")).not.toBeInTheDocument()

    await act(async () => {
      schemaRequest.resolve(schema)
    })
    expect(await screen.findByRole("table")).toBeInTheDocument()
    expect(screen.getByRole("cell", { name: "Spear" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "View" })).toBeEnabled()
  })

  it("shows an empty table with no pick actions for an empty catalog", async () => {
    const onPick = vi.fn()
    render(<CatalogBrowser catalogType="weapon_catalog" onPick={onPick} />)

    expect(await screen.findByRole("cell", { name: "No entries" })).toBeInTheDocument()
    expect(screen.getAllByRole("columnheader").map((header) => header.textContent))
      .toEqual(["ID", "Name", "Actions"])
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(onPick).not.toHaveBeenCalled()
  })

  it("picks the selected entry ID without opening details or fetching again", async () => {
    const user = userEvent.setup()
    const onPick = vi.fn()
    mockListCatalog.mockResolvedValue([
      { id: "spear", data: { name: "Spear" } },
      { id: "bow", data: { name: "Longbow" } },
    ])
    render(<CatalogBrowser catalogType="weapon_catalog" onPick={onPick} />)

    const row = await screen.findByRole("row", { name: "bow Longbow Pick" })
    expect(screen.queryByRole("button", { name: "View" })).not.toBeInTheDocument()
    await user.click(within(row).getByRole("button", { name: "Pick" }))

    expect(onPick).toHaveBeenCalledExactlyOnceWith("bow")
    expect(screen.getByRole("table")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Back/ })).not.toBeInTheDocument()
    expect(mockListCatalog).toHaveBeenCalledExactlyOnceWith("weapon_catalog")
    expect(mockGetSchema).toHaveBeenCalledExactlyOnceWith("weapon_catalog")
  })

  it.each(["catalog", "schema"] as const)(
    "shows a load error when the %s request fails and recovers on catalog change",
    async (failedRequest) => {
      if (failedRequest === "catalog") {
        mockListCatalog.mockRejectedValueOnce(new Error("Catalog unavailable"))
      } else {
        mockGetSchema.mockRejectedValueOnce(new Error("Schema unavailable"))
      }
      const { rerender } = render(<CatalogBrowser catalogType="broken_catalog" />)

      expect(await screen.findByText("Failed to load catalog")).toBeInTheDocument()
      expect(screen.queryByRole("table")).not.toBeInTheDocument()
      expect(screen.queryByRole("button")).not.toBeInTheDocument()
      expect(mockListCatalog).toHaveBeenNthCalledWith(1, "broken_catalog")
      expect(mockGetSchema).toHaveBeenNthCalledWith(1, "broken_catalog")

      const nextCatalog = deferred<CatalogEntry[]>()
      mockListCatalog.mockReturnValueOnce(nextCatalog.promise)
      rerender(<CatalogBrowser catalogType="armor_catalog" />)

      expect(screen.queryByText("Failed to load catalog")).not.toBeInTheDocument()
      expect(screen.queryByRole("table")).not.toBeInTheDocument()
      expect(mockListCatalog).toHaveBeenNthCalledWith(2, "armor_catalog")
      expect(mockGetSchema).toHaveBeenNthCalledWith(2, "armor_catalog")

      await act(async () => {
        nextCatalog.resolve([{ id: "shield", data: { name: "Shield" } }])
      })
      expect(await screen.findByRole("cell", { name: "Shield" })).toBeInTheDocument()
      expect(screen.queryByText("Failed to load catalog")).not.toBeInTheDocument()
    },
  )

  it("renders localized, primitive, missing, and unwrapped names using their fallbacks", async () => {
    mockListCatalog.mockResolvedValue([
      { id: "english", data: { name: { fr: "Bouclier", en: "Shield" } } },
      { id: "fallback-language", data: { name: { fr: "Epee", de: "Schwert" } } },
      { id: "empty-localized", data: { name: {} } },
      { id: "missing-name", data: {} },
      { id: "null-name", data: { name: null } },
      { id: "numeric-name", data: { name: 42 } },
      { id: "unwrapped", name: "Top-level name" },
      { id: "null-data", data: null, name: "Null-data fallback" },
    ])
    render(<CatalogBrowser catalogType="item_catalog" />)

    const table = await screen.findByRole("table")
    const expectedNames = [
      ["english", "Shield"],
      ["fallback-language", "Epee"],
      ["empty-localized", ""],
      ["missing-name", ""],
      ["null-name", ""],
      ["numeric-name", "42"],
      ["unwrapped", "Top-level name"],
      ["null-data", "Null-data fallback"],
    ]
    for (const [id, name] of expectedNames) {
      const row = within(table).getByRole("row", { name: `${id} ${name} View`.replace(/ +/g, " ") })
      const nameCell = within(row).getAllByRole("cell")[1]
      if (name) {
        expect(nameCell).toHaveTextContent(name)
      } else {
        expect(nameCell).toBeEmptyDOMElement()
      }
    }
  })

  it("uses unwrapped data in details and returns to the table without persisting form edits", async () => {
    const user = userEvent.setup()
    mockListCatalog.mockResolvedValue([{ id: "troll", name: "Troll", hp: 84 }])
    render(<CatalogBrowser catalogType="monster_catalog" />)

    await user.click(await screen.findByRole("button", { name: "View" }))
    expect(screen.getByRole("heading", { name: "Troll" })).toBeInTheDocument()
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue("Troll")
    expect(screen.getByRole("spinbutton", { name: "HP" })).toHaveValue(84)

    await user.clear(screen.getByRole("textbox", { name: "Name" }))
    await user.type(screen.getByRole("textbox", { name: "Name" }), "Edited troll")
    // The browser intentionally supplies a no-op submit handler to SchemaForm.
    await user.click(screen.getByRole("button", { name: "Save" }))
    expect(screen.getByRole("heading", { name: "Troll" })).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: /Back/ }))

    expect(screen.getByRole("table")).toBeInTheDocument()
    expect(screen.getByRole("cell", { name: "Troll" })).toBeInTheDocument()
    expect(screen.queryByText("Edited troll")).not.toBeInTheDocument()
    expect(mockListCatalog).toHaveBeenCalledExactlyOnceWith("monster_catalog")
    expect(mockGetSchema).toHaveBeenCalledExactlyOnceWith("monster_catalog")
  })
})
