import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import i18n from "@/i18n"

// Perception's actions use WebSocket, not REST; isolate both transports.
vi.mock("@/transport/apiClient", () => ({ api: { player: {}, master: {} } }))
vi.mock("@/transport/wsClient", () => ({
  wsClient: {
    send: vi.fn(),
    onStatus: vi.fn(() => vi.fn()),
    onMessage: vi.fn(() => vi.fn()),
    getStatus: vi.fn(() => "disconnected"),
    connect: vi.fn(),
    disconnect: vi.fn(),
  },
}))

import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import type { CombatAwareness, NearbyEntity, PeacefulAwareness } from "@/types/game"
import { Perception } from "../Perception"

const sendMock = vi.mocked(wsClient.send)
const goblin: NearbyEntity = { id: "goblin-1", description: "Goblin" }

function peaceful(nearby: NearbyEntity[] = [goblin]): PeacefulAwareness {
  return {
    hour: 12,
    day: 1,
    month: 1,
    year: 1,
    weather: {},
    location_name: "Town",
    region_name: "Region",
    nearby,
  }
}

function combat(): CombatAwareness {
  return {
    self_hp: 20,
    self_max_hp: 20,
    self_ac: 15,
    self_speed: 30,
    self_weapon: "Longsword",
    self_weapon_damage: "1d8",
    nearby: [goblin],
    round_number: 1,
  }
}

function withSpellSlots() {
  useGameStore.setState({
    mode: "combat",
    awareness: {
      ...combat(),
      self_resource_pools: [
        { id: "spell_slot_1", max_uses: 2, current_uses: 0 },
        { id: "spell_slot_2", max_uses: 1, current_uses: 1 },
      ],
    },
  })
}

function renderTalk() {
  useGameStore.setState({ awareness: peaceful() })
  render(<Perception />)
}

// The inline send button is icon-only; the other buttons have target-aware names.
function sendButton() {
  return screen.getByRole("button", { name: "" })
}

beforeEach(async () => {
  sendMock.mockReset()
  await i18n.changeLanguage("en")
  useGameStore.setState({ ...useGameStore.getInitialState(), isMyTurn: true })
})

afterEach(() => {
  cleanup()
  useGameStore.setState(useGameStore.getInitialState(), true)
})

