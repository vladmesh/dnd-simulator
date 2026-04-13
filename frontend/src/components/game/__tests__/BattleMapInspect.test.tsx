import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import "@/i18n"
import { useGameStore } from "@/store/gameStore"
import { BattleMap } from "../BattleMap"
import { CombatPanel } from "../CombatPanel"
import { NpcInspectModal } from "../NpcInspectModal"
import type { CombatAwareness, CombatEntity, NearbyEntity } from "@/types/game"

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const enemy: CombatEntity = {
  id: "goblin_1",
  description: "Goblin",
  is_wounded: false,
  is_hostile: true,
  distance_ft: 5,
  direction: "N",
  x: 5,
  y: 0,
}

const combatAwareness: CombatAwareness = {
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
  battle_map_walls: [],
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  useGameStore.setState({
    mode: "combat",
    awareness: combatAwareness,
    isMyTurn: true,
    waitingForAction: false,
    budget: { actions: 1, bonus_actions: 1, movement_remaining: 30, reaction: 1 },
  })
})

// ---------------------------------------------------------------------------
// BattleMap — click occupied cell
// ---------------------------------------------------------------------------

describe("BattleMap — click-to-inspect", () => {
  it("calls onEntityClick when clicking an occupied enemy cell", async () => {
    const user = userEvent.setup()
    const onEntityClick = vi.fn()

    render(<BattleMap onEntityClick={onEntityClick} />)

    // Enemy is at (5, 0) → grid col=1, row=0 → cell-1-0
    const enemyCell = screen.getByTestId("cell-1-0")
    await user.click(enemyCell)

    expect(onEntityClick).toHaveBeenCalledTimes(1)
    expect(onEntityClick).toHaveBeenCalledWith(enemy)
  })

  it("does NOT call onEntityClick when clicking the player's own cell", async () => {
    const user = userEvent.setup()
    const onEntityClick = vi.fn()

    render(<BattleMap onEntityClick={onEntityClick} />)

    // Player is at (0, 0) → grid col=0, row=0 → cell-0-0
    const playerCell = screen.getByTestId("cell-0-0")
    await user.click(playerCell)

    expect(onEntityClick).not.toHaveBeenCalled()
  })

  it("occupied enemy cell has cursor-pointer class", () => {
    render(<BattleMap onEntityClick={vi.fn()} />)
    const enemyCell = screen.getByTestId("cell-1-0")
    expect(enemyCell.className).toContain("cursor-pointer")
  })

  it("pins coord convention: feet → cell via x/5, y/5 (no flip, no offset)", () => {
    // Pin the canonical invariant: backend sends positions in feet; frontend
    // renders `cell-{col}-{row}` with col=x/5 and row=y/5. No axis flip.
    useGameStore.setState({
      mode: "combat",
      awareness: {
        ...combatAwareness,
        self_x: 25,
        self_y: 30,
        battle_map_width: 60,
        battle_map_height: 60,
        nearby: [{ ...enemy, x: 15, y: 20 }],
      },
      isMyTurn: false,
      waitingForAction: false,
    })
    render(<BattleMap />)
    // Player at feet (25, 30) → cell-5-6
    expect(screen.getByTestId("cell-5-6")).toBeInTheDocument()
    // Enemy at feet (15, 20) → cell-3-4
    expect(screen.getByTestId("cell-3-4")).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// CombatPanel — no enemies list
// ---------------------------------------------------------------------------

describe("CombatPanel — no enemies list", () => {
  it("does not render the enemies section", () => {
    render(<CombatPanel />)

    // The enemies heading should be gone
    expect(screen.queryByText(/enemies/i)).not.toBeInTheDocument()
    // Individual enemy entries should not exist
    expect(screen.queryByText("Goblin")).not.toBeInTheDocument()
  })

  it("still shows self stats and round counter", () => {
    render(<CombatPanel />)

    // Round counter and HP bar should still be present
    expect(screen.getByText(/20.*20/)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// NpcInspectModal — faction display name
// ---------------------------------------------------------------------------

describe("NpcInspectModal — faction name", () => {
  it("shows faction_name instead of faction_id when available", () => {
    const entity: NearbyEntity = {
      id: "npc_1",
      description: "Guard",
      name: "Captain Aldric",
      race: "human",
      role: "guard",
      faction_id: "kingdom",
      faction_name: "Kingdom Forces",
      npc_description: "A royal guard",
    }

    render(
      <NpcInspectModal entity={entity} open={true} onClose={vi.fn()} isCombat={false} />,
    )

    expect(screen.getByText(/Kingdom Forces/)).toBeInTheDocument()
    // Should NOT show the raw faction_id
    expect(screen.queryByText(/: kingdom$/)).not.toBeInTheDocument()
  })

  it("falls back to faction_id when faction_name is not set", () => {
    const entity: NearbyEntity = {
      id: "npc_1",
      description: "Guard",
      name: "Captain Aldric",
      faction_id: "kingdom",
      npc_description: "A royal guard",
    }

    render(
      <NpcInspectModal entity={entity} open={true} onClose={vi.fn()} isCombat={false} />,
    )

    expect(screen.getByText(/kingdom/)).toBeInTheDocument()
  })
})
