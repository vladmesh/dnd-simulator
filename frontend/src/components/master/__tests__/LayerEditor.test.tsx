import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import "@/i18n"
import { api, ApiError } from "@/transport/apiClient"
import type { LayerFilesResponse, MessageResponse } from "@/types/api"
import { LayerEditor } from "../LayerEditor"

vi.mock("@/transport/apiClient", async () => {
  const { ApiError } = await import("@/transport/requestCore")
  return {
    ApiError,
    api: {
      master: {
        getLayerFiles: vi.fn(),
        updateLayerFile: vi.fn(),
      },
    },
  }
})

const mockApi = vi.mocked(api.master)
const files: LayerFilesResponse = {
  files: {
    "regions.yaml": "regions: [forest]",
    "locations.yaml": "locations: [village]",
  },
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((fulfill) => {
    resolve = fulfill
  })
  return { promise, resolve }
}

function setup(readOnly = false) {
  const onClose = vi.fn()
  const view = render(
    <LayerEditor
      worldId="sword_vale"
      layerType="geography"
      readOnly={readOnly}
      onClose={onClose}
    />,
  )
  return { ...view, onClose }
}

describe("LayerEditor", () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mockApi.getLayerFiles.mockResolvedValue(files)
    mockApi.updateLayerFile.mockResolvedValue({ message: "Saved" })
  })

  it("withholds editor controls while files are loading", async () => {
    const loading = deferred<LayerFilesResponse>()
    mockApi.getLayerFiles.mockReturnValueOnce(loading.promise)
    setup()

    expect(mockApi.getLayerFiles).toHaveBeenCalledExactlyOnceWith("sword_vale", "geography")
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()

    await act(async () => loading.resolve(files))

    expect(screen.getByRole("textbox")).toHaveValue("regions: [forest]")
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled()
  })

  it("renders filenames and the first file, enabling Save only for changes", async () => {
    const user = userEvent.setup()
    setup()

    const editor = await screen.findByRole("textbox")
    expect(screen.getByRole("button", { name: "regions.yaml" })).toBeVisible()
    expect(screen.getByRole("button", { name: "locations.yaml" })).toBeVisible()
    expect(editor).toHaveValue("regions: [forest]")
    const save = screen.getByRole("button", { name: "Save" })
    expect(save).toBeDisabled()
    await user.click(save)
    expect(mockApi.updateLayerFile).not.toHaveBeenCalled()

    fireEvent.change(editor, { target: { value: "regions: [desert]" } })
    expect(save).toBeEnabled()
    fireEvent.change(editor, { target: { value: "regions: [forest]" } })
    expect(save).toBeDisabled()
  })

  it("switches files and resets unsaved edits without writing to the API", async () => {
    const user = userEvent.setup()
    setup()
    const editor = await screen.findByRole("textbox")
    fireEvent.change(editor, { target: { value: "unsaved regions" } })

    await user.click(screen.getByRole("button", { name: "locations.yaml" }))
    expect(editor).toHaveValue("locations: [village]")
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled()

    await user.click(screen.getByRole("button", { name: "regions.yaml" }))
    expect(editor).toHaveValue("regions: [forest]")
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled()
    expect(mockApi.getLayerFiles).toHaveBeenCalledTimes(1)
    expect(mockApi.updateLayerFile).not.toHaveBeenCalled()
  })

  it("saves the selected file, prevents duplicate saves, and retains saved content", async () => {
    const user = userEvent.setup()
    const saving = deferred<MessageResponse>()
    mockApi.updateLayerFile.mockReturnValueOnce(saving.promise)
    setup()
    await user.click(await screen.findByRole("button", { name: "locations.yaml" }))
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "locations: [castle]" } })

    const save = screen.getByRole("button", { name: "Save" })
    await user.click(save)
    expect(mockApi.updateLayerFile).toHaveBeenCalledExactlyOnceWith(
      "sword_vale", "geography", "locations.yaml", { content: "locations: [castle]" },
    )
    expect(save).toBeDisabled()
    await user.click(save)
    expect(mockApi.updateLayerFile).toHaveBeenCalledTimes(1)

    await act(async () => saving.resolve({ message: "Saved" }))
    expect(save).toBeDisabled()
    await user.click(screen.getByRole("button", { name: "regions.yaml" }))
    await user.click(screen.getByRole("button", { name: "locations.yaml" }))
    expect(screen.getByRole("textbox")).toHaveValue("locations: [castle]")
    expect(save).toBeDisabled()

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "locations: [village]" } })
    expect(save).toBeEnabled()
  })

  it("shows API error details, preserves edits, and allows a successful retry", async () => {
    const user = userEvent.setup()
    mockApi.updateLayerFile.mockRejectedValueOnce(new ApiError(403, { detail: "Layer is locked" }))
    setup()
    const editor = await screen.findByRole("textbox")
    fireEvent.change(editor, { target: { value: "regions: [desert]" } })
    const save = screen.getByRole("button", { name: "Save" })
    await user.click(save)

    expect(await screen.findByText("Layer is locked")).toBeVisible()
    expect(editor).toHaveValue("regions: [desert]")
    await waitFor(() => expect(save).toBeEnabled())
    await user.click(save)

    await waitFor(() => expect(save).toBeDisabled())
    expect(screen.queryByText("Layer is locked")).not.toBeInTheDocument()
    expect(mockApi.updateLayerFile).toHaveBeenCalledTimes(2)
    expect(mockApi.updateLayerFile).toHaveBeenLastCalledWith(
      "sword_vale", "geography", "regions.yaml", { content: "regions: [desert]" },
    )
  })

  it("shows non-API save errors and clears them when another file is selected", async () => {
    const user = userEvent.setup()
    mockApi.updateLayerFile.mockRejectedValueOnce(new Error("Connection lost"))
    setup()
    fireEvent.change(await screen.findByRole("textbox"), { target: { value: "changed" } })
    await user.click(screen.getByRole("button", { name: "Save" }))

    expect(await screen.findByText("Error: Connection lost")).toBeVisible()
    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled()
    await user.click(screen.getByRole("button", { name: "locations.yaml" }))
    expect(screen.queryByText("Error: Connection lost")).not.toBeInTheDocument()
    expect(screen.getByRole("textbox")).toHaveValue("locations: [village]")
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled()
  })

  it("allows browsing read-only files but not editing or saving", async () => {
    const user = userEvent.setup()
    setup(true)
    const editor = await screen.findByRole("textbox")
    expect(editor).toHaveAttribute("readonly")
    await user.type(editor, "cannot edit")
    expect(editor).toHaveValue("regions: [forest]")
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "locations.yaml" }))
    expect(editor).toHaveValue("locations: [village]")
    expect(mockApi.updateLayerFile).not.toHaveBeenCalled()
  })

  it("has no editing controls for an empty layer and still allows closing", async () => {
    const user = userEvent.setup()
    mockApi.getLayerFiles.mockResolvedValueOnce({ files: {} })
    const { onClose } = setup()

    // The icon-only close button currently has no accessible name.
    const close = await screen.findByRole("button", { name: "" })
    expect(screen.getAllByRole("button")).toHaveLength(1)
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument()
    await user.click(close)
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(mockApi.updateLayerFile).not.toHaveBeenCalled()
  })

  // BUG: Initial load errors are hidden because the error message requires a selected file.
  it.fails("shows a visible error when loading the layer files fails", async () => {
    mockApi.getLayerFiles.mockRejectedValueOnce(new Error("Network unavailable"))
    setup()

    await screen.findByRole("button", { name: "" })
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
    expect(screen.getByText("Failed to load layer files")).toBeVisible()
  })
})
