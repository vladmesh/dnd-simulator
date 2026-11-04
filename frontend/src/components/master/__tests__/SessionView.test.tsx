import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter, Route, Routes } from "react-router"
import { toast } from "sonner"
import "@/i18n"
import { api } from "@/transport/apiClient"
import type { MessageResponse, WorldStateResponse } from "@/types/api"
import { SessionView } from "../SessionView"

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      getSession: vi.fn(),
      getCreatures: vi.fn(),
      advanceTime: vi.fn(),
      getSaves: vi.fn(),
      save: vi.fn(),
      loadSave: vi.fn(),
      deleteSave: vi.fn(),
    },
  },
}))

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }))

const mockApi = vi.mocked(api.master)
const sessionId = "campaign-12345678"
const world: WorldStateResponse = {
  session_id: sessionId,
  time: "Day 1, 08:00",
  regions: [{
    id: "moonvale",
    name: "Moonvale",
    latitude: 0,
    longitude: 0,
    elevation: 100,
    terrain: "forest",
    water_proximity: 0,
    weather: { condition: "Clear", temperature: 18 },
    temperature: 18,
  }],
  nations: [],
  settlements: [],
  entities: [],
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => { resolve = res })
  return { promise, resolve }
}

function renderView(path = `/master/${sessionId}`) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/master/:sessionId" element={<SessionView />} />
        <Route path="/without-session" element={<SessionView />} />
        <Route path="/master" element={<h1>Session list</h1>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.resetAllMocks()
  localStorage.clear()
  mockApi.getSession.mockResolvedValue(world)
  mockApi.getCreatures.mockResolvedValue([])
  mockApi.advanceTime.mockResolvedValue({ message: "Advanced one hour" })
  mockApi.getSaves.mockResolvedValue({ saves: [] })
  mockApi.save.mockResolvedValue({ message: "Saved" })
  mockApi.loadSave.mockResolvedValue({ message: "Loaded" })
  mockApi.deleteSave.mockResolvedValue({ message: "Deleted" })
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.restoreAllMocks()
})

// Live-tab/socket behaviour is covered separately by SessionView.live.test.tsx.
describe("SessionView loading and refresh", () => {
  it("withholds world content while loading, renders the response, and links back to sessions", async () => {
    const user = userEvent.setup()
    const request = deferred<WorldStateResponse>()
    mockApi.getSession.mockReturnValueOnce(request.promise)
    renderView()

    expect(mockApi.getSession).toHaveBeenCalledWith(sessionId)
    expect(screen.getByRole("heading", { name: "campaign" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Back to sessions" })).toHaveAttribute("href", "/master")
    // The skeletons have no accessible loading label; check that data is withheld.
    expect(screen.queryByRole("heading", { name: "Regions" })).not.toBeInTheDocument()
    expect(screen.queryByText("No regions.")).not.toBeInTheDocument()
    expect(screen.queryByText(world.time)).not.toBeInTheDocument()

    await act(async () => { request.resolve(world) })

    expect(await screen.findByText(world.time)).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Regions" })).toBeInTheDocument()
    expect(screen.getByRole("cell", { name: "Moonvale" })).toBeInTheDocument()
    expect(screen.getByRole("cell", { name: "forest" })).toBeInTheDocument()
    expect(screen.getByRole("cell", { name: "Clear, 18°" })).toBeInTheDocument()

    await user.click(screen.getByRole("link", { name: "Back to sessions" }))
    expect(screen.getByRole("heading", { name: "Session list" })).toBeInTheDocument()
  })

  it("renders nothing and skips both initial and periodic requests without a session id", async () => {
    vi.useFakeTimers()
    renderView("/without-session")

    expect(screen.queryByRole("heading")).not.toBeInTheDocument()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    await act(async () => { await vi.advanceTimersByTimeAsync(10000) })
    expect(mockApi.getSession).not.toHaveBeenCalled()
  })

  it("shows an initial fetch error and finishes loading so other tabs remain usable", async () => {
    const user = userEvent.setup()
    mockApi.getSession.mockRejectedValueOnce(new Error("Not found"))
    renderView()

    expect(await screen.findByText("Session not found.")).toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "Regions" })).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Time" }))
    expect(screen.getByRole("spinbutton")).toHaveValue(1)
    expect(screen.getByRole("button", { name: "Advance" })).toBeEnabled()
  })

  it("polls every five seconds, preserves data on failure, updates on recovery, and stops on unmount", async () => {
    vi.useFakeTimers()
    const { unmount } = renderView()
    await act(async () => { await Promise.resolve() })
    expect(screen.getByText(world.time)).toBeInTheDocument()

    mockApi.getSession
      .mockRejectedValueOnce(new Error("Offline"))
      .mockResolvedValueOnce({ ...world, time: "Day 2, 08:00", regions: [] })

    await act(async () => { await vi.advanceTimersByTimeAsync(4999) })
    expect(mockApi.getSession).toHaveBeenCalledTimes(1)
    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    expect(mockApi.getSession).toHaveBeenCalledTimes(2)
    expect(screen.getByText(world.time)).toBeInTheDocument()
    expect(screen.getByRole("cell", { name: "Moonvale" })).toBeInTheDocument()
    expect(screen.queryByText("Session not found.")).not.toBeInTheDocument()

    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(mockApi.getSession).toHaveBeenNthCalledWith(3, sessionId)
    expect(screen.getByText("Day 2, 08:00")).toBeInTheDocument()
    expect(screen.getByText("No regions.")).toBeInTheDocument()
    expect(screen.queryByText("Moonvale")).not.toBeInTheDocument()

    unmount()
    await act(async () => { await vi.advanceTimersByTimeAsync(10000) })
    expect(mockApi.getSession).toHaveBeenCalledTimes(3)
  })

  it("opens the creatures tab with the session id and returns to an empty world", async () => {
    const user = userEvent.setup()
    mockApi.getSession.mockResolvedValueOnce({ ...world, regions: [] })
    renderView()
    await screen.findByText("No regions.")
    expect(screen.getByText("No nations.")).toBeInTheDocument()
    expect(screen.getByText("No settlements.")).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Creatures" }))
    expect(await screen.findByText("No creatures.")).toBeInTheDocument()
    expect(mockApi.getCreatures).toHaveBeenCalledWith(sessionId, undefined)
    expect(screen.queryByText("No regions.")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "World" }))
    expect(screen.getByText("No regions.")).toBeInTheDocument()
    expect(screen.queryByText("No creatures.")).not.toBeInTheDocument()
  })
})

