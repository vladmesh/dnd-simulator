import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import "@/i18n"
import { LevelUpModal } from "../LevelUpModal"
import type { PlayerStatus } from "@/types/game"
import { api, ApiError } from "@/transport/apiClient"

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

vi.mock("@/transport/apiClient", async () => {
  const actual = await vi.importActual<typeof import("@/transport/apiClient")>(
    "@/transport/apiClient",
  )
  return {
    ...actual,
    api: {
      ...actual.api,
      player: {
        ...actual.api.player,
        levelUp: vi.fn(),
      },
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
    experience: 300,
    level_up_available: true,
    xp_to_next_level: 0,
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

function makeUpdatedStatus(overrides?: Partial<PlayerStatus>): PlayerStatus {
  return makePlayer({ level: 2, experience: 300, level_up_available: false, ...overrides })
}

beforeEach(() => {
  levelUpMock.mockReset()
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("LevelUpModal", () => {
  it("Paladin L1 shows three fighting-style options and confirm is disabled until one is picked", async () => {
    const user = userEvent.setup()
    render(
      <LevelUpModal
        open
        player={makePlayer({ char_class: "paladin" })}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />,
    )

    const select = screen.getByLabelText(/fighting style/i) as HTMLSelectElement
    const options = Array.from(select.querySelectorAll("option")).map((o) => o.value)
    expect(options).toContain("defense")
    expect(options).toContain("dueling")
    expect(options).toContain("great_weapon_fighting")

    const confirm = screen.getByRole("button", { name: /confirm/i })
    expect(confirm).toBeDisabled()

    await user.selectOptions(select, "dueling")
    expect(confirm).toBeEnabled()
  })

  it("Fighter L1 shows no dropdown, confirm enabled immediately, Action Surge mentioned", () => {
    render(
      <LevelUpModal
        open
        player={makePlayer({ char_class: "fighter" })}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />,
    )
    expect(screen.queryByLabelText(/fighting style/i)).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: /confirm/i })).toBeEnabled()
    expect(screen.getByText(/action surge/i)).toBeInTheDocument()
  })

  it("Rogue L1 shows no dropdown, confirm enabled, HP gain displayed", () => {
    render(
      <LevelUpModal
        open
        player={makePlayer({ char_class: "rogue" })}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />,
    )
    expect(screen.queryByLabelText(/fighting style/i)).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: /confirm/i })).toBeEnabled()
    expect(screen.getByTestId("hp-gain")).toBeInTheDocument()
  })

  it("Paladin submit calls api with { fighting_style: 'dueling' } and invokes onSuccess", async () => {
    const user = userEvent.setup()
    const onSuccess = vi.fn()
    const updated = makeUpdatedStatus({ char_class: "paladin" })
    levelUpMock.mockResolvedValueOnce(updated)

    render(
      <LevelUpModal
        open
        sessionId="s1"
        player={makePlayer({ char_class: "paladin" })}
        onClose={vi.fn()}
        onSuccess={onSuccess}
      />,
    )

    await user.selectOptions(screen.getByLabelText(/fighting style/i), "dueling")
    await user.click(screen.getByRole("button", { name: /confirm/i }))

    expect(levelUpMock).toHaveBeenCalledTimes(1)
    expect(levelUpMock).toHaveBeenCalledWith("s1", { fighting_style: "dueling" })
    expect(onSuccess).toHaveBeenCalledWith(updated)
  })

  it("Fighter submit calls api with empty body (no fighting_style)", async () => {
    const user = userEvent.setup()
    const onSuccess = vi.fn()
    const updated = makeUpdatedStatus({ char_class: "fighter" })
    levelUpMock.mockResolvedValueOnce(updated)

    render(
      <LevelUpModal
        open
        sessionId="s1"
        player={makePlayer({ char_class: "fighter" })}
        onClose={vi.fn()}
        onSuccess={onSuccess}
      />,
    )

    await user.click(screen.getByRole("button", { name: /confirm/i }))

    expect(levelUpMock).toHaveBeenCalledTimes(1)
    const body = levelUpMock.mock.calls[0][1]
    expect(body).toEqual({})
    expect(onSuccess).toHaveBeenCalledWith(updated)
  })

  it("surfaces API error inline and re-enables confirm for retry", async () => {
    const user = userEvent.setup()
    levelUpMock.mockRejectedValueOnce(new ApiError(400, { detail: "boom" }))

    render(
      <LevelUpModal
        open
        sessionId="s1"
        player={makePlayer({ char_class: "fighter" })}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />,
    )

    const confirm = screen.getByRole("button", { name: /confirm/i })
    await user.click(confirm)

    expect(await screen.findByTestId("level-up-error")).toBeInTheDocument()
    expect(confirm).toBeEnabled()
  })

  it("Cancel fires onClose and does not call the API", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()

    render(
      <LevelUpModal
        open
        sessionId="s1"
        player={makePlayer({ char_class: "fighter" })}
        onClose={onClose}
        onSuccess={vi.fn()}
      />,
    )

    await user.click(screen.getByRole("button", { name: /cancel/i }))
    expect(onClose).toHaveBeenCalled()
    expect(levelUpMock).not.toHaveBeenCalled()
  })
})
