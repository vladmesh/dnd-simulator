import { useMemo, useCallback } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import type { CombatAwareness, CombatEntity } from "@/types/game"

/** Which borders of a cell have walls. */
interface CellWalls {
  top: boolean
  right: boolean
  bottom: boolean
  left: boolean
}

/**
 * Build a set of blocked edges from raw wall segments.
 * Each wall is an axis-aligned segment in feet coordinates.
 * Returns a Set of "x1,y1|x2,y2" edge keys (sorted so order doesn't matter).
 */
function buildBlockedEdges(
  walls: Array<{ x1: number; y1: number; x2: number; y2: number }>,
): Set<string> {
  const edges = new Set<string>()
  for (const w of walls) {
    if (w.x1 === w.x2) {
      // Vertical wall at x=W — blocks east/west crossing
      const wx = w.x1
      const yMin = Math.min(w.y1, w.y2)
      const yMax = Math.max(w.y1, w.y2)
      for (let y = yMin; y < yMax; y += 5) {
        edges.add(edgeKey(wx - 5, y, wx, y))
      }
    } else if (w.y1 === w.y2) {
      // Horizontal wall at y=W — blocks north/south crossing
      const wy = w.y1
      const xMin = Math.min(w.x1, w.x2)
      const xMax = Math.max(w.x1, w.x2)
      for (let x = xMin; x < xMax; x += 5) {
        edges.add(edgeKey(x, wy - 5, x, wy))
      }
    }
  }
  return edges
}

function edgeKey(x1: number, y1: number, x2: number, y2: number): string {
  // Canonical order: smaller coordinate first
  if (x1 < x2 || (x1 === x2 && y1 < y2)) return `${x1},${y1}|${x2},${y2}`
  return `${x2},${y2}|${x1},${y1}`
}

/** Check if a single step between adjacent cells is blocked by a wall edge. */
function isEdgeBlocked(
  fromX: number, fromY: number,
  toX: number, toY: number,
  edges: Set<string>,
): boolean {
  const dx = toX - fromX
  const dy = toY - fromY
  const isDiag = dx !== 0 && dy !== 0
  if (!isDiag) {
    return edges.has(edgeKey(fromX, fromY, toX, toY))
  }
  // Diagonal: blocked only if BOTH L-shaped paths are blocked
  const mid1Blocked = edges.has(edgeKey(fromX, fromY, fromX + dx, fromY)) &&
    edges.has(edgeKey(fromX + dx, fromY, toX, toY))
  const mid2Blocked = edges.has(edgeKey(fromX, fromY, fromX, fromY + dy)) &&
    edges.has(edgeKey(fromX, fromY + dy, toX, toY))
  return mid1Blocked && mid2Blocked
}

/** Determine which borders of a cell have inner walls. */
function getCellWalls(
  col: number,
  row: number,
  edges: Set<string>,
): CellWalls {
  const x = col * 5
  const y = row * 5
  return {
    // Wall between this cell and cell above (y+5)
    top: edges.has(edgeKey(x, y, x, y + 5)),
    // Wall between this cell and cell to the right (x+5)
    right: edges.has(edgeKey(x, y, x + 5, y)),
    // Wall between this cell and cell below (y-5)
    bottom: edges.has(edgeKey(x, y - 5, x, y)),
    // Wall between this cell and cell to the left (x-5)
    left: edges.has(edgeKey(x - 5, y, x, y)),
  }
}

/**
 * BFS to compute reachable cells from player position within movement budget.
 * Uses D&D 5e diagonal cost: first diagonal = 5ft, second = 10ft, alternating.
 */
function computeReachable(
  startCol: number,
  startRow: number,
  budget: number,
  maxCol: number,
  maxRow: number,
  occupied: Set<string>,
  edges: Set<string>,
): Set<string> {
  const reachable = new Set<string>()
  if (budget <= 0) return reachable

  // BFS with cost tracking — state is (col, row, costSoFar, diagCount)
  // We track best cost to each cell to prune
  const bestCost = new Map<string, number>()
  const queue: Array<[number, number, number, number]> = [[startCol, startRow, 0, 0]]
  bestCost.set(`${startCol},${startRow}`, 0)

  const dirs = [
    [-1, 0], [1, 0], [0, -1], [0, 1],
    [-1, -1], [-1, 1], [1, -1], [1, 1],
  ]

  while (queue.length > 0) {
    const [col, row, cost, diagCount] = queue.shift()!
    if (cost > budget) continue

    for (const [dc, dr] of dirs) {
      const nc = col + dc
      const nr = row + dr
      if (nc < 0 || nc > maxCol || nr < 0 || nr > maxRow) continue

      const nKey = `${nc},${nr}`
      if (occupied.has(nKey)) continue

      const fromX = col * 5
      const fromY = row * 5
      const toX = nc * 5
      const toY = nr * 5
      if (isEdgeBlocked(fromX, fromY, toX, toY, edges)) continue

      const isDiag = dc !== 0 && dr !== 0
      let stepCost: number
      let newDiag: number
      if (isDiag) {
        stepCost = diagCount % 2 === 1 ? 10 : 5
        newDiag = diagCount + 1
      } else {
        stepCost = 5
        newDiag = diagCount
      }

      const newCost = cost + stepCost
      if (newCost > budget) continue

      const prevBest = bestCost.get(nKey)
      if (prevBest !== undefined && prevBest <= newCost) continue

      bestCost.set(nKey, newCost)
      reachable.add(nKey)
      queue.push([nc, nr, newCost, newDiag])
    }
  }

  return reachable
}

