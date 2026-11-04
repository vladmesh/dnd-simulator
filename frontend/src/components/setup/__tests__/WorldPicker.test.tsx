import { act, cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import i18n from "@/i18n"
import { api } from "@/transport/apiClient"
import type { SessionResponse, WorldListItem } from "@/types/api"
import { WorldPicker } from "../WorldPicker"

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      getWorlds: vi.fn(),
      createSession: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api.master)
const originalLanguage = i18n.language
const originalStoredLanguage = localStorage.getItem("i18n_lang")
const worlds: WorldListItem[] = [
  { id: "moon_coast", name: "Moon Coast", description: "An island adventure", editable: false },
  { id: "ash_desert", name: "Ash Desert", description: "", editable: true },
]
const session: SessionResponse = {
  session_id: "new-session-42",
  player_name: "",
  player_location: "",
  time: "Y1490 M6 D1 10:00",
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

function setup() {
  const onWorldSelected = vi.fn()
  render(<WorldPicker onWorldSelected={onWorldSelected} />)
  return { onWorldSelected }
}

describe("WorldPicker", () => {
  beforeEach(async () => {
    vi.resetAllMocks()
    await i18n.changeLanguage("en")
    mockApi.getWorlds.mockResolvedValue(worlds)
  })

  afterEach(async () => {
    cleanup()
    await i18n.changeLanguage(originalLanguage)
    if (originalStoredLanguage === null) {
      localStorage.removeItem("i18n_lang")
    } else {
      localStorage.setItem("i18n_lang", originalStoredLanguage)
    }
  })

  it("withholds world choices until the initial language-specific request completes", async () => {
    const request = deferred<WorldListItem[]>()
    mockApi.getWorlds.mockReturnValue(request.promise)
    const { onWorldSelected } = setup()

    expect(mockApi.getWorlds).toHaveBeenCalledExactlyOnceWith("en")
    // The loading spinner has no accessible label; assert the visible choices are withheld.
    expect(screen.queryByRole("button", { name: "New Session" })).not.toBeInTheDocument()
    expect(screen.queryByText("Moon Coast")).not.toBeInTheDocument()
    expect(screen.queryByText("No worlds available. Create one via the Master API.")).not.toBeInTheDocument()
    expect(mockApi.createSession).not.toHaveBeenCalled()
    expect(onWorldSelected).not.toHaveBeenCalled()

    await act(async () => request.resolve(worlds))

    expect(await screen.findByText("Moon Coast")).toBeInTheDocument()
    expect(screen.getAllByRole("button", { name: "New Session" })).toHaveLength(2)
  })

  it("renders every world and falls back to its id when the description is empty", async () => {
    setup()

    expect(await screen.findByText("An island adventure")).toBeInTheDocument()
    expect(screen.getByText("Moon Coast")).toBeInTheDocument()
    expect(screen.getByText("Ash Desert")).toBeInTheDocument()
    expect(screen.getByText("ash_desert")).toBeInTheDocument()
    for (const button of screen.getAllByRole("button", { name: "New Session" })) {
      expect(button).toBeEnabled()
    }
  })

  it("shows the empty-world message without offering session creation", async () => {
    mockApi.getWorlds.mockResolvedValue([])
    const { onWorldSelected } = setup()

    expect(await screen.findByText("No worlds available. Create one via the Master API.")).toBeInTheDocument()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(mockApi.createSession).not.toHaveBeenCalled()
    expect(onWorldSelected).not.toHaveBeenCalled()
  })

  it("shows a load error instead of the empty-world message when fetching fails", async () => {
    mockApi.getWorlds.mockRejectedValue(new Error("World service unavailable"))
    const { onWorldSelected } = setup()

    expect(await screen.findByText("Failed to load worlds")).toBeInTheDocument()
    expect(screen.queryByText("No worlds available. Create one via the Master API.")).not.toBeInTheDocument()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(mockApi.createSession).not.toHaveBeenCalled()
    expect(onWorldSelected).not.toHaveBeenCalled()
  })

  it("disables every choice during creation, sends the selected id, and returns the new session id", async () => {
    const user = userEvent.setup()
    const request = deferred<SessionResponse>()
    mockApi.createSession.mockReturnValue(request.promise)
    const { onWorldSelected } = setup()
    const buttons = await screen.findAllByRole("button", { name: "New Session" })

    await user.click(buttons[1])

    expect(mockApi.createSession).toHaveBeenCalledExactlyOnceWith({ world_name: "ash_desert", lang: "en" })
    for (const button of buttons) expect(button).toBeDisabled()
    expect(onWorldSelected).not.toHaveBeenCalled()
    await user.click(buttons[0])
    await user.click(buttons[1])
    expect(mockApi.createSession).toHaveBeenCalledTimes(1)

    await act(async () => request.resolve(session))

    await waitFor(() => {
      expect(onWorldSelected).toHaveBeenCalledExactlyOnceWith("new-session-42")
    })
  })

  it("shows a session creation error without selecting a world when creation fails", async () => {
    const user = userEvent.setup()
    mockApi.createSession.mockRejectedValue(new Error("Session service unavailable"))
    const { onWorldSelected } = setup()
    const buttons = await screen.findAllByRole("button", { name: "New Session" })

    await user.click(buttons[0])

    expect(await screen.findByText("Failed to create session")).toBeInTheDocument()
    expect(mockApi.createSession).toHaveBeenCalledExactlyOnceWith({ world_name: "moon_coast", lang: "en" })
    expect(screen.queryByText("Failed to load worlds")).not.toBeInTheDocument()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(onWorldSelected).not.toHaveBeenCalled()
  })

  it("reloads localized worlds and uses the current language when creating a session", async () => {
    const user = userEvent.setup()
    mockApi.createSession.mockResolvedValue(session)
    const { onWorldSelected } = setup()
    await screen.findByText("Moon Coast")
    mockApi.getWorlds.mockResolvedValue([
      { ...worlds[0], name: "Лунный берег", description: "Островное приключение" },
    ])

    await act(async () => {
      await i18n.changeLanguage("ru")
    })

    expect(await screen.findByText("Лунный берег")).toBeInTheDocument()
    expect(screen.getByText("Островное приключение")).toBeInTheDocument()
    expect(screen.queryByText("Moon Coast")).not.toBeInTheDocument()
    expect(mockApi.getWorlds).toHaveBeenCalledTimes(2)
    expect(mockApi.getWorlds).toHaveBeenNthCalledWith(2, "ru")
    await user.click(screen.getByRole("button", { name: "Новая сессия" }))

    expect(mockApi.createSession).toHaveBeenCalledExactlyOnceWith({ world_name: "moon_coast", lang: "ru" })
    await waitFor(() => {
      expect(onWorldSelected).toHaveBeenCalledExactlyOnceWith(session.session_id)
    })
  })
})
