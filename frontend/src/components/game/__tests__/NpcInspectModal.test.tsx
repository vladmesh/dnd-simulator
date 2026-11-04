import { act, fireEvent, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import "@/i18n"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import type { CombatAwareness, CombatEntity, MerchantInfo, NearbyEntity, PeacefulAwareness, PlayerStatus } from "@/types/game"
import { NpcInspectModal } from "../NpcInspectModal"

// This modal sends WS actions, not HTTP requests. Keep both transports isolated.
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

const npc: NearbyEntity = {
  id: "merchant_1",
  name: "Mira",
  description: "A human trader",
  npc_description: "A trader with a bright blue cloak.",
  race: "human",
  role: "merchant",
  is_merchant: true,
}
const enemy: CombatEntity = { id: "goblin_1", description: "Goblin" }
const merchant: MerchantInfo = {
  id: npc.id,
  name: "Mira's wares",
  gold: 50,
  items: [{ id: "potion", name: "Healing potion", description: "Restores health", price: 10 }],
}
const peaceful: PeacefulAwareness = {
  hour: 12, day: 1, month: 1, year: 1, weather: {},
  location_name: "Market", region_name: "Town", nearby: [npc], merchants: [merchant],
}
const combat: CombatAwareness = {
  self_hp: 20, self_max_hp: 20, self_ac: 15, self_speed: 30,
  self_weapon: "Sword", self_weapon_damage: "1d8", nearby: [enemy], round_number: 1,
}
const slots: CombatAwareness = {
  ...combat,
  self_resource_pools: [
    { id: "spell_slot_1", current_uses: 0, max_uses: 2 },
    { id: "spell_slot_2", current_uses: 1, max_uses: 1 },
  ],
}
const player: PlayerStatus = {
  player_id: "p1", name: "Hero", race: "human", char_class: "fighter", level: 1,
  experience: 0, level_up_available: false, xp_to_next_level: 300, alignment: "neutral",
  hp: 20, max_hp: 20, ac: 15, gold: 20, location_id: "market",
  ability_scores: { str: 16, dex: 14, con: 14, int: 10, wis: 10, cha: 8 },
  inventory: [{ id: "dagger", name: "Old dagger", description: "A worn blade", price: 5 }],
}

// Scope the unnamed icon-only Send button to the dialog, excluding focus guards.
const sendButton = () => within(screen.getByRole("dialog")).getByRole("button", { name: "" })

beforeEach(() => {
  vi.clearAllMocks()
  useGameStore.setState({
    awareness: peaceful, mode: "peaceful", player, isMyTurn: true, waitingForAction: false,
  })
})

// Faction display and speech-length errors/boundaries already have dedicated tests
// in BattleMapInspect.test.tsx and speechLimit.test.tsx respectively.
describe("NpcInspectModal — remaining branches", () => {
  it("renders nothing without an entity or while closed, then shows the supplied NPC", () => {
    const onClose = vi.fn()
    const { rerender } = render(
      <NpcInspectModal entity={null} open onClose={onClose} isCombat={false} />,
    )
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    rerender(<NpcInspectModal entity={npc} open={false} onClose={onClose} isCombat={false} />)
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    rerender(<NpcInspectModal entity={npc} open onClose={onClose} isCombat={false} />)
    expect(screen.getByRole("dialog", { name: "Mira" })).toBeInTheDocument()
    expect(screen.getByText("Human · Merchant")).toBeInTheDocument()
    expect(screen.getByText(npc.npc_description!)).toBeInTheDocument()
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
    expect(screen.queryByText(merchant.name)).not.toBeInTheDocument()
    expect(wsClient.send).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
  })

  it("uses perceived descriptions and untranslated race/role fallbacks for strangers", () => {
    const stranger: NearbyEntity = {
      id: "stranger", name: "", description: "A tall stranger", npc_description: "",
      race: "Aasimar", role: "Cartographer",
    }
    const { rerender } = render(
      <NpcInspectModal entity={stranger} open onClose={vi.fn()} isCombat={false} />,
    )
    expect(screen.getByRole("heading", { name: "A tall stranger" })).toBeInTheDocument()
    expect(screen.getByText("Aasimar · Cartographer")).toBeInTheDocument()
    rerender(
      <NpcInspectModal entity={{ ...stranger, description: "", race: "", role: "" }} open onClose={vi.fn()} isCombat={false} />,
    )
    expect(screen.getByRole("heading", { name: "someone" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Attack someone" })).toBeInTheDocument()
  })

  it("renders combat conditions, distance and wounds but omits absent combat details", () => {
    useGameStore.setState({ awareness: combat, mode: "combat" })
    const { rerender } = render(
      <NpcInspectModal entity={{ ...enemy, conditions: ["Prone", "Poisoned"], distance_ft: 15, direction: "NE", is_wounded: true }} open onClose={vi.fn()} isCombat />,
    )
    expect(screen.getByText("Prone")).toBeInTheDocument()
    expect(screen.getByText("Poisoned")).toBeInTheDocument()
    expect(screen.getByText("15ft NE")).toBeInTheDocument()
    expect(screen.getByText("(wounded)")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Talk" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Trade" })).not.toBeInTheDocument()
    rerender(<NpcInspectModal entity={{ ...enemy, conditions: [], distance_ft: 0 }} open onClose={vi.fn()} isCombat />)
    expect(screen.getByText("0ft")).toBeInTheDocument()
    expect(screen.queryByText("Prone")).not.toBeInTheDocument()
    expect(screen.queryByText("(wounded)")).not.toBeInTheDocument()
    rerender(<NpcInspectModal entity={enemy} open onClose={vi.fn()} isCombat />)
    expect(screen.queryByText(/ft/)).not.toBeInTheDocument()
  })

  it("withholds actions for dead NPCs and outside the player's turn", () => {
    const { rerender } = render(
      <NpcInspectModal entity={{ ...npc, is_dead: true, is_wounded: true }} open onClose={vi.fn()} isCombat={false} />,
    )
    expect(screen.getByText("(dead)")).toBeInTheDocument()
    expect(screen.queryByText("(wounded)")).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Attack|Talk|Trade/ })).not.toBeInTheDocument()
    act(() => useGameStore.setState({ isMyTurn: false }))
    rerender(<NpcInspectModal entity={npc} open onClose={vi.fn()} isCombat={false} />)
    expect(screen.queryByRole("button", { name: /Attack|Talk|Trade/ })).not.toBeInTheDocument()
    expect(screen.queryByText("(dead)")).not.toBeInTheDocument()
    expect(wsClient.send).not.toHaveBeenCalled()
  })

  it("attacks immediately without spell slots, using the label for display and id for targeting", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    useGameStore.setState({ awareness: combat, mode: "combat" })
    render(<NpcInspectModal entity={enemy} targetLabel="Goblin #2" open onClose={onClose} isCombat />)
    await user.click(screen.getByRole("button", { name: "Attack Goblin #2" }))
    expect(wsClient.send).toHaveBeenCalledExactlyOnceWith({
      type: "action", name: "attack", params: { target_id: enemy.id },
    })
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    expect(useGameStore.getState().waitingForAction).toBe(true)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("allows cancelling smite, disables depleted slots and sends the chosen slot", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    useGameStore.setState({ awareness: slots, mode: "combat" })
    render(<NpcInspectModal entity={enemy} targetLabel="Goblin #2" open onClose={onClose} isCombat />)
    const attack = screen.getByRole("button", { name: "Attack Goblin #2" })
    await user.click(attack)
    expect(screen.getByRole("menu", { name: "Attack Goblin #2" })).toBeInTheDocument()
    await user.click(screen.getByRole("menuitem", { name: /Smite \(slot 1\)/ }))
    expect(screen.getByRole("menuitem", { name: /Smite \(slot 1\)/ })).toBeDisabled()
    expect(wsClient.send).not.toHaveBeenCalled()
    await user.click(screen.getByRole("menuitem", { name: "Cancel" }))
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
    await user.click(attack)
    await user.click(screen.getByRole("menuitem", { name: /Attack Goblin #2 \+ Smite \(slot 2\)/ }))
    expect(wsClient.send).toHaveBeenCalledExactlyOnceWith({
      type: "action", name: "attack", params: { target_id: enemy.id, smite_slot_level: 2 },
    })
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(useGameStore.getState().waitingForAction).toBe(true)
  })

  it("clears the smite chooser on dismissal and offers a normal attack without a slot", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    useGameStore.setState({ awareness: slots, mode: "combat" })
    const { rerender } = render(<NpcInspectModal entity={enemy} open onClose={onClose} isCombat />)
    await user.click(screen.getByRole("button", { name: "Attack Goblin" }))
    await user.click(screen.getByRole("button", { name: "Close" }))
    expect(onClose).toHaveBeenCalledTimes(1)
    rerender(<NpcInspectModal entity={enemy} open={false} onClose={onClose} isCombat />)
    rerender(<NpcInspectModal entity={enemy} open onClose={onClose} isCombat />)
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Attack Goblin" }))
    await user.click(screen.getByRole("menuitem", { name: "Attack Goblin" }))
    expect(wsClient.send).toHaveBeenCalledExactlyOnceWith({
      type: "action", name: "attack", params: { target_id: enemy.id },
    })
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it("rejects blank speech and lets Talk and Escape dismiss the draft", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<NpcInspectModal entity={npc} open onClose={onClose} isCombat={false} />)
    const talk = screen.getByRole("button", { name: "Talk" })
    await user.click(talk)
    const input = screen.getByRole("textbox")
    expect(input).toHaveValue("")
    expect(sendButton()).toBeDisabled()
    fireEvent.change(input, { target: { value: "   " } })
    fireEvent.keyDown(input, { key: "Enter" })
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    expect(wsClient.send).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
    await user.click(talk)
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
    await user.click(talk)
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Never mind" } })
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Escape" })
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
    expect(wsClient.send).not.toHaveBeenCalled()
  })

  it("sends trimmed speech via the send button and clears the draft", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<NpcInspectModal entity={npc} open onClose={onClose} isCombat={false} />)
    await user.click(screen.getByRole("button", { name: "Talk" }))
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "  Hello, Mira!  " } })
    await user.click(sendButton())
    expect(wsClient.send).toHaveBeenCalledExactlyOnceWith({
      type: "action", name: "say", params: { target_id: npc.id, text: "Hello, Mira!" },
    })
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
    expect(useGameStore.getState().waitingForAction).toBe(true)
  })

  it("toggles the matching merchant's inventory and sends buy/sell actions", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<NpcInspectModal entity={npc} open onClose={onClose} isCombat={false} />)
    const trade = screen.getByRole("button", { name: "Trade" })
    await user.click(trade)
    expect(screen.getByText(merchant.name)).toBeInTheDocument()
    expect(screen.getByText("Healing potion")).toBeInTheDocument()
    expect(screen.getByText("Old dagger")).toBeInTheDocument()
    await user.click(trade)
    expect(screen.queryByText(merchant.name)).not.toBeInTheDocument()
    await user.click(trade)
    await user.click(screen.getByRole("button", { name: "Buy" }))
    expect(wsClient.send).toHaveBeenNthCalledWith(1, {
      type: "action", name: "buy", params: { merchant_id: npc.id, item_id: "potion" },
    })
    expect(screen.getByRole("button", { name: "Buy" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Sell" })).toBeDisabled()
    act(() => useGameStore.setState({ waitingForAction: false }))
    await user.click(screen.getByRole("button", { name: "Sell" }))
    expect(wsClient.send).toHaveBeenNthCalledWith(2, {
      type: "action", name: "sell", params: { merchant_id: npc.id, item_id: "dagger" },
    })
    expect(wsClient.send).toHaveBeenCalledTimes(2)
    expect(onClose).not.toHaveBeenCalled()
  })

  it("omits Trade when merchant awareness is missing or does not match the NPC", () => {
    useGameStore.setState({ awareness: null })
    render(<NpcInspectModal entity={npc} open onClose={vi.fn()} isCombat={false} />)
    expect(screen.queryByRole("button", { name: "Trade" })).not.toBeInTheDocument()
    act(() => useGameStore.setState({ awareness: { ...peaceful, merchants: undefined } }))
    expect(screen.queryByRole("button", { name: "Trade" })).not.toBeInTheDocument()
    act(() => useGameStore.setState({ awareness: { ...peaceful, merchants: [{ ...merchant, id: "other" }] } }))
    expect(screen.queryByRole("button", { name: "Trade" })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Talk" })).toBeInTheDocument()
  })

  it("clears trade and speech on dialog close before reopening", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    const { rerender } = render(<NpcInspectModal entity={npc} open onClose={onClose} isCombat={false} />)
    await user.click(screen.getByRole("button", { name: "Trade" }))
    await user.click(screen.getByRole("button", { name: "Talk" }))
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Unsent draft" } })
    await user.click(screen.getByRole("button", { name: "Close" }))
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(wsClient.send).not.toHaveBeenCalled()
    rerender(<NpcInspectModal entity={npc} open={false} onClose={onClose} isCombat={false} />)
    rerender(<NpcInspectModal entity={npc} open onClose={onClose} isCombat={false} />)
    const dialog = within(screen.getByRole("dialog", { name: "Mira" }))
    expect(dialog.queryByText(merchant.name)).not.toBeInTheDocument()
    expect(dialog.queryByRole("textbox")).not.toBeInTheDocument()
    await user.click(dialog.getByRole("button", { name: "Talk" }))
    expect(dialog.getByRole("textbox")).toHaveValue("")
  })
})
