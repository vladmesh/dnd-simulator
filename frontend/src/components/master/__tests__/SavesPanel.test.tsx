import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Toaster } from "sonner"
import "@/i18n"
import { SavesPanel } from "../SavesPanel"
import { api } from "@/transport/apiClient"
import type { MessageResponse } from "@/types/api"

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      getSaves: vi.fn(),
      save: vi.fn(),
      loadSave: vi.fn(),
      deleteSave: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api.master)
const onLoaded = vi.fn()

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  const promise = new Promise<T>((res) => { resolve = res })
  return { promise, resolve }
}

function renderPanel() {
  return render(
    <>
      <SavesPanel sessionId="s1" onLoaded={onLoaded} />
      <Toaster />
    </>,
  )
}

// Use the unnamed role until the accessibility regression below is fixed.
function deleteButton(index = 0) {
  return screen.getAllByRole("button", { name: "" })[index]
}

beforeEach(() => {
  vi.resetAllMocks()
  mockApi.getSaves.mockResolvedValue({ saves: ["checkpoint"] })
  mockApi.save.mockResolvedValue({ message: "ok" })
  mockApi.loadSave.mockResolvedValue({ message: "ok" })
  mockApi.deleteSave.mockResolvedValue({ message: "ok" })
  vi.spyOn(window, "confirm").mockReturnValue(true)
  // Sonner observes the system colour scheme; jsdom does not implement matchMedia.
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
  }))
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe("SavesPanel", () => {
  it("keeps the save form available while loading, then shows the empty state", async () => {
    const request = deferred<{ saves: string[] }>()
    mockApi.getSaves.mockReturnValueOnce(request.promise)
    renderPanel()

    expect(mockApi.getSaves).toHaveBeenCalledWith("s1")
    expect(screen.getByRole("textbox")).toHaveAttribute("placeholder", "Save name (optional)")
    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled()
    expect(screen.queryByText("No saves.")).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Load" })).not.toBeInTheDocument()

    await act(async () => { request.resolve({ saves: [] }) })

    expect(await screen.findByText("No saves.")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Load" })).not.toBeInTheDocument()
    expect(screen.getAllByRole("button")).toHaveLength(1)
    expect(onLoaded).not.toHaveBeenCalled()
  })

  it("renders the returned save names and a load and delete action for each", async () => {
    mockApi.getSaves.mockResolvedValue({ saves: ["checkpoint", "earlier"] })
    renderPanel()

    expect(await screen.findByText("checkpoint")).toBeInTheDocument()
    expect(screen.getByText("earlier")).toBeInTheDocument()
    expect(screen.getByText("Saves")).toBeInTheDocument()
    expect(screen.queryByText("No saves.")).not.toBeInTheDocument()
    for (const button of screen.getAllByRole("button", { name: "Load" })) {
      expect(button).toBeEnabled()
    }
    expect(screen.getAllByRole("button", { name: "Load" })).toHaveLength(2)
    expect(screen.getAllByRole("button", { name: "" })).toHaveLength(2)
  })

  it.fails("gives the delete action an accessible name", async () => {
    renderPanel()
    await screen.findByText("checkpoint")

    // BUG: The icon-only delete button has no accessible name.
    expect(screen.getByRole("button", { name: "Delete" })).toBeEnabled()
  })

  it("saves a supplied name, prevents duplicate submissions, clears the input and refreshes", async () => {
    const request = deferred<MessageResponse>()
    mockApi.save.mockReturnValueOnce(request.promise)
    mockApi.getSaves
      .mockResolvedValueOnce({ saves: [] })
      .mockResolvedValueOnce({ saves: ["Evening & rest"] })
    renderPanel()
    await screen.findByText("No saves.")

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Evening & rest" } })
    const save = screen.getByRole("button", { name: "Save" })
    fireEvent.click(save)

    expect(mockApi.save).toHaveBeenCalledWith("s1", "Evening & rest")
    expect(save).toBeDisabled()
    fireEvent.click(save)
    expect(mockApi.save).toHaveBeenCalledTimes(1)
    expect(screen.getByRole("textbox")).toHaveValue("Evening & rest")
    expect(mockApi.getSaves).toHaveBeenCalledTimes(1)

    await act(async () => { request.resolve({ message: "ok" }) })

    expect(await screen.findByText("Saved.")).toBeInTheDocument()
    expect(await screen.findByText("Evening & rest")).toBeInTheDocument()
    expect(screen.getByRole("textbox")).toHaveValue("")
    expect(save).toBeEnabled()
    expect(mockApi.getSaves).toHaveBeenCalledTimes(2)
    expect(mockApi.getSaves).toHaveBeenLastCalledWith("s1")
    expect(onLoaded).not.toHaveBeenCalled()
  })

  it("passes undefined for an empty optional save name", async () => {
    renderPanel()
    await screen.findByText("checkpoint")

    fireEvent.click(screen.getByRole("button", { name: "Save" }))

    expect(mockApi.save).toHaveBeenCalledWith("s1", undefined)
    expect(await screen.findByText("Saved.")).toBeInTheDocument()
    expect(mockApi.getSaves).toHaveBeenCalledTimes(2)
  })

  it("shows a save error, retains the name and allows retrying without refreshing", async () => {
    mockApi.save.mockRejectedValueOnce(new Error("save failed"))
    renderPanel()
    await screen.findByText("checkpoint")
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "retry me" } })

    fireEvent.click(screen.getByRole("button", { name: "Save" }))

    expect(await screen.findByText("Error")).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole("button", { name: "Save" })).toBeEnabled())
    expect(mockApi.save).toHaveBeenCalledWith("s1", "retry me")
    expect(screen.getByRole("textbox")).toHaveValue("retry me")
    expect(screen.getByText("checkpoint")).toBeInTheDocument()
    expect(screen.queryByText("Saved.")).not.toBeInTheDocument()
    expect(mockApi.getSaves).toHaveBeenCalledTimes(1)
    expect(onLoaded).not.toHaveBeenCalled()
  })

  it("does not load a save when confirmation is cancelled", async () => {
    vi.mocked(window.confirm).mockReturnValue(false)
    renderPanel()
    await screen.findByText("checkpoint")

    fireEvent.click(screen.getByRole("button", { name: "Load" }))

    expect(window.confirm).toHaveBeenCalledWith("Load save checkpoint? Current state will be replaced.")
    expect(mockApi.loadSave).not.toHaveBeenCalled()
    expect(mockApi.getSaves).toHaveBeenCalledTimes(1)
    expect(onLoaded).not.toHaveBeenCalled()
    expect(screen.getByRole("button", { name: "Load" })).toBeEnabled()
    expect(deleteButton()).toBeEnabled()
    expect(screen.queryByText("Loaded.")).not.toBeInTheDocument()
  })

  it("loads the selected save, disables its actions while pending and notifies the parent", async () => {
    const request = deferred<MessageResponse>()
    mockApi.loadSave.mockReturnValueOnce(request.promise)
    mockApi.getSaves
      .mockResolvedValueOnce({ saves: ["earlier", "checkpoint"] })
      .mockResolvedValueOnce({ saves: ["earlier", "checkpoint", "after-load"] })
    renderPanel()
    await screen.findByText("checkpoint")
    const [otherLoad, selectedLoad] = screen.getAllByRole("button", { name: "Load" })

    fireEvent.click(selectedLoad)

    expect(window.confirm).toHaveBeenCalledWith("Load save checkpoint? Current state will be replaced.")
    expect(mockApi.loadSave).toHaveBeenCalledWith("s1", "checkpoint")
    expect(selectedLoad).toBeDisabled()
    expect(deleteButton(1)).toBeDisabled()
    expect(otherLoad).toBeEnabled()
    expect(deleteButton(0)).toBeEnabled()
    fireEvent.click(selectedLoad)
    expect(mockApi.loadSave).toHaveBeenCalledTimes(1)
    expect(onLoaded).not.toHaveBeenCalled()

    await act(async () => { request.resolve({ message: "ok" }) })

    expect(await screen.findByText("Loaded.")).toBeInTheDocument()
    expect(await screen.findByText("after-load")).toBeInTheDocument()
    expect(onLoaded).toHaveBeenCalledTimes(1)
    expect(onLoaded).toHaveBeenCalledWith()
    expect(mockApi.getSaves).toHaveBeenCalledTimes(2)
    expect(mockApi.getSaves).toHaveBeenLastCalledWith("s1")
    expect(selectedLoad).toBeEnabled()
    expect(deleteButton(1)).toBeEnabled()
  })

  it("shows a load error and restores the actions without notifying the parent", async () => {
    mockApi.loadSave.mockRejectedValueOnce(new Error("load failed"))
    renderPanel()
    await screen.findByText("checkpoint")

    fireEvent.click(screen.getByRole("button", { name: "Load" }))

    expect(await screen.findByText("Error")).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole("button", { name: "Load" })).toBeEnabled())
    expect(deleteButton()).toBeEnabled()
    expect(mockApi.loadSave).toHaveBeenCalledWith("s1", "checkpoint")
    expect(screen.getByText("checkpoint")).toBeInTheDocument()
    expect(screen.queryByText("Loaded.")).not.toBeInTheDocument()
    expect(mockApi.getSaves).toHaveBeenCalledTimes(1)
    expect(onLoaded).not.toHaveBeenCalled()
  })

  it("does not delete a save when confirmation is cancelled", async () => {
    vi.mocked(window.confirm).mockReturnValue(false)
    renderPanel()
    await screen.findByText("checkpoint")

    fireEvent.click(deleteButton())

    expect(window.confirm).toHaveBeenCalledWith("Delete save checkpoint?")
    expect(mockApi.deleteSave).not.toHaveBeenCalled()
    expect(mockApi.getSaves).toHaveBeenCalledTimes(1)
    expect(screen.getByText("checkpoint")).toBeInTheDocument()
    expect(deleteButton()).toBeEnabled()
    expect(screen.getByRole("button", { name: "Load" })).toBeEnabled()
    expect(screen.queryByText("Save deleted.")).not.toBeInTheDocument()
    expect(onLoaded).not.toHaveBeenCalled()
  })

  it("deletes a confirmed save, disables both actions while pending and refreshes to empty", async () => {
    const request = deferred<MessageResponse>()
    mockApi.deleteSave.mockReturnValueOnce(request.promise)
    mockApi.getSaves
      .mockResolvedValueOnce({ saves: ["checkpoint"] })
      .mockResolvedValueOnce({ saves: [] })
    renderPanel()
    await screen.findByText("checkpoint")
    const remove = deleteButton()

    fireEvent.click(remove)

    expect(window.confirm).toHaveBeenCalledWith("Delete save checkpoint?")
    expect(mockApi.deleteSave).toHaveBeenCalledWith("s1", "checkpoint")
    expect(remove).toBeDisabled()
    expect(screen.getByRole("button", { name: "Load" })).toBeDisabled()
    fireEvent.click(remove)
    expect(mockApi.deleteSave).toHaveBeenCalledTimes(1)
    expect(screen.getByText("checkpoint")).toBeInTheDocument()

    await act(async () => { request.resolve({ message: "ok" }) })

    expect(await screen.findByText("Save deleted.")).toBeInTheDocument()
    expect(await screen.findByText("No saves.")).toBeInTheDocument()
    expect(screen.queryByText("checkpoint")).not.toBeInTheDocument()
    expect(mockApi.getSaves).toHaveBeenCalledTimes(2)
    expect(mockApi.getSaves).toHaveBeenLastCalledWith("s1")
    expect(onLoaded).not.toHaveBeenCalled()
  })

  it("shows a delete error and keeps the save available without refreshing", async () => {
    mockApi.deleteSave.mockRejectedValueOnce(new Error("delete failed"))
    renderPanel()
    await screen.findByText("checkpoint")

    fireEvent.click(deleteButton())

    expect(await screen.findByText("Error")).toBeInTheDocument()
    await waitFor(() => expect(deleteButton()).toBeEnabled())
    expect(screen.getByRole("button", { name: "Load" })).toBeEnabled()
    expect(mockApi.deleteSave).toHaveBeenCalledWith("s1", "checkpoint")
    expect(screen.getByText("checkpoint")).toBeInTheDocument()
    expect(screen.queryByText("Save deleted.")).not.toBeInTheDocument()
    expect(mockApi.getSaves).toHaveBeenCalledTimes(1)
    expect(onLoaded).not.toHaveBeenCalled()
  })
})
