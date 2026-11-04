import { act, cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import "@/i18n"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import type { CombatAwareness, CombatEntity, PeacefulAwareness } from "@/types/game"
import { BattleMap } from "../BattleMap"

// Movement uses WebSocket messages, not REST. Keep both transports isolated.
vi.mock("@/transport/apiClient", () => ({ api: {} }))
vi.mock("@/transport/wsClient", () => ({
  wsClient: { send: vi.fn(), onStatus: vi.fn(), onMessage: vi.fn() },
}))

const initialState = useGameStore.getInitialState()
const enemy: CombatEntity = {
  id: "goblin_1",
  description: "Goblin",
  is_hostile: true,
  x: 5,
  y: 0,
}

function combat(overrides: Partial<CombatAwareness> = {}): CombatAwareness {
  return {
    self_hp: 20,
    self_max_hp: 20,
    self_ac: 15,
    self_speed: 30,
    self_weapon: "Sword",
    self_weapon_damage: "1d8",
    self_x: 0,
    self_y: 0,
    nearby: [enemy],
    round_number: 1,
    battle_map_width: 10,
    battle_map_height: 10,
    reachable: [[5, 10], [10, 10]],
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  useGameStore.setState({
    ...initialState,
    mode: "combat",
    awareness: combat(),
    isMyTurn: true,
    waitingForAction: false,
  }, true)
})

afterEach(() => {
  cleanup()
  useGameStore.setState(initialState, true)
})

describe("BattleMap — rendering and movement", () => {
  it("renders nothing before awareness arrives or with peaceful awareness", () => {
    useGameStore.setState({ awareness: null })
    render(<BattleMap />)
    expect(screen.queryByRole("heading", { name: "Battle Map" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()

    const peaceful: PeacefulAwareness = {
      hour: 12,
      day: 1,
      month: 1,
      year: 1,
      weather: {},
      location_name: "Town",
      region_name: "Valley",
      nearby: [],
    }
    act(() => useGameStore.setState({ awareness: peaceful }))
    expect(screen.queryByRole("heading", { name: "Battle Map" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(wsClient.send).not.toHaveBeenCalled()
  })

  it("hides the map when either dimension is missing or zero", () => {
    const dimensions: Partial<CombatAwareness>[] = [
      { battle_map_width: undefined },
      { battle_map_height: undefined },
      { battle_map_width: 0 },
      { battle_map_height: 0 },
    ]
    for (const dimensionsOverride of dimensions) {
      useGameStore.setState({ awareness: combat(dimensionsOverride) })
      const { unmount } = render(<BattleMap />)
      expect(screen.queryByRole("heading", { name: "Battle Map" })).not.toBeInTheDocument()
      expect(screen.queryByRole("button")).not.toBeInTheDocument()
      unmount()
    }
  })

  it("numbers positioned creatures through nine, then uses +, skipping missing positions", () => {
    const creatures: CombatEntity[] = Array.from({ length: 10 }, (_, i) => ({
      id: `creature_${i}`,
      description: `Creature ${i + 1}`,
      is_hostile: i % 2 === 0,
      x: (i % 4) * 5,
      y: Math.floor(i / 4) * 5,
    }))
    useGameStore.setState({
      awareness: combat({
        self_x: undefined,
        self_y: undefined,
        battle_map_width: 15,
        battle_map_height: 15,
        nearby: [
          ...creatures,
          { id: "unknown_x", description: "Missing X", y: 15 },
          { id: "unknown_y", description: "Missing Y", x: 15 },
        ],
      }),
    })
    render(<BattleMap />)

    expect(screen.getByRole("heading", { name: "Battle Map" })).toBeInTheDocument()
    expect(screen.getByText("Highlighted tile: move. Miniature: inspect. @ is your character.")).toBeInTheDocument()
    expect(screen.getAllByRole("button")).toHaveLength(17)
    creatures.forEach((creature, i) => {
      expect(screen.getByRole("button", { name: creature.description }))
        .toHaveTextContent(i < 9 ? String(i + 1) : "+")
    })
    expect(screen.queryByRole("button", { name: "Your character" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Missing X" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Missing Y" })).not.toBeInTheDocument()
  })

  it("sends a move in feet and prevents duplicate moves while awaiting a response", async () => {
    const user = userEvent.setup()
    render(<BattleMap />)
    const destination = screen.getByRole("button", { name: "Move to 5, 10" })
    expect(destination).toBeEnabled()

    await user.click(destination)
    expect(wsClient.send).toHaveBeenCalledExactlyOnceWith({
      type: "action", name: "move_to", params: { x: 5, y: 10 },
    })
    expect(destination).toBeDisabled()
    const otherDestination = screen.getByRole("button", { name: "Move to 10, 10" })
    expect(otherDestination).toBeDisabled()
    await user.click(destination)
    await user.click(otherDestination)
    expect(wsClient.send).toHaveBeenCalledTimes(1)
  })

  it("does not move to unreachable or occupied tiles, even if occupied tiles are reachable", async () => {
    const user = userEvent.setup()
    useGameStore.setState({ awareness: combat({ reachable: [[5, 0]] }) })
    render(<BattleMap />)
    const unreachable = screen.getByRole("button", { name: "Move to 10, 0" })
    const occupied = screen.getByRole("button", { name: "Goblin" })
    expect(unreachable).toBeDisabled()
    expect(occupied).toBeDisabled()
    await user.click(unreachable)
    await user.click(occupied)
    expect(wsClient.send).not.toHaveBeenCalled()
  })

  it("disables movement outside the player's turn and enables it when the turn arrives", async () => {
    const user = userEvent.setup()
    useGameStore.setState({ isMyTurn: false })
    render(<BattleMap />)
    const destination = screen.getByRole("button", { name: "Move to 5, 10" })
    expect(destination).toBeDisabled()
    await user.click(destination)
    expect(wsClient.send).not.toHaveBeenCalled()

    act(() => useGameStore.setState({ isMyTurn: true }))
    expect(destination).toBeEnabled()
    await user.click(destination)
    expect(wsClient.send).toHaveBeenCalledExactlyOnceWith({
      type: "action", name: "move_to", params: { x: 5, y: 10 },
    })
  })

  it("allows retrying a move when a server error clears the pending action", async () => {
    const user = userEvent.setup()
    render(<BattleMap />)
    const destination = screen.getByRole("button", { name: "Move to 5, 10" })
    await user.click(destination)
    expect(destination).toBeDisabled()

    // BattleMap has no error UI; the store handles server errors and releases movement.
    act(() => useGameStore.getState().onError({ type: "error", message: "Move rejected" }))
    expect(destination).toBeEnabled()
    await user.click(destination)
    expect(wsClient.send).toHaveBeenCalledTimes(2)
    expect(wsClient.send).toHaveBeenNthCalledWith(2, {
      type: "action", name: "move_to", params: { x: 5, y: 10 },
    })
    expect(destination).toBeDisabled()
  })

  it("disables all empty cells when reachable data is missing or empty", () => {
    for (const reachable of [undefined, []]) {
      useGameStore.setState({ awareness: combat({ nearby: [], reachable }) })
      const { unmount } = render(<BattleMap />)
      const emptyCells = screen.getAllByRole("button", { name: /^Move to / })
      expect(emptyCells).toHaveLength(8)
      emptyCells.forEach((cell) => expect(cell).toBeDisabled())
      unmount()
    }
    expect(wsClient.send).not.toHaveBeenCalled()
  })

  it("toggles tabletop view off and back on without sending an action", async () => {
    const user = userEvent.setup()
    render(<BattleMap />)
    const toggle = screen.getByRole("button", { name: "Tabletop view", pressed: true })
    await user.click(toggle)
    expect(screen.getByRole("button", { name: "Tabletop view", pressed: false })).toBe(toggle)
    await user.click(toggle)
    expect(screen.getByRole("button", { name: "Tabletop view", pressed: true })).toBe(toggle)
    expect(wsClient.send).not.toHaveBeenCalled()
  })

  it("updates the player tile and reachable destinations after a successful move", async () => {
    const user = userEvent.setup()
    render(<BattleMap />)
    await user.click(screen.getByRole("button", { name: "Move to 5, 10" }))

    act(() => useGameStore.setState({
      awareness: combat({ self_x: 5, self_y: 10, reachable: [[0, 0]] }),
      waitingForAction: false,
    }))
    expect(screen.queryByRole("button", { name: "Move to 5, 10" })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Your character" })).toHaveTextContent("@")
    const nextDestination = screen.getByRole("button", { name: "Move to 0, 0" })
    expect(nextDestination).toBeEnabled()
    expect(screen.getByRole("button", { name: "Move to 10, 10" })).toBeDisabled()
    await user.click(nextDestination)
    expect(wsClient.send).toHaveBeenCalledTimes(2)
    expect(wsClient.send).toHaveBeenNthCalledWith(2, {
      type: "action", name: "move_to", params: { x: 0, y: 0 },
    })
  })

  it("uses backend reachability on maps with horizontal and vertical wall segments", async () => {
    const user = userEvent.setup()
    useGameStore.setState({
      awareness: combat({
        reachable: [[0, 5]],
        battle_map_walls: [
          { x1: 5, y1: 10, x2: 5, y2: 0 },
          { x1: 10, y1: 5, x2: 5, y2: 5 },
          { x1: 10, y1: 0, x2: 10, y2: 5 },
          { x1: 0, y1: 10, x2: 5, y2: 10 },
        ],
      }),
    })
    render(<BattleMap />)
    const destination = screen.getByRole("button", { name: "Move to 0, 5" })
    expect(destination).toBeEnabled()
    expect(screen.getByRole("button", { name: "Move to 10, 5" })).toBeDisabled()
    await user.click(destination)
    expect(wsClient.send).toHaveBeenCalledExactlyOnceWith({
      type: "action", name: "move_to", params: { x: 0, y: 5 },
    })
  })
})