describe("Perception — remaining state and interaction branches", () => {
  it("renders nothing while awareness is pending, then shows an empty nearby list", () => {
    render(<Perception />)

    expect(screen.queryByRole("heading")).not.toBeInTheDocument()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(screen.queryByText("Nobody around.")).not.toBeInTheDocument()

    act(() => useGameStore.setState({ awareness: peaceful([]) }))

    expect(screen.getByRole("heading", { name: "Nearby" })).toBeInTheDocument()
    expect(screen.getByText("Nobody around.")).toBeInTheDocument()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(sendMock).not.toHaveBeenCalled()
  })

  it("keeps wounded entities visible without any controls outside the player's turn", () => {
    useGameStore.setState({
      awareness: peaceful([{ ...goblin, is_wounded: true }]),
      isMyTurn: false,
    })
    render(<Perception />)

    expect(screen.getByText("Goblin")).toBeInTheDocument()
    expect(screen.getByText("(wounded)")).toBeInTheDocument()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
    expect(sendMock).not.toHaveBeenCalled()
  })

  it("attacks directly in combat when resource pools are omitted or undefined", async () => {
    const user = userEvent.setup()
    useGameStore.setState({ mode: "combat", awareness: combat() })
    render(<Perception />)

    expect(screen.getByRole("heading", { name: "Enemies" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Talk to Goblin" })).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Attack Goblin" }))
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    expect(sendMock).toHaveBeenNthCalledWith(1, {
      type: "action", name: "attack", params: { target_id: "goblin-1" },
    })

    act(() => useGameStore.setState({
      awareness: { ...combat(), self_resource_pools: undefined },
      waitingForAction: false,
    }))
    await user.click(screen.getByRole("button", { name: "Attack Goblin" }))
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    expect(sendMock).toHaveBeenNthCalledWith(2, {
      type: "action", name: "attack", params: { target_id: "goblin-1" },
    })
    expect(sendMock).toHaveBeenCalledTimes(2)
  })

  it("blocks depleted smite slots and sends the selected available slot, closing the menu", async () => {
    const user = userEvent.setup()
    withSpellSlots()
    render(<Perception />)

    await user.click(screen.getByRole("button", { name: "Attack Goblin" }))
    const depleted = screen.getByRole("menuitem", { name: /Attack Goblin \+ Smite \(slot 1\)/ })
    expect(depleted).toBeDisabled()
    await user.click(depleted)
    expect(sendMock).not.toHaveBeenCalled()

    await user.click(screen.getByRole("menuitem", { name: /Attack Goblin \+ Smite \(slot 2\)/ }))
    expect(sendMock).toHaveBeenCalledExactlyOnceWith({
      type: "action",
      name: "attack",
      params: { target_id: "goblin-1", smite_slot_level: 2 },
    })
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
  })

  it("dismisses the smite menu by toggling Attack or choosing Cancel without sending", async () => {
    const user = userEvent.setup()
    withSpellSlots()
    render(<Perception />)

    const attack = screen.getByRole("button", { name: "Attack Goblin" })
    await user.click(attack)
    expect(screen.getByRole("menu", { name: "Attack Goblin" })).toBeInTheDocument()
    await user.click(attack)
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()

    await user.click(attack)
    await user.click(screen.getByRole("menuitem", { name: "Cancel" }))
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    expect(sendMock).not.toHaveBeenCalled()
  })

  it("toggles the talk input without discarding its unsent draft", async () => {
    const user = userEvent.setup()
    renderTalk()

    const talk = screen.getByRole("button", { name: "Talk to Goblin" })
    await user.click(talk)
    await user.type(screen.getByRole("textbox"), "Hello")
    await user.click(talk)
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()

    await user.click(talk)
    expect(screen.getByRole("textbox")).toHaveValue("Hello")
    expect(sendMock).not.toHaveBeenCalled()
  })

  it("sends trimmed speech on Enter and clears the draft after submission", async () => {
    const user = userEvent.setup()
    renderTalk()

    await user.click(screen.getByRole("button", { name: "Talk to Goblin" }))
    await user.type(screen.getByRole("textbox"), "  Hello there  {Enter}")

    expect(sendMock).toHaveBeenCalledExactlyOnceWith({
      type: "action", name: "say", params: { target_id: "goblin-1", text: "Hello there" },
    })
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Talk to Goblin" }))
    expect(screen.getByRole("textbox")).toHaveValue("")
    expect(sendButton()).toBeDisabled()
  })

  it("sends speech to the chosen target when the send button is clicked", async () => {
    const user = userEvent.setup()
    useGameStore.setState({
      awareness: peaceful([goblin, { id: "guard-2", description: "Guard" }]),
    })
    render(<Perception />)

    await user.click(screen.getByRole("button", { name: "Talk to Guard" }))
    await user.type(screen.getByRole("textbox"), "  Good day  ")
    expect(sendButton()).toBeEnabled()
    await user.click(sendButton())

    expect(sendMock).toHaveBeenCalledExactlyOnceWith({
      type: "action", name: "say", params: { target_id: "guard-2", text: "Good day" },
    })
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
  })

  it("disables sending empty or whitespace-only speech and ignores Enter", async () => {
    const user = userEvent.setup()
    renderTalk()

    await user.click(screen.getByRole("button", { name: "Talk to Goblin" }))
    expect(sendButton()).toBeDisabled()
    await user.type(screen.getByRole("textbox"), "   {Enter}")

    expect(sendButton()).toBeDisabled()
    expect(screen.getByRole("textbox")).toHaveValue("   ")
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    expect(sendMock).not.toHaveBeenCalled()
  })

  it("shows accessible length feedback, blocks overlong speech, and accepts a corrected boundary draft", async () => {
    const user = userEvent.setup()
    renderTalk()
    await user.click(screen.getByRole("button", { name: "Talk to Goblin" }))
    const input = screen.getByRole("textbox")

    fireEvent.change(input, { target: { value: "x".repeat(2001) } })
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Too long: 2001 of 2000 characters. Shorten it to send.",
    )
    expect(input).toHaveAttribute("aria-invalid", "true")
    expect(input).toHaveAccessibleDescription("Too long: 2001 of 2000 characters. Shorten it to send.")
    expect(sendButton()).toBeDisabled()
    await user.keyboard("{Enter}")
    expect(sendMock).not.toHaveBeenCalled()
    expect(input).toHaveValue("x".repeat(2001))

    // Astral characters count as one code point, not two UTF-16 code units.
    const boundary = "😀".repeat(2000)
    fireEvent.change(input, { target: { value: `  ${boundary}  ` } })
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    expect(input).not.toHaveAttribute("aria-invalid")
    expect(input).not.toHaveAttribute("aria-describedby")
    expect(sendButton()).toBeEnabled()
    await user.click(sendButton())
    expect(sendMock).toHaveBeenCalledExactlyOnceWith({
      type: "action", name: "say", params: { target_id: "goblin-1", text: boundary },
    })
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
  })

  it("discards the talk draft on Escape without submitting it", async () => {
    const user = userEvent.setup()
    renderTalk()

    await user.click(screen.getByRole("button", { name: "Talk to Goblin" }))
    await user.type(screen.getByRole("textbox"), "Never mind{Escape}")
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
    expect(sendMock).not.toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: "Talk to Goblin" }))
    expect(screen.getByRole("textbox")).toHaveValue("")
    expect(sendButton()).toBeDisabled()
  })

  it("closes inspection and returns to the nearby list without sending an action", async () => {
    const user = userEvent.setup()
    useGameStore.setState({ awareness: peaceful() })
    render(<Perception />)

    await user.click(screen.getByRole("button", { name: "Inspect Goblin" }))
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Close" }))

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    expect(screen.getByRole("heading", { name: "Nearby" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Inspect Goblin" })).toBeInTheDocument()
    expect(sendMock).not.toHaveBeenCalled()
  })
})
