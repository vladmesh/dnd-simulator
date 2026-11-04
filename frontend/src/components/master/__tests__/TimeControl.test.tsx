import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { toast, Toaster } from "sonner"
import "@/i18n"
import { api } from "@/transport/apiClient"
import type { MessageResponse } from "@/types/api"
import { TimeControl } from "../TimeControl"

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      advanceTime: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api.master)
const onAdvanced = vi.fn()

function renderTimeControl(sessionId = "session-1") {
  return render(
    <>
      <TimeControl sessionId={sessionId} onAdvanced={onAdvanced} />
      <Toaster />
    </>,
  )
}

function pendingResponse() {
  let resolve!: (response: MessageResponse) => void
  const promise = new Promise<MessageResponse>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

beforeEach(() => {
  vi.resetAllMocks()
  toast.dismiss()
  mockApi.advanceTime.mockResolvedValue({ message: "The world clock moved forward." })
})

describe("TimeControl", () => {
  it("renders the initial controls with one hour and does not advance on mount", () => {
    renderTimeControl()

    expect(screen.getByText("Advance Time")).toBeInTheDocument()
    expect(screen.getByText("Hours")).toBeInTheDocument()
    expect(screen.getByRole("spinbutton")).toHaveValue(1)
    expect(screen.getByRole("button", { name: "Advance" })).toBeEnabled()
    expect(screen.queryByText("Time advanced.")).not.toBeInTheDocument()
    expect(mockApi.advanceTime).not.toHaveBeenCalled()
    expect(onAdvanced).not.toHaveBeenCalled()
  })

  it("advances by the default hour, renders the response and announces success", async () => {
    renderTimeControl()

    fireEvent.click(screen.getByRole("button", { name: "Advance" }))

    expect(mockApi.advanceTime).toHaveBeenCalledExactlyOnceWith("session-1", { hours: 1 })
    expect(await screen.findByText("The world clock moved forward.")).toBeInTheDocument()
    expect(await screen.findByText("Time advanced.")).toBeInTheDocument()
    expect(onAdvanced).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(screen.getByRole("button", { name: "Advance" })).toBeEnabled())
  })

  it("submits an edited number of hours at the supported upper boundary for the supplied session", async () => {
    renderTimeControl("another-session")

    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "8760" } })
    expect(screen.getByRole("spinbutton")).toHaveValue(8760)
    fireEvent.click(screen.getByRole("button", { name: "Advance" }))

    expect(mockApi.advanceTime).toHaveBeenCalledExactlyOnceWith("another-session", { hours: 8760 })
    expect(await screen.findByText("The world clock moved forward.")).toBeInTheDocument()
    expect(onAdvanced).toHaveBeenCalledTimes(1)
  })

  it("disables advance while a request is pending and prevents duplicate submissions", async () => {
    const pending = pendingResponse()
    mockApi.advanceTime.mockReturnValueOnce(pending.promise)
    renderTimeControl()
    const button = screen.getByRole("button", { name: "Advance" })

    fireEvent.click(button)

    expect(button).toBeDisabled()
    expect(onAdvanced).not.toHaveBeenCalled()
    expect(screen.queryByText("The world clock moved forward.")).not.toBeInTheDocument()
    fireEvent.click(button)
    expect(mockApi.advanceTime).toHaveBeenCalledTimes(1)

    await act(async () => pending.resolve({ message: "A day has passed." }))

    expect(screen.getByText("A day has passed.")).toBeInTheDocument()
    expect(button).toBeEnabled()
    expect(onAdvanced).toHaveBeenCalledTimes(1)
  })

  it("clears the previous result during the next request and displays the new result", async () => {
    const pending = pendingResponse()
    mockApi.advanceTime
      .mockResolvedValueOnce({ message: "Morning arrived." })
      .mockReturnValueOnce(pending.promise)
    renderTimeControl()
    const button = screen.getByRole("button", { name: "Advance" })
    fireEvent.click(button)
    expect(await screen.findByText("Morning arrived.")).toBeInTheDocument()
    await waitFor(() => expect(button).toBeEnabled())

    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "12" } })
    fireEvent.click(button)

    expect(screen.queryByText("Morning arrived.")).not.toBeInTheDocument()
    expect(button).toBeDisabled()
    expect(mockApi.advanceTime).toHaveBeenNthCalledWith(2, "session-1", { hours: 12 })

    await act(async () => pending.resolve({ message: "Night arrived." }))

    expect(screen.getByText("Night arrived.")).toBeInTheDocument()
    expect(screen.queryByText("Morning arrived.")).not.toBeInTheDocument()
    expect(onAdvanced).toHaveBeenCalledTimes(2)
  })

  it("shows an error without notifying the parent and allows a successful retry", async () => {
    mockApi.advanceTime.mockRejectedValueOnce(new Error("Request failed"))
    renderTimeControl()
    const button = screen.getByRole("button", { name: "Advance" })
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "6" } })
    fireEvent.click(button)

    expect(await screen.findByText("Error")).toBeInTheDocument()
    expect(screen.queryByText("Time advanced.")).not.toBeInTheDocument()
    expect(screen.queryByText("The world clock moved forward.")).not.toBeInTheDocument()
    expect(onAdvanced).not.toHaveBeenCalled()
    await waitFor(() => expect(button).toBeEnabled())
    expect(screen.getByRole("spinbutton")).toHaveValue(6)

    fireEvent.click(button)

    expect(await screen.findByText("The world clock moved forward.")).toBeInTheDocument()
    expect(await screen.findByText("Time advanced.")).toBeInTheDocument()
    expect(mockApi.advanceTime).toHaveBeenCalledTimes(2)
    expect(mockApi.advanceTime).toHaveBeenNthCalledWith(1, "session-1", { hours: 6 })
    expect(mockApi.advanceTime).toHaveBeenNthCalledWith(2, "session-1", { hours: 6 })
    expect(onAdvanced).toHaveBeenCalledTimes(1)
  })

  it.each(["", "0", "-2"])("disables advance for invalid hours %j and recovers when corrected", async (value) => {
    renderTimeControl()
    const input = screen.getByRole("spinbutton")
    const button = screen.getByRole("button", { name: "Advance" })

    fireEvent.change(input, { target: { value } })

    expect(button).toBeDisabled()
    fireEvent.click(button)
    expect(mockApi.advanceTime).not.toHaveBeenCalled()
    expect(onAdvanced).not.toHaveBeenCalled()

    fireEvent.change(input, { target: { value: "2" } })
    expect(button).toBeEnabled()
    fireEvent.click(button)

    expect(mockApi.advanceTime).toHaveBeenCalledExactlyOnceWith("session-1", { hours: 2 })
    expect(await screen.findByText("The world clock moved forward.")).toBeInTheDocument()
  })

  it("handles a successful empty message without leaving the controls disabled", async () => {
    mockApi.advanceTime.mockResolvedValueOnce({ message: "" })
    renderTimeControl()
    const button = screen.getByRole("button", { name: "Advance" })
    fireEvent.click(button)

    expect(await screen.findByText("Time advanced.")).toBeInTheDocument()
    expect(onAdvanced).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(button).toBeEnabled())
    expect(screen.getByRole("spinbutton")).toHaveValue(1)
    expect(screen.queryByText("The world clock moved forward.")).not.toBeInTheDocument()
  })

  // BUG: The 8760-hour input maximum is not enforced by the Advance button.
  it.fails("prevents advancing beyond the supported 8760-hour maximum", () => {
    renderTimeControl()
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "8761" } })

    expect(screen.getByRole("button", { name: "Advance" })).toBeDisabled()
  })
})
