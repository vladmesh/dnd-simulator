import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { ErrorBoundary } from "../ErrorBoundary"

vi.mock("@/transport/apiClient", () => ({ api: {} }))

// ErrorBoundary reports directly with fetch rather than through the API client.
const fetchMock = vi.fn<typeof fetch>()

function BrokenChild({ error }: { error: Error }): never {
  throw error
}

function renderError(error: Error) {
  return render(
    <ErrorBoundary>
      <BrokenChild error={error} />
    </ErrorBoundary>,
  )
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal("fetch", fetchMock)
    // React also logs caught render errors; keep expected failures out of test output.
    vi.spyOn(console, "error").mockImplementation(() => {})
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("renders healthy children immediately and leaves their controls usable", async () => {
    const user = userEvent.setup()
    const onContinue = vi.fn()
    render(
      <ErrorBoundary>
        <h1>Adventure ready</h1>
        <p>Your party is waiting.</p>
        <button onClick={onContinue}>Continue adventure</button>
      </ErrorBoundary>,
    )

    expect(screen.getByRole("heading", { name: "Adventure ready" })).toBeInTheDocument()
    expect(screen.getByText("Your party is waiting.")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Back to start" })).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Continue adventure" }))
    expect(onContinue).toHaveBeenCalledOnce()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("renders nothing when children are empty without showing an error", () => {
    const { container } = render(<ErrorBoundary>{null}</ErrorBoundary>)

    expect(container).toBeEmptyDOMElement()
    expect(screen.queryByRole("button", { name: "Back to start" })).not.toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("replaces failed children with an error message, stack and recovery button", () => {
    const error = new Error("The encounter could not render")
    error.stack = "Error: The encounter could not render\n    at BrokenChild (fixture.tsx:1:1)"
    render(
      <ErrorBoundary>
        <h2>Encounter details</h2>
        <BrokenChild error={error} />
      </ErrorBoundary>,
    )

    expect(screen.getByRole("heading", { name: "Something went wrong" })).toBeInTheDocument()
    expect(screen.getByText(/at BrokenChild \(fixture.tsx:1:1\)/)).toHaveTextContent(
      "The encounter could not render",
    )
    expect(screen.queryByRole("heading", { name: "Encounter details" })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Back to start" })).toBeEnabled()
  })

  it("posts the caught error and component stack to the frontend-error endpoint", async () => {
    const error = new Error("Unable to display the party")
    renderError(error)

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock).toHaveBeenCalledWith("/api/frontend-error", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: expect.any(String),
    })
    const options = fetchMock.mock.calls[0][1]
    expect(JSON.parse(options?.body as string)).toEqual({
      message: error.message,
      stack: error.stack,
      component: expect.stringContaining("BrokenChild"),
    })
    expect(await screen.findByRole("heading", { name: "Something went wrong" })).toBeInTheDocument()
  })

  it("keeps the fallback usable when error reporting rejects", async () => {
    fetchMock.mockRejectedValue(new Error("Reporting service unavailable"))
    renderError(new Error("The map could not render"))

    expect(await screen.findByText(/The map could not render/)).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Something went wrong" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Back to start" })).toBeEnabled()
    expect(screen.queryByText(/Reporting service unavailable/)).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it("still displays the error message when no stack is available", () => {
    const error = new Error("Missing character data")
    error.stack = undefined
    renderError(error)

    expect(screen.getByText("Missing character data")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Back to start" })).toBeEnabled()
  })

  it("clears the error and navigates home when Back to start is clicked", async () => {
    const user = userEvent.setup()
    const error = new Error("Temporary render failure")
    let shouldThrow = true
    function RecoverableChild() {
      if (shouldThrow) throw error
      return <h2>Adventure recovered</h2>
    }
    render(
      <ErrorBoundary>
        <RecoverableChild />
      </ErrorBoundary>,
    )

    // jsdom cannot navigate; replace only location while preserving the rest of window.
    const location = { href: "/encounter" }
    vi.stubGlobal("window", new Proxy(window, {
      get(target, property) {
        return property === "location" ? location : Reflect.get(target, property, target)
      },
    }))
    shouldThrow = false
    await user.click(screen.getByRole("button", { name: "Back to start" }))

    expect(location.href).toBe("/")
    expect(screen.getByRole("heading", { name: "Adventure recovered" })).toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "Something went wrong" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Back to start" })).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledOnce()
  })
})
