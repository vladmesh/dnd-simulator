import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { toast } from "sonner"
import i18n from "@/i18n"
import { ApiError } from "@/transport/apiClient"
import type { GiveItemRequest } from "@/types/api"
import { GiveItemDialog } from "../GiveItemDialog"

const mockGiveItem = vi.fn<
  (sessionId: string, entityId: string, data: GiveItemRequest) => Promise<{ item_id: string; name: string }>
>()

vi.mock("@/transport/apiClient", async () => {
  const { ApiError } = await vi.importActual<typeof import("@/transport/requestCore")>("@/transport/requestCore")
  return {
    ApiError,
    api: { master: { giveItem: (...args: Parameters<typeof mockGiveItem>) => mockGiveItem(...args) } },
  }
})

vi.mock("sonner", () => ({ toast: { success: vi.fn() } }))

function renderDialog() {
  const onClose = vi.fn()
  const onGiven = vi.fn()
  render(<GiveItemDialog sessionId="session-1" entityId="hero-2" onClose={onClose} onGiven={onGiven} />)
  return { onClose, onGiven }
}

function pendingItem() {
  let resolve!: (value: { item_id: string; name: string }) => void
  const promise = new Promise<{ item_id: string; name: string }>((done) => { resolve = done })
  return { promise, resolve }
}

// The text fields currently lack accessible names; use their visible form order
// until the label-association regression below is fixed.
const nameInput = () => screen.getAllByRole("textbox")[0]
const giveButton = () => screen.getByRole("button", { name: "Give Item" })