describe("SessionView time controls", () => {
  it("advances the chosen hours, disables duplicate submissions, and refreshes the session on success", async () => {
    const user = userEvent.setup()
    const request = deferred<MessageResponse>()
    mockApi.advanceTime.mockReturnValueOnce(request.promise)
    renderView()
    await screen.findByText(world.time)
    await user.click(screen.getByRole("button", { name: "Time" }))
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "6" } })
    await user.click(screen.getByRole("button", { name: "Advance" }))

    expect(mockApi.advanceTime).toHaveBeenCalledWith(sessionId, { hours: 6 })
    expect(screen.getByRole("button", { name: "Advance" })).toBeDisabled()
    mockApi.getSession.mockResolvedValue({ ...world, time: "Day 1, 14:00" })
    await act(async () => { request.resolve({ message: "Six hours passed" }) })

    expect(await screen.findByText("Six hours passed")).toBeInTheDocument()
    expect(await screen.findByText("Day 1, 14:00")).toBeInTheDocument()
    expect(mockApi.getSession).toHaveBeenNthCalledWith(2, sessionId)
    expect(toast.success).toHaveBeenCalledWith("Time advanced.")
    expect(screen.getByRole("button", { name: "Advance" })).toBeEnabled()
  })

  it("prevents zero-hour advances and reports a failed advance without refreshing the world", async () => {
    const user = userEvent.setup()
    mockApi.advanceTime.mockRejectedValueOnce(new Error("Offline"))
    renderView()
    await screen.findByText(world.time)
    await user.click(screen.getByRole("button", { name: "Time" }))

    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "" } })
    expect(screen.getByRole("button", { name: "Advance" })).toBeDisabled()
    await user.click(screen.getByRole("button", { name: "Advance" }))
    expect(mockApi.advanceTime).not.toHaveBeenCalled()

    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "2" } })
    await user.click(screen.getByRole("button", { name: "Advance" }))
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Error"))
    expect(mockApi.advanceTime).toHaveBeenCalledWith(sessionId, { hours: 2 })
    expect(mockApi.getSession).toHaveBeenCalledTimes(1)
    expect(screen.getByText(world.time)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Advance" })).toBeEnabled()
    expect(toast.success).not.toHaveBeenCalled()
  })
})