export function BattleMap() {
  const { t } = useTranslation(["game"])
  const awareness = useGameStore((s) => s.awareness)
  const isMyTurn = useGameStore((s) => s.isMyTurn)
  const budget = useGameStore((s) => s.budget)
  const waitingForAction = useGameStore((s) => s.waitingForAction)

  const handleCellClick = useCallback((x: number, y: number) => {
    wsClient.send({ type: "action", name: "move_to", params: { x, y } })
    useGameStore.getState().setWaitingForAction(true)
  }, [])

  if (!awareness || !("self_hp" in awareness)) return null
  const combat = awareness as CombatAwareness

  const width = combat.battle_map_width ?? 0
  const height = combat.battle_map_height ?? 0
  if (width === 0 || height === 0) return null

  const cols = width / 5 + 1
  const rows = height / 5 + 1

  // Build position lookup and blocked edges
  const { posLookup, blockedEdges, occupiedSet } = useMemo(() => {
    const lookup = new Map<string, { glyph: string; isPlayer: boolean }>()
    const occ = new Set<string>()

    // Player position
    if (combat.self_x != null && combat.self_y != null) {
      const pCol = combat.self_x / 5
      const pRow = combat.self_y / 5
      lookup.set(`${pCol},${pRow}`, { glyph: "@", isPlayer: true })
    }

    // Enemy positions — numbered to match CombatPanel order
    combat.nearby.forEach((entity: CombatEntity, i: number) => {
      if (entity.x != null && entity.y != null) {
        const eCol = entity.x / 5
        const eRow = entity.y / 5
        const glyph = i < 9 ? String(i + 1) : "+"
        lookup.set(`${eCol},${eRow}`, { glyph, isPlayer: false })
        occ.add(`${eCol},${eRow}`)
      }
    })

    const edges = buildBlockedEdges(combat.battle_map_walls ?? [])

    return { posLookup: lookup, blockedEdges: edges, occupiedSet: occ }
  }, [combat.self_x, combat.self_y, combat.nearby, combat.battle_map_walls])

  // Compute reachable cells when it's player's turn
  const reachableCells = useMemo(() => {
    if (!isMyTurn || waitingForAction) return new Set<string>()
    const moveBudget = budget?.movement_remaining ?? 0
    if (moveBudget <= 0 || combat.self_x == null || combat.self_y == null) return new Set<string>()
    const startCol = combat.self_x / 5
    const startRow = combat.self_y / 5
    return computeReachable(startCol, startRow, moveBudget, cols - 1, rows - 1, occupiedSet, blockedEdges)
  }, [isMyTurn, waitingForAction, budget?.movement_remaining, combat.self_x, combat.self_y, cols, rows, occupiedSet, blockedEdges])

  const canClick = isMyTurn && !waitingForAction

  // Render grid top-down: row 0 in render = max y (north at top)
  const cells: React.ReactNode[] = []
  for (let renderRow = 0; renderRow < rows; renderRow++) {
    const gridRow = rows - 1 - renderRow // map row (y increases north)
    for (let col = 0; col < cols; col++) {
      const key = `${col},${gridRow}`
      const entity = posLookup.get(key)
      const walls = getCellWalls(col, gridRow, blockedEdges)
      const isReachable = reachableCells.has(key)
      const isClickable = canClick && isReachable && !entity

      const wallClasses = [
        walls.top ? "border-t-yellow-600 border-t-2" : "border-t-transparent border-t",
        walls.right ? "border-r-yellow-600 border-r-2" : "border-r-transparent border-r",
        walls.bottom ? "border-b-yellow-600 border-b-2" : "border-b-transparent border-b",
        walls.left ? "border-l-yellow-600 border-l-2" : "border-l-transparent border-l",
      ].join(" ")

      const bgClass = entity?.isPlayer
        ? "bg-green-900/50 text-green-300 font-bold"
        : entity
          ? "bg-red-900/50 text-red-300 font-bold"
          : isReachable
            ? "bg-blue-500/20 text-muted-foreground/30"
            : "text-muted-foreground/30"

      cells.push(
        <div
          key={`${col}-${renderRow}`}
          data-testid={entity ? `cell-${col}-${gridRow}` : isReachable ? `reachable-${col}-${gridRow}` : undefined}
          className={`aspect-square flex items-center justify-center text-xs font-mono ${wallClasses} ${bgClass} ${isClickable ? "cursor-pointer hover:bg-blue-500/40" : ""}`}
          onClick={isClickable ? () => handleCellClick(col * 5, gridRow * 5) : undefined}
        >
          {entity ? entity.glyph : "·"}
        </div>,
      )
    }
  }

  return (
    <div className="space-y-1" data-testid="battle-map">
      <h3 className="text-xs font-medium uppercase text-muted-foreground">
        {t("game:battle_map")}
      </h3>
      <div
        className="rounded border border-border bg-muted/50 p-1"
        style={{ display: "grid", gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
      >
        {cells}
      </div>
    </div>
  )
}