describe("GiveItemDialog", () => {
  beforeEach(async () => {
    vi.resetAllMocks()
    await i18n.changeLanguage("en")
    mockGiveItem.mockResolvedValue({ item_id: "new-item", name: "Long Sword" })
  })

  afterEach(cleanup)

  it("renders the default weapon form without fetching and disables submission for an empty name", async () => {
    const user = userEvent.setup()
    renderDialog()

    expect(screen.getByRole("dialog", { name: "Give Item" })).toBeVisible()
    expect(screen.getByRole("button", { name: "Weapon" })).toBeVisible()
    expect(screen.getByRole("button", { name: "Potion" })).toBeVisible()
    expect(screen.getByText("Weapon ID")).toBeVisible()
    expect(screen.queryByText("Heal Dice")).not.toBeInTheDocument()
    expect(nameInput()).toHaveValue("")
    expect(screen.getAllByRole("textbox")[3]).toHaveValue("1d8")
    expect(screen.getAllByRole("combobox")[0]).toHaveValue("simple")
    expect(screen.getAllByRole("combobox")[1]).toHaveValue("slashing")
    expect(screen.getByRole("spinbutton")).toHaveValue(5)
    expect(screen.getByRole("checkbox", { name: "Magic" })).not.toBeChecked()
    expect(screen.getByRole("checkbox", { name: "Finesse" })).not.toBeChecked()
    expect(giveButton()).toBeDisabled()
    await user.click(giveButton())
    expect(mockGiveItem).not.toHaveBeenCalled()

    await user.type(nameInput(), "Sword")
    expect(giveButton()).toBeEnabled()
    await user.clear(nameInput())
    expect(giveButton()).toBeDisabled()
    expect(mockGiveItem).not.toHaveBeenCalled()
  })

  it("submits weapon defaults, blocks duplicate saves while pending, and reports success", async () => {
    const user = userEvent.setup()
    const pending = pendingItem()
    mockGiveItem.mockReturnValueOnce(pending.promise)
    const { onGiven, onClose } = renderDialog()

    await user.type(nameInput(), "Long  Sword")
    expect(screen.getByPlaceholderText("long_sword")).toBeVisible()
    expect(screen.getByPlaceholderText(/Long\s+Sword/)).toBeVisible()
    await user.click(giveButton())

    expect(mockGiveItem).toHaveBeenCalledExactlyOnceWith("session-1", "hero-2", {
      name: "Long  Sword", type: "weapon", weapon_id: "long_sword", attack_name: "Long  Sword",
      category: "simple", damage: [{ dice: "1d8", type: "slashing" }], reach: 5,
      is_magic: false, is_finesse: false,
    })
    expect(giveButton()).toBeDisabled()
    await user.click(giveButton())
    expect(mockGiveItem).toHaveBeenCalledTimes(1)
    expect(onGiven).not.toHaveBeenCalled()
    expect(toast.success).not.toHaveBeenCalled()

    await act(async () => { pending.resolve({ item_id: "sword", name: "Long  Sword" }) })
    await waitFor(() => expect(giveButton()).toBeEnabled())
    expect(onGiven).toHaveBeenCalledExactlyOnceWith()
    expect(toast.success).toHaveBeenCalledExactlyOnceWith("Item given.")
    expect(onClose).not.toHaveBeenCalled()
  })

  it("submits all customized weapon fields and restores the minimum reach when cleared", async () => {
    const user = userEvent.setup()
    renderDialog()
    await user.type(nameInput(), "Flame Rapier")
    await user.type(screen.getByPlaceholderText("flame_rapier"), "rapier-rare")
    await user.type(screen.getByPlaceholderText("Flame Rapier"), "Flaming thrust")
    await user.selectOptions(screen.getAllByRole("combobox")[0], "martial")
    const damageInput = screen.getByDisplayValue("1d8")
    await user.clear(damageInput)
    await user.type(damageInput, "2d6")
    await user.selectOptions(screen.getAllByRole("combobox")[1], "fire")
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "" } })
    expect(screen.getByRole("spinbutton")).toHaveValue(5)
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "10" } })
    await user.click(screen.getByRole("checkbox", { name: "Magic" }))
    await user.click(screen.getByRole("checkbox", { name: "Finesse" }))
    expect(screen.getByRole("checkbox", { name: "Magic" })).toBeChecked()
    expect(screen.getByRole("checkbox", { name: "Finesse" })).toBeChecked()
    await user.click(giveButton())

    expect(mockGiveItem).toHaveBeenCalledExactlyOnceWith("session-1", "hero-2", {
      name: "Flame Rapier", type: "weapon", weapon_id: "rapier-rare", attack_name: "Flaming thrust",
      category: "martial", damage: [{ dice: "2d6", type: "fire" }], reach: 10,
      is_magic: true, is_finesse: true,
    })
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Item given."))
  })

  it("switches to a potion and submits the default healing dice without weapon fields", async () => {
    const user = userEvent.setup()
    const { onGiven } = renderDialog()
    await user.click(screen.getByRole("button", { name: "Potion" }))

    expect(screen.getByText("Heal Dice")).toBeVisible()
    expect(screen.getByDisplayValue("2d4+2")).toBeVisible()
    expect(screen.queryByText("Weapon ID")).not.toBeInTheDocument()
    expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument()
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument()
    expect(giveButton()).toBeDisabled()
    await user.type(nameInput(), "Healing Potion")
    await user.click(giveButton())

    expect(mockGiveItem).toHaveBeenCalledExactlyOnceWith("session-1", "hero-2", {
      name: "Healing Potion", type: "potion", heal_dice: "2d4+2",
    })
    await waitFor(() => expect(onGiven).toHaveBeenCalledOnce())
  })

  it("preserves edited values when switching item types and submits customized healing dice", async () => {
    const user = userEvent.setup()
    renderDialog()
    await user.type(nameInput(), "Restorative")
    await user.type(screen.getByPlaceholderText("restorative"), "custom-weapon")
    await user.click(screen.getByRole("button", { name: "Potion" }))
    await user.clear(screen.getByDisplayValue("2d4+2"))
    await user.type(screen.getAllByRole("textbox")[1], "4d4+4")
    await user.click(screen.getByRole("button", { name: "Weapon" }))
    expect(screen.getByDisplayValue("custom-weapon")).toBeVisible()
    expect(screen.queryByText("Heal Dice")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Potion" }))
    expect(nameInput()).toHaveValue("Restorative")
    expect(screen.getByDisplayValue("4d4+4")).toBeVisible()
    await user.click(giveButton())

    expect(mockGiveItem).toHaveBeenCalledExactlyOnceWith("session-1", "hero-2", {
      name: "Restorative", type: "potion", heal_dice: "4d4+4",
    })
    await waitFor(() => expect(toast.success).toHaveBeenCalledOnce())
  })

  it.each(["Cancel", "Close"])("calls onClose without saving when %s is clicked", async (button) => {
    const user = userEvent.setup()
    const { onClose, onGiven } = renderDialog()
    await user.click(screen.getByRole("button", { name: button }))

    expect(onClose).toHaveBeenCalledOnce()
    expect(onGiven).not.toHaveBeenCalled()
    expect(mockGiveItem).not.toHaveBeenCalled()
    expect(toast.success).not.toHaveBeenCalled()
  })

  it("shows API error details, clears them on retry, and succeeds without losing the form", async () => {
    const user = userEvent.setup()
    const pending = pendingItem()
    mockGiveItem.mockRejectedValueOnce(new ApiError(400, { detail: "Inventory is full" }))
    const { onGiven, onClose } = renderDialog()
    await user.type(nameInput(), "Sword")
    await user.click(giveButton())

    expect(await screen.findByText("Inventory is full")).toBeVisible()
    await waitFor(() => expect(giveButton()).toBeEnabled())
    expect(nameInput()).toHaveValue("Sword")
    expect(onGiven).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
    expect(toast.success).not.toHaveBeenCalled()

    mockGiveItem.mockReturnValueOnce(pending.promise)
    await user.click(giveButton())
    expect(screen.queryByText("Inventory is full")).not.toBeInTheDocument()
    expect(giveButton()).toBeDisabled()
    expect(mockGiveItem).toHaveBeenCalledTimes(2)
    expect(mockGiveItem).toHaveBeenNthCalledWith(2, "session-1", "hero-2", {
      name: "Sword", type: "weapon", weapon_id: "sword", attack_name: "Sword",
      category: "simple", damage: [{ dice: "1d8", type: "slashing" }], reach: 5,
      is_magic: false, is_finesse: false,
    })
    await act(async () => { pending.resolve({ item_id: "sword", name: "Sword" }) })
    await waitFor(() => expect(giveButton()).toBeEnabled())
    expect(onGiven).toHaveBeenCalledOnce()
    expect(toast.success).toHaveBeenCalledExactlyOnceWith("Item given.")
  })

  it.each([
    { reason: new Error("Connection lost"), message: "Connection lost", kind: "Error" },
    { reason: "Unexpected response", message: "Unexpected response", kind: "string" },
    { reason: null, message: "null", kind: "null" },
  ])("renders a non-API $kind rejection and re-enables saving", async ({ reason, message }) => {
    const user = userEvent.setup()
    mockGiveItem.mockRejectedValueOnce(reason)
    const { onGiven, onClose } = renderDialog()
    await user.type(nameInput(), "Sword")
    await user.click(giveButton())

    expect(await screen.findByText(message)).toBeVisible()
    await waitFor(() => expect(giveButton()).toBeEnabled())
    expect(onGiven).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
    expect(toast.success).not.toHaveBeenCalled()
  })

  // BUG: The visible Name label is not associated with its input, leaving it without an accessible name.
  it.fails("exposes the item name field through its visible label", () => {
    renderDialog()
    expect(screen.getByRole("textbox", { name: "Name" })).toBeVisible()
  })
})