describe("SessionView saves", () => {
  it("shows empty saves, creates a named save, and refreshes the list without refreshing the world", async () => {
    const user = userEvent.setup()
    const request = deferred<MessageResponse>()
    mockApi.save.mockReturnValueOnce(request.promise)
    renderView()
    await screen.findByText(world.time)
    await user.click(screen.getByRole("button", { name: "Saves" }))
    expect(await screen.findByText("No saves.")).toBeInTheDocument()
    expect(mockApi.getSaves).toHaveBeenCalledWith(sessionId)

    await user.type(screen.getByRole("textbox"), "checkpoint")
    await user.click(screen.getByRole("button", { name: "Save" }))
    expect(mockApi.save).toHaveBeenCalledWith(sessionId, "checkpoint")
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled()
    mockApi.getSaves.mockResolvedValue({ saves: ["checkpoint"] })
    await act(async () => { request.resolve({ message: "Saved" }) })

    expect(await screen.findByText("checkpoint")).toBeInTheDocument()
    expect(screen.getByRole("textbox")).toHaveValue("")
    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled()
    expect(mockApi.getSaves).toHaveBeenCalledTimes(2)
    expect(mockApi.getSession).toHaveBeenCalledTimes(1)
    expect(toast.success).toHaveBeenCalledWith("Saved.")
  })

  it("passes undefined for an unnamed save and reports failures without refreshing either list or world", async () => {
    const user = userEvent.setup()
    mockApi.save.mockRejectedValueOnce(new Error("Disk full"))
    renderView()
    await screen.findByText(world.time)
    await user.click(screen.getByRole("button", { name: "Saves" }))
    await screen.findByText("No saves.")
    await user.click(screen.getByRole("button", { name: "Save" }))

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Error"))
    expect(mockApi.save).toHaveBeenCalledWith(sessionId, undefined)
    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled()
    expect(screen.getByText("No saves.")).toBeInTheDocument()
    expect(mockApi.getSaves).toHaveBeenCalledTimes(1)
    expect(mockApi.getSession).toHaveBeenCalledTimes(1)
  })

  it("loads a confirmed save and refreshes both the saves and the displayed session", async () => {
    const user = userEvent.setup()
    const request = deferred<MessageResponse>()
    const confirm = vi.spyOn(globalThis, "confirm").mockReturnValue(true)
    mockApi.getSaves.mockResolvedValue({ saves: ["checkpoint"] })
    mockApi.loadSave.mockReturnValueOnce(request.promise)
    renderView()
    await screen.findByText(world.time)
    await user.click(screen.getByRole("button", { name: "Saves" }))
    await screen.findByText("checkpoint")
    await user.click(screen.getByRole("button", { name: "Load" }))

    expect(confirm).toHaveBeenCalledWith("Load save checkpoint? Current state will be replaced.")
    expect(mockApi.loadSave).toHaveBeenCalledWith(sessionId, "checkpoint")
    expect(screen.getByRole("button", { name: "Load" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "" })).toBeDisabled()
    mockApi.getSession.mockResolvedValue({ ...world, time: "Day 0, 12:00" })
    await act(async () => { request.resolve({ message: "Loaded" }) })

    expect(await screen.findByText("Day 0, 12:00")).toBeInTheDocument()
    expect(mockApi.getSession).toHaveBeenNthCalledWith(2, sessionId)
    expect(mockApi.getSaves).toHaveBeenNthCalledWith(2, sessionId)
    expect(screen.getByRole("button", { name: "Load" })).toBeEnabled()
    expect(toast.success).toHaveBeenCalledWith("Loaded.")
  })

  it("does not load after cancellation or refresh the session after a load error", async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true)
    mockApi.getSaves.mockResolvedValue({ saves: ["checkpoint"] })
    mockApi.loadSave.mockRejectedValueOnce(new Error("Invalid save"))
    renderView()
    await screen.findByText(world.time)
    await user.click(screen.getByRole("button", { name: "Saves" }))
    await screen.findByText("checkpoint")
    await user.click(screen.getByRole("button", { name: "Load" }))
    expect(mockApi.loadSave).not.toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: "Load" }))
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Error"))
    expect(mockApi.loadSave).toHaveBeenCalledExactlyOnceWith(sessionId, "checkpoint")
    expect(mockApi.getSession).toHaveBeenCalledTimes(1)
    expect(mockApi.getSaves).toHaveBeenCalledTimes(1)
    expect(screen.getByText(world.time)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Load" })).toBeEnabled()
    expect(toast.success).not.toHaveBeenCalled()
  })

  it("requires confirmation to delete a save, allows retry on failure, and refreshes the list on success", async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, "confirm").mockReturnValueOnce(false).mockReturnValue(true)
    mockApi.getSaves.mockResolvedValue({ saves: ["checkpoint"] })
    mockApi.deleteSave.mockRejectedValueOnce(new Error("Offline"))
    renderView()
    await screen.findByText(world.time)
    await user.click(screen.getByRole("button", { name: "Saves" }))
    await screen.findByText("checkpoint")
    // The delete action is the only unlabelled button in the saves panel.
    await user.click(screen.getByRole("button", { name: "" }))
    expect(mockApi.deleteSave).not.toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: "" }))
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Error"))
    expect(screen.getByText("checkpoint")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "" })).toBeEnabled()
    expect(mockApi.getSaves).toHaveBeenCalledTimes(1)

    mockApi.getSaves.mockResolvedValue({ saves: [] })
    await user.click(screen.getByRole("button", { name: "" }))
    expect(await screen.findByText("No saves.")).toBeInTheDocument()
    expect(mockApi.deleteSave).toHaveBeenNthCalledWith(1, sessionId, "checkpoint")
    expect(mockApi.deleteSave).toHaveBeenNthCalledWith(2, sessionId, "checkpoint")
    expect(toast.success).toHaveBeenCalledWith("Save deleted.")
    expect(mockApi.getSession).toHaveBeenCalledTimes(1)
  })
})
