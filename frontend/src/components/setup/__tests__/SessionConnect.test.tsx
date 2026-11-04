import { fireEvent, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import "@/i18n"
import { SessionConnect } from "../SessionConnect"

// Joining delegates to onConnect; this component does not call the API itself.
vi.mock("@/transport/apiClient", () => ({ api: {} }))

function setup() {
  const onConnect = vi.fn()
  render(<SessionConnect onConnect={onConnect} />)
  return {
    onConnect,
    input: screen.getByRole("textbox"),
    join: screen.getByRole("button", { name: "Join" }),
  }
}

describe("SessionConnect", () => {
  it("initially shows an empty session field and a disabled Join button", () => {
    const { input, join, onConnect } = setup()

    expect(screen.getByText("Session ID")).toBeInTheDocument()
    expect(screen.getByPlaceholderText("paste session id...")).toBeVisible()
    expect(input).toHaveValue("")
    expect(join).toBeDisabled()
    expect(onConnect).not.toHaveBeenCalled()
  })

  it("displays typed text and disables Join again when the field is cleared", async () => {
    const user = userEvent.setup()
    const { input, join, onConnect } = setup()

    await user.type(input, "abc-123")
    expect(input).toHaveValue("abc-123")
    expect(join).toBeEnabled()
    expect(onConnect).not.toHaveBeenCalled()

    await user.clear(input)
    expect(input).toHaveValue("")
    expect(join).toBeDisabled()
  })

  it("joins with a trimmed session ID when Join is clicked", async () => {
    const user = userEvent.setup()
    const { input, join, onConnect } = setup()

    await user.type(input, "  abc-123  ")
    await user.click(join)

    expect(onConnect).toHaveBeenCalledExactlyOnceWith("abc-123")
    expect(input).toHaveValue("  abc-123  ")
  })

  it("joins with a trimmed session ID when Enter is pressed", async () => {
    const user = userEvent.setup()
    const { input, onConnect } = setup()

    await user.type(input, "  keyboard-session  {Enter}")

    expect(onConnect).toHaveBeenCalledExactlyOnceWith("keyboard-session")
  })

  it("does not join on other keys even with a valid session ID", async () => {
    const user = userEvent.setup()
    const { input, join, onConnect } = setup()

    await user.type(input, "abc-123{Escape}{ArrowLeft}")

    expect(join).toBeEnabled()
    expect(onConnect).not.toHaveBeenCalled()
  })

  it.each(["", "   \t  "])("does not join with a blank session ID (%j)", async (value) => {
    const user = userEvent.setup()
    const { input, join, onConnect } = setup()

    fireEvent.change(input, { target: { value } })
    expect(input).toHaveValue(value)
    expect(join).toBeDisabled()

    await user.click(join)
    await user.click(input)
    await user.keyboard("{Enter}")

    expect(onConnect).not.toHaveBeenCalled()
  })

  it("submits the current session ID after editing a previous submission", async () => {
    const user = userEvent.setup()
    const { input, join, onConnect } = setup()

    await user.type(input, "first-session")
    await user.click(join)
    await user.clear(input)
    await user.type(input, "  second-session  ")
    await user.click(join)

    expect(onConnect).toHaveBeenCalledTimes(2)
    expect(onConnect).toHaveBeenNthCalledWith(1, "first-session")
    expect(onConnect).toHaveBeenNthCalledWith(2, "second-session")
  })
})
