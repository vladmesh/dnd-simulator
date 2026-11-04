import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router"
import { Toaster, toast } from "sonner"
import i18n from "@/i18n"
import { api } from "@/transport/apiClient"
import type { MessageResponse, SessionListItem, SessionResponse, WorldListItem } from "@/types/api"
import { MasterScreen } from "../MasterScreen"

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      getSessions: vi.fn(),
      getWorlds: vi.fn(),
      createSession: vi.fn(),
      deleteSession: vi.fn(),
      forkWorld: vi.fn(),
      deleteWorld: vi.fn(),
      getWorldManifest: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api.master)
const worlds: WorldListItem[] = [
  { id: "base_valley", name: "Base Valley", description: "", editable: false },
  { id: "home_valley", name: "Home Valley", description: "Our campaign", editable: true },
]
const session: SessionListItem = {
  session_id: "session-123456789",
  player_name: "",
  player_location: "",
  time: "",
  world_name: "",
}
const createdSession: SessionResponse = {
  session_id: "new-session-123",
  player_name: "Aria",
  player_location: "Town",
  time: "Day 2",
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

function setup() {
  const user = userEvent.setup()
  render(
    <MemoryRouter initialEntries={["/master"]}>
      <MasterScreen />
      <Toaster />
    </MemoryRouter>,
  )
  return user
}

async function openSessions(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByText("Base Valley")
  await user.click(screen.getByRole("tab", { name: "Sessions" }))
}

function forkSubmit() {
  // The other Fork buttons belong to world cards, not the open form.
  return screen.getAllByRole("button", { name: "Fork" }).at(-1)!
}

function sessionDelete() {
  // Session deletion is icon-only; scope its unnamed button to the visible tab.
  return within(screen.getByRole("tabpanel", { name: "Sessions" }))
    .getByRole("button", { name: "" })
}

describe("MasterScreen uncovered branches", () => {
  beforeEach(async () => {
    vi.resetAllMocks()
    await i18n.changeLanguage("en")
    mockApi.getWorlds.mockResolvedValue(worlds)
    mockApi.getSessions.mockResolvedValue([])
  })

  afterEach(() => {
    toast.dismiss()
    cleanup()
    vi.restoreAllMocks()
  })

  it("keeps both tabs in loading state until the lists resolve, then shows empty states", async () => {
    const pendingWorlds = deferred<WorldListItem[]>()
    const pendingSessions = deferred<SessionListItem[]>()
    mockApi.getWorlds.mockReturnValue(pendingWorlds.promise)
    mockApi.getSessions.mockReturnValue(pendingSessions.promise)
    const user = setup()

    expect(screen.getByRole("heading", { name: "Dungeon Master" })).toBeVisible()
    expect(screen.queryByText("No worlds available.")).not.toBeInTheDocument()
    expect(mockApi.getSessions).toHaveBeenCalledWith()
    expect(mockApi.getWorlds).toHaveBeenCalledWith("en")
    await user.click(screen.getByRole("tab", { name: "Sessions" }))
    expect(screen.queryByText("No active sessions.")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "New Session" })).toBeDisabled()

    await act(async () => { pendingWorlds.resolve([]); pendingSessions.resolve([]) })
    expect(await screen.findByText("No active sessions.")).toBeVisible()
    await user.click(screen.getByRole("button", { name: "New Session" }))
    expect(mockApi.createSession).not.toHaveBeenCalled()
    await user.click(screen.getByRole("tab", { name: "Worlds" }))
    expect(screen.getByText("No worlds available.")).toBeVisible()
  })

  it("reports a list-loading failure and leaves session creation unavailable", async () => {
    mockApi.getWorlds.mockRejectedValue(new Error("unavailable"))
    const user = setup()
    expect(await screen.findByText("Error")).toBeVisible()
    expect(screen.getByText("No worlds available.")).toBeVisible()
    await user.click(screen.getByRole("tab", { name: "Sessions" }))
    expect(screen.getByText("No active sessions.")).toBeVisible()
    expect(screen.getByRole("button", { name: "New Session" })).toBeDisabled()
  })

  it("creates a session with the default world, blocks duplicate submissions and renders refreshed data", async () => {
    const pending = deferred<SessionResponse>()
    mockApi.createSession.mockReturnValue(pending.promise)
    const user = setup()
    await openSessions(user)
    const create = screen.getByRole("button", { name: "New Session" })
    await user.click(create)
    expect(mockApi.createSession).toHaveBeenCalledExactlyOnceWith({ world_name: "base_valley", lang: "en" })
    expect(create).toBeDisabled()
    await user.click(create)
    expect(mockApi.createSession).toHaveBeenCalledTimes(1)

    mockApi.getSessions.mockResolvedValue([{ ...createdSession, world_name: "base_valley" }])
    const previousReads = mockApi.getSessions.mock.calls.length
    await act(async () => pending.resolve(createdSession))
    expect(await screen.findByText("Aria · Day 2 · base_valley")).toBeVisible()
    expect(await within(screen.getByRole("region", { name: /notifications/i })).findByText("New Session")).toBeVisible()
    expect(mockApi.getSessions.mock.calls.length).toBeGreaterThan(previousReads)
    expect(mockApi.getWorlds).toHaveBeenLastCalledWith("en")
    expect(create).toBeEnabled()
  })

  it("uses the newly selected world and recovers from a session-creation error", async () => {
    mockApi.createSession.mockRejectedValue(new Error("creation failed"))
    const user = setup()
    await openSessions(user)
    await user.click(screen.getByRole("combobox"))
    await user.click(await screen.findByRole("option", { name: "Home Valley" }))
    expect(screen.getByRole("combobox")).toHaveTextContent("Home Valley")
    const previousReads = mockApi.getSessions.mock.calls.length
    const create = screen.getByRole("button", { name: "New Session" })
    await user.click(create)
    expect(mockApi.createSession).toHaveBeenCalledExactlyOnceWith({ world_name: "home_valley", lang: "en" })
    expect(await screen.findByText("Error")).toBeVisible()
    expect(create).toBeEnabled()
    expect(mockApi.getSessions).toHaveBeenCalledTimes(previousReads)
    expect(screen.getByText("No active sessions.")).toBeVisible()
  })

  it("renders missing session details and only deletes the full session ID after confirmation", async () => {
    mockApi.getSessions.mockResolvedValue([session])
    const pending = deferred<MessageResponse>()
    mockApi.deleteSession.mockReturnValue(pending.promise)
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false)
    const user = setup()
    await openSessions(user)
    expect(screen.getByText("session-")).toBeVisible()
    expect(screen.getByText("—")).toBeVisible()
    const remove = sessionDelete()
    await user.click(remove)
    expect(confirm).toHaveBeenCalledWith("Delete session session-123456789?")
    expect(mockApi.deleteSession).not.toHaveBeenCalled()
    expect(remove).toBeEnabled()

    confirm.mockReturnValue(true)
    await user.click(remove)
    expect(mockApi.deleteSession).toHaveBeenCalledExactlyOnceWith(session.session_id)
    expect(remove).toBeDisabled()
    mockApi.getSessions.mockResolvedValue([])
    await act(async () => pending.resolve({ message: "deleted" }))
    expect(await screen.findByText("Session deleted.")).toBeVisible()
    expect(await screen.findByText("No active sessions.")).toBeVisible()
    expect(screen.queryByText("session-")).not.toBeInTheDocument()
  })

  it("keeps a session and re-enables deletion when the API rejects it", async () => {
    mockApi.getSessions.mockResolvedValue([session])
    const pending = deferred<MessageResponse>()
    mockApi.deleteSession.mockReturnValue(pending.promise)
    vi.spyOn(window, "confirm").mockReturnValue(true)
    const user = setup()
    await openSessions(user)
    const previousReads = mockApi.getSessions.mock.calls.length
    const remove = sessionDelete()
    await user.click(remove)
    expect(remove).toBeDisabled()
    await act(async () => pending.reject(new Error("delete failed")))
    expect(await screen.findByText("Error")).toBeVisible()
    expect(remove).toBeEnabled()
    expect(screen.getByText("session-")).toBeVisible()
    expect(mockApi.deleteSession).toHaveBeenCalledExactlyOnceWith(session.session_id)
    expect(mockApi.getSessions).toHaveBeenCalledTimes(previousReads)
  })

  it("cancels world deletion and restores the delete control after a rejected request", async () => {
    const pending = deferred<MessageResponse>()
    mockApi.deleteWorld.mockReturnValue(pending.promise)
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false)
    const user = setup()
    await screen.findByText("Home Valley")
    const remove = screen.getByRole("button", { name: "Delete" })
    await user.click(remove)
    expect(confirm).toHaveBeenCalledWith("Delete world home_valley? This cannot be undone.")
    expect(mockApi.deleteWorld).not.toHaveBeenCalled()
    expect(remove).toBeEnabled()

    confirm.mockReturnValue(true)
    const previousReads = mockApi.getWorlds.mock.calls.length
    await user.click(remove)
    expect(mockApi.deleteWorld).toHaveBeenCalledExactlyOnceWith("home_valley")
    expect(remove).toBeDisabled()
    // Clicking the action must not also open the editor on the parent card.
    expect(mockApi.getWorldManifest).not.toHaveBeenCalled()
    await act(async () => pending.reject(new Error("world in use")))
    expect(await screen.findByText("Error")).toBeVisible()
    expect(remove).toBeEnabled()
    expect(screen.getByText("Home Valley")).toBeVisible()
    expect(mockApi.getWorlds).toHaveBeenCalledTimes(previousReads)
  })

  it("disables empty or whitespace-only forks and discards the draft on cancellation", async () => {
    const user = setup()
    await screen.findByText("Base Valley")
    await user.click(screen.getAllByRole("button", { name: "Fork" })[0])
    expect(forkSubmit()).toBeDisabled()
    await user.type(screen.getByRole("textbox", { name: "ID" }), "   ")
    expect(forkSubmit()).toBeDisabled()
    await user.click(forkSubmit())
    expect(mockApi.forkWorld).not.toHaveBeenCalled()
    await user.type(screen.getByRole("textbox", { name: "ID" }), "draft")
    expect(forkSubmit()).toBeEnabled()
    await user.click(screen.getByRole("button", { name: "Cancel" }))
    expect(screen.queryByRole("textbox", { name: "ID" })).not.toBeInTheDocument()
    await user.click(screen.getAllByRole("button", { name: "Fork" })[1])
    expect(screen.getByText("Fork world: home_valley")).toBeVisible()
    expect(screen.getByRole("textbox", { name: "ID" })).toHaveValue("")
    expect(forkSubmit()).toBeDisabled()
    expect(mockApi.forkWorld).not.toHaveBeenCalled()
    expect(mockApi.getWorldManifest).not.toHaveBeenCalled()
  })

  it("trims a fork ID, blocks resubmission while pending and retains the draft on failure", async () => {
    const pending = deferred<WorldListItem>()
    mockApi.forkWorld.mockReturnValue(pending.promise)
    const user = setup()
    await screen.findByText("Base Valley")
    await user.click(screen.getAllByRole("button", { name: "Fork" })[0])
    await user.type(screen.getByRole("textbox", { name: "ID" }), "  new_valley  ")
    const submit = forkSubmit()
    const previousReads = mockApi.getWorlds.mock.calls.length
    await user.click(submit)
    expect(mockApi.forkWorld).toHaveBeenCalledExactlyOnceWith("base_valley", { new_id: "new_valley" })
    expect(submit).toBeDisabled()
    await user.click(submit)
    expect(mockApi.forkWorld).toHaveBeenCalledTimes(1)
    await act(async () => pending.reject(new Error("duplicate ID")))
    expect(await screen.findByText("Failed to fork world")).toBeVisible()
    expect(screen.getByRole("textbox", { name: "ID" })).toHaveValue("  new_valley  ")
    expect(submit).toBeEnabled()
    expect(mockApi.getWorlds).toHaveBeenCalledTimes(previousReads)
  })

  it("shows the world ID for an empty description and returns from an editable world's editor", async () => {
    // A layer without entity editors keeps this test focused on MasterScreen's close callback.
    mockApi.getWorldManifest.mockResolvedValue({
      world_id: "home_valley",
      name: "Home Valley",
      layers: [{ layer_type: "rules", source: "custom", template: null, version: null }],
    })
    const user = setup()
    expect(await screen.findByText("base_valley")).toBeVisible()
    await user.click(screen.getByText("Home Valley"))
    await user.click(await screen.findByRole("button", { name: "Close" }))
    expect(await screen.findByText("Our campaign")).toBeVisible()
    expect(screen.queryByRole("button", { name: "Close" })).not.toBeInTheDocument()
    expect(mockApi.getWorldManifest).toHaveBeenCalledExactlyOnceWith("home_valley", "en")
  })

  it("refreshes localized worlds when the language changes", async () => {
    const user = setup()
    await screen.findByText("Base Valley")
    const previousReads = mockApi.getSessions.mock.calls.length
    await user.click(screen.getByRole("button", { name: "RU" }))
    await waitFor(() => expect(mockApi.getWorlds).toHaveBeenLastCalledWith("ru"))
    expect(mockApi.getSessions.mock.calls.length).toBeGreaterThan(previousReads)
    expect(screen.getByRole("heading", { name: i18n.t("master:title") })).toBeVisible()
    // Restore the shared i18n instance without triggering another mounted refresh.
    cleanup()
    await i18n.changeLanguage("en")
  })
})
