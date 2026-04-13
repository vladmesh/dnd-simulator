import { render, screen, act } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import "@/i18n"
import { PlayerStats } from "../PlayerStats"
import { useGameStore } from "@/store/gameStore"
import { api, ApiError } from "@/transport/apiClient"
import type { PlayerStatus } from "@/types/game"

vi.mock("@/transport/apiClient", async () => {
  const actual = await vi.importActual<typeof import("@/transport/apiClient")>(
    "@/transport/apiClient",
  )
  return {
    ...actual,
    api: {
      ...actual.api,
      player: { ...actual.api.player, levelUp: vi.fn() },
    },
  }
})

const levelUpMock = api.player.levelUp as unknown as ReturnType<typeof vi.fn>

function makePlayer(overrides?: Partial<PlayerStatus>): PlayerStatus {
  return {
    player_id: "p1",
    name: "Hero",
    race: "human",
    char_class: "fighter",
    level: 1,
    experience: 0,
    level_up_available: false,
    xp_to_next_level: 300,
    alignment: "neutral",
    hp: 12,
    max_hp: 12,
    ac: 15,
    gold: 0,
    location_id: "town",
    ability_scores: { str: 16, dex: 14, con: 14, int: 10, wis: 10, cha: 8 },
    ...overrides,
  }
}

beforeEach(() => {
  levelUpMock.mockReset()
  useGameStore.setState({ player: null, sessionId: "s1" })
})

describe("PlayerStats — level-up integration", () => {
  it("hides level-up button when level_up_available is false", () => {
    useGameStore.setState({ player: makePlayer({ level_up_available: false }) })
    render(<PlayerStats />)
    expect(
      screen.queryByRole("button", { name: /level up/i }),
    ).not.toBeInTheDocument()
    expect(screen.queryByTestId("level-up-modal")).not.toBeInTheDocument()
  })

  it("auto-opens modal once when flag transitions false → true; does not reopen on close", async () => {
    useGameStore.setState({ player: makePlayer({ level_up_available: false }) })
    render(<PlayerStats />)
    expect(screen.queryByTestId("level-up-modal")).not.toBeInTheDocument()

    act(() => {
      useGameStore.setState({
        player: makePlayer({ level_up_available: true }),
      })
    })

    expect(screen.getByTestId("level-up-modal")).toBeInTheDocument()

    const user = userEvent.setup()
    await user.click(screen.getByRole("button", { name: /cancel/i }))
    expect(screen.queryByTestId("level-up-modal")).not.toBeInTheDocument()
    // After modal closes, the level-up button stays available for manual reopen.
    expect(
      screen.getByRole("button", { name: /level up/i }),
    ).toBeInTheDocument()

    // Force a store update with the same flag — must not auto-reopen.
    act(() => {
      useGameStore.setState({
        player: makePlayer({ level_up_available: true, hp: 11 }),
      })
    })
    expect(screen.queryByTestId("level-up-modal")).not.toBeInTheDocument()
  })

  it("clicking level-up button after manual close reopens the modal", async () => {
    useGameStore.setState({ player: makePlayer({ level_up_available: false }) })
    render(<PlayerStats />)
    act(() => {
      useGameStore.setState({
        player: makePlayer({ level_up_available: true }),
      })
    })

    const user = userEvent.setup()
    await user.click(screen.getByRole("button", { name: /cancel/i }))
    expect(screen.queryByTestId("level-up-modal")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /level up/i }))
    expect(screen.getByTestId("level-up-modal")).toBeInTheDocument()
  })

  it("on successful level-up: store reflects new player, modal closes, button hidden", async () => {
    useGameStore.setState({ player: makePlayer({ level_up_available: true }) })
    const updated = makePlayer({
      level: 2,
      level_up_available: false,
      hp: 18,
      max_hp: 18,
      resource_pools: [{ id: "action_surge", max_uses: 1, current_uses: 1 }],
    })
    levelUpMock.mockResolvedValueOnce(updated)

    const user = userEvent.setup()
    render(<PlayerStats />)
    await user.click(screen.getByRole("button", { name: /confirm/i }))

    await vi.waitFor(() => {
      expect(useGameStore.getState().player?.level).toBe(2)
    })
    expect(useGameStore.getState().player?.level_up_available).toBe(false)
    expect(useGameStore.getState().player?.max_hp).toBe(18)
    expect(useGameStore.getState().player?.resource_pools).toEqual([
      { id: "action_surge", max_uses: 1, current_uses: 1 },
    ])
    expect(screen.queryByTestId("level-up-modal")).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: /level up/i }),
    ).not.toBeInTheDocument()
  })

  it("on API failure: store is not mutated and modal stays open with error", async () => {
    const initial = makePlayer({ level_up_available: true })
    useGameStore.setState({ player: initial })
    levelUpMock.mockRejectedValueOnce(new ApiError(400, { detail: "boom" }))

    const user = userEvent.setup()
    render(<PlayerStats />)
    await user.click(screen.getByRole("button", { name: /confirm/i }))

    expect(await screen.findByTestId("level-up-error")).toBeInTheDocument()
    expect(screen.getByTestId("level-up-modal")).toBeInTheDocument()
    expect(useGameStore.getState().player).toEqual(initial)
  })
})
