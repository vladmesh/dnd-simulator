import { useState, useRef, useCallback, useEffect } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import { BudgetDisplay } from "./BudgetDisplay"
import { Button } from "@/components/ui/button"
import { Loader2, ChevronDown, FlaskConical, Sparkles, Backpack } from "lucide-react"
import { categorizeActions } from "@/lib/actionCategories"
import type { CombatAwareness, ActionInfo, TurnBudget, ItemInfo } from "@/types/game"

/** Check if an action has a specific param by name. */
function hasParam(action: ActionInfo, paramName: string): boolean {
  return action.params.some((p) => p.name === paramName)
}

function getActionLabel(t: (key: string) => string, name: string): string {
  const key = `game:${name}`
  const result = t(key)
  return result === key ? name : result
}

/** Check if the cost type's budget is depleted. */
function isCostDepleted(costType: string | undefined, budget: TurnBudget | undefined): boolean {
  if (!budget || !costType) return false
  switch (costType) {
    case "action": return budget.actions <= 0
    case "bonus_action": return budget.bonus_actions <= 0
    case "movement": return budget.movement_remaining <= 0
    default: return false
  }
}

/** Get button variant based on action name and cost type. */
function getButtonVariant(name: string, costType: string | undefined): "destructive" | "secondary" | "outline" {
  if (name === "attack") return "destructive"
  if (name === "end_turn") return "outline"
  if (costType === "bonus_action") return "secondary"
  return "secondary"
}

/** Get cost-type specific className. */
function getCostTypeClass(costType: string | undefined): string {
  if (costType === "bonus_action") return "ring-1 ring-amber-400/60 text-amber-200"
  if (costType === "free") return "opacity-80"
  return ""
}

export function ActionBar() {
  const { t } = useTranslation(["game", "common"])
  const isMyTurn = useGameStore((s) => s.isMyTurn)
  const waitingForAction = useGameStore((s) => s.waitingForAction)
  const budget = useGameStore((s) => s.budget)
  const mode = useGameStore((s) => s.mode)
  const awareness = useGameStore((s) => s.awareness)
  const [openDropdown, setOpenDropdown] = useState<string | null>(null)
  const [sayOpen, setSayOpen] = useState(false)
  const [sayText, setSayText] = useState("")
  const sayInputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const sendAction = useCallback((name: string, params?: Record<string, unknown>) => {
    wsClient.send({ type: "action", name, params })
    useGameStore.getState().setWaitingForAction(true)
    setOpenDropdown(null)
  }, [])

  // Close any open drawer/dropdown on Escape
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpenDropdown(null)
      }
    }
    el.addEventListener("keydown", handleKeyDown)
    return () => el.removeEventListener("keydown", handleKeyDown)
  }, [])

  if (!isMyTurn) {
    return (
      <div className="flex items-center gap-2 border-t border-border px-4 py-2 text-sm text-muted-foreground">
        {waitingForAction && <Loader2 className="size-4 animate-spin" />}
        {t("common:waiting_for_turn")}
      </div>
    )
  }

  // buy/sell always handled by TradePanel; use_item/equip/unequip handled by
  // InventoryPanel in peaceful mode, but must stay in ActionBar during combat
  const ALWAYS_HIDDEN = new Set(["buy", "sell", "move", "move_to"])
  const PEACEFUL_ONLY_HIDDEN = new Set(["use_item", "equip", "unequip"])
  const available = (awareness?.available_actions ?? []).filter(
    (a) => !ALWAYS_HIDDEN.has(a.name) && !(mode === "peaceful" && PEACEFUL_ONLY_HIDDEN.has(a.name)),
  )
  const availableItems = awareness?.available_items ?? []

  const isCombat = mode === "combat" && awareness && "self_hp" in awareness
  const enemies = isCombat ? (awareness as CombatAwareness).nearby : []

  const isDisabled = () => waitingForAction

  const groups = categorizeActions(available)

  // Filter consumable items (potions etc.) from available_items
  const consumableItems = availableItems.filter((item) => {
    const t = item.item_type ?? item.type
    return t === "potion" || t === "scroll" || t === "bomb"
  })

  /** Render a single action — handles all parameter variants. */
  const renderAction = (action: ActionInfo) => {
    const { name } = action
    const costType = action.cost_type
    const depleted = isCostDepleted(costType, budget)
    const costClass = getCostTypeClass(costType)
    const dataAttrs: Record<string, string> = {}
    if (costType) dataAttrs["data-cost-type"] = costType
    if (depleted) dataAttrs["data-depleted"] = ""

    // Has target_id param → target dropdown
    if (hasParam(action, "target_id") && enemies.length > 0) {
      return (
        <TargetDropdown
          key={name}
          name={name}
          description={action.description}
          enemies={enemies}
          disabled={isDisabled()}
          openDropdown={openDropdown}
          setOpenDropdown={setOpenDropdown}
          sendAction={sendAction}
          t={t}
          costType={costType}
          depleted={depleted}
          costClass={costClass}
        />
      )
    }

    // Has toward/away_from/direction params → directional dropdown
    if ((hasParam(action, "toward") || hasParam(action, "direction")) && enemies.length > 0) {
      return (
        <DirectionalDropdown
          key={name}
          name={name}
          description={action.description}
          enemies={enemies}
          disabled={isDisabled()}
          openDropdown={openDropdown}
          setOpenDropdown={setOpenDropdown}
          sendAction={sendAction}
          t={t}
          costType={costType}
          depleted={depleted}
          costClass={costClass}
        />
      )
    }

    // Say — needs text input
    if (name === "say") {
      return (
        <div key={name} className="relative flex items-center gap-1">
          {sayOpen ? (
            <>
              <input
                ref={sayInputRef}
                type="text"
                className="h-8 rounded border border-border bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
                placeholder={t("game:say_placeholder")}
                value={sayText}
                onChange={(e) => setSayText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && sayText.trim()) {
                    sendAction("say", { text: sayText.trim() })
                    setSayText("")
                    setSayOpen(false)
                  }
                  if (e.key === "Escape") {
                    setSayText("")
                    setSayOpen(false)
                  }
                }}
                disabled={isDisabled()}
                autoFocus
              />
              <Button
                size="sm"
                variant="secondary"
                disabled={isDisabled() || !sayText.trim()}
                onClick={() => {
                  if (sayText.trim()) {
                    sendAction("say", { text: sayText.trim() })
                    setSayText("")
                    setSayOpen(false)
                  }
                }}
              >
                ↵
              </Button>
            </>
          ) : (
            <Button
              size="sm"
              variant="secondary"
              disabled={isDisabled()}
              title={action.description}
              className={costClass}
              {...dataAttrs}
              onClick={() => setSayOpen(true)}
            >
              {getActionLabel(t, name)}
            </Button>
          )}
        </div>
      )
    }

    // Simple button — no special params
    return (
      <Button
        key={name}
        size="sm"
        variant={getButtonVariant(name, costType)}
        disabled={isDisabled()}
        title={action.description}
        className={costClass}
        {...dataAttrs}
        onClick={() => {
          if (name === "wait") {
            sendAction("wait", { hours: 1 })
          } else {
            sendAction(name)
          }
        }}
      >
        {getActionLabel(t, name)}
      </Button>
    )
  }

  const showConsumableDrawer = groups.consumables.length > 0 && consumableItems.length > 0
  const showClassFeatureDrawer = groups.classFeatures.length > 0
  const showInventoryDrawer = isCombat && groups.inventory.length > 0
  const hasDrawers = showConsumableDrawer || showClassFeatureDrawer || showInventoryDrawer

  return (
    <div ref={containerRef} className="border-t border-border px-4 py-2" tabIndex={-1}
      onKeyDown={(e) => { if (e.key === "Escape") setOpenDropdown(null) }}
    >
      {budget && (
        <div className="mb-2">
          <BudgetDisplay budget={budget} />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {/* Core actions first */}
        {groups.core.map(renderAction)}

        {/* Other actions (say, wait, idle, move) */}
        {groups.other.map(renderAction)}

        {/* Drawer section — separated by a thin divider when present */}
        {hasDrawers && <div className="mx-1 h-6 w-px bg-border" />}

        {showConsumableDrawer && (
          <ActionDrawer
            drawerKey="consumables"
            icon={<FlaskConical className="size-3.5" />}
            count={consumableItems.length}
            isOpen={openDropdown === "drawer:consumables"}
            onToggle={() => setOpenDropdown(openDropdown === "drawer:consumables" ? null : "drawer:consumables")}
            disabled={isDisabled()}
            title={t("game:consumables_tooltip", "Consumable items")}
          >
            {consumableItems.map((item) => (
              <button
                key={item.id}
                className="flex w-full flex-col gap-0.5 rounded px-3 py-1.5 text-left text-xs hover:bg-accent"
                onClick={() => sendAction("use_item", { item_id: item.id })}
              >
                <span className="font-medium">{item.name}</span>
                {item.description && (
                  <span className="text-muted-foreground">{item.description}</span>
                )}
              </button>
            ))}
          </ActionDrawer>
        )}

        {showClassFeatureDrawer && (
          <ActionDrawer
            drawerKey="class-features"
            icon={<Sparkles className="size-3.5" />}
            count={groups.classFeatures.length}
            isOpen={openDropdown === "drawer:class-features"}
            onToggle={() => setOpenDropdown(openDropdown === "drawer:class-features" ? null : "drawer:class-features")}
            disabled={isDisabled()}
          >
            {groups.classFeatures.map((action) => (
              <button
                key={action.name}
                className="flex w-full flex-col gap-0.5 rounded px-3 py-1.5 text-left text-xs hover:bg-accent"
                onClick={() => sendAction(action.name)}
              >
                <span className="flex items-center gap-2 font-medium">
                  {getActionLabel(t, action.name)}
                  {action.cost_type && (
                    <span className="rounded bg-muted px-1 text-[10px] text-muted-foreground">
                      {action.cost_type}
                    </span>
                  )}
                </span>
                <span className="text-muted-foreground">{action.description}</span>
              </button>
            ))}
          </ActionDrawer>
        )}

        {showInventoryDrawer && (
          <ActionDrawer
            drawerKey="inventory"
            icon={<Backpack className="size-3.5" />}
            count={groups.inventory.length}
            isOpen={openDropdown === "drawer:inventory"}
            onToggle={() => setOpenDropdown(openDropdown === "drawer:inventory" ? null : "drawer:inventory")}
            disabled={isDisabled()}
          >
            {groups.inventory.map((action) => {
              // For equip actions with weapon_id param, show weapon options
              if (hasParam(action, "weapon_id")) {
                const weapons = availableItems.filter((i) => (i.item_type ?? i.type) === "weapon" || i.description.toLowerCase().includes("weapon"))
                return weapons.map((w) => (
                  <button
                    key={`${action.name}:${w.id}`}
                    className="flex w-full flex-col gap-0.5 rounded px-3 py-1.5 text-left text-xs hover:bg-accent"
                    onClick={() => sendAction(action.name, { weapon_id: w.id })}
                  >
                    <span className="font-medium">{getActionLabel(t, action.name)}: {w.name}</span>
                    {w.description && <span className="text-muted-foreground">{w.description}</span>}
                  </button>
                ))
              }
              // Simple equip/unequip actions (armor, shield, etc.)
              return (
                <button
                  key={action.name}
                  className="flex w-full flex-col gap-0.5 rounded px-3 py-1.5 text-left text-xs hover:bg-accent"
                  onClick={() => sendAction(action.name)}
                >
                  <span className="font-medium">{getActionLabel(t, action.name)}</span>
                  <span className="text-muted-foreground">{action.description}</span>
                </button>
              )
            })}
          </ActionDrawer>
        )}

        {/* End turn always last */}
        {groups.endTurn ? (
          renderAction(groups.endTurn)
        ) : (
          <Button
            size="sm"
            variant="outline"
            disabled={waitingForAction}
            data-cost-type="free"
            onClick={() => sendAction("end_turn")}
          >
            {getActionLabel(t, "end_turn")}
          </Button>
        )}
      </div>
    </div>
  )
}

// --- ActionDrawer generic component ---

interface ActionDrawerProps {
  drawerKey: string
  icon: React.ReactNode
  count: number
  isOpen: boolean
  onToggle: () => void
  disabled: boolean
  title?: string
  children: React.ReactNode
}

function ActionDrawer({ drawerKey, icon, count, isOpen, onToggle, disabled, title, children }: ActionDrawerProps) {
  return (
    <div className="relative">
      <Button
        size="sm"
        variant="secondary"
        disabled={disabled}
        data-drawer={drawerKey}
        onClick={onToggle}
        className="gap-1"
        title={title}
      >
        {icon}
        <span className="text-xs">{count}</span>
      </Button>
      {isOpen && (
        <div
          data-drawer-popup={drawerKey}
          className="absolute bottom-full left-0 z-10 mb-1 min-w-[200px] max-w-[280px] rounded border border-border bg-popover p-1 shadow-md"
        >
          {children}
        </div>
      )}
    </div>
  )
}

// --- Sub-components for dropdowns ---

interface CostProps {
  costType?: string
  depleted: boolean
  costClass: string
}

interface DropdownProps extends CostProps {
  openDropdown: string | null
  setOpenDropdown: (v: string | null) => void
  sendAction: (name: string, params?: Record<string, unknown>) => void
  t: (key: string, opts?: Record<string, unknown>) => string
  disabled: boolean
  description: string
}

interface TargetDropdownProps extends DropdownProps {
  name: string
  enemies: { id: string; distance_ft?: number }[]
}

function TargetDropdown({ name, description, enemies, disabled, openDropdown, setOpenDropdown, sendAction, t, costType, depleted, costClass }: TargetDropdownProps) {
  const dataAttrs: Record<string, string> = {}
  if (costType) dataAttrs["data-cost-type"] = costType
  if (depleted) dataAttrs["data-depleted"] = ""

  return (
    <div className="relative">
      <Button
        size="sm"
        variant={getButtonVariant(name, costType)}
        disabled={disabled}
        title={description}
        className={costClass}
        {...dataAttrs}
        onClick={() => {
          if (enemies.length === 1) {
            sendAction(name, { target_id: enemies[0].id })
          } else {
            setOpenDropdown(openDropdown === name ? null : name)
          }
        }}
      >
        {getActionLabel(t, name)}
        {enemies.length > 1 && <ChevronDown className="ml-1 size-3" />}
      </Button>
      {openDropdown === name && enemies.length > 1 && (
        <div className="absolute bottom-full left-0 z-10 mb-1 min-w-[160px] rounded border border-border bg-popover p-1 shadow-md">
          {enemies.map((e) => (
            <button
              key={e.id}
              className="w-full rounded px-2 py-1 text-left text-xs hover:bg-accent"
              onClick={() => sendAction(name, { target_id: e.id })}
            >
              {t("game:attack_target", { target: e.id })}
              {e.distance_ft != null && (
                <span className="ml-1 text-muted-foreground">({e.distance_ft}ft)</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

interface DirectionalDropdownProps extends DropdownProps {
  name: string
  enemies: { id: string }[]
}

function DirectionalDropdown({ name, description, enemies, disabled, openDropdown, setOpenDropdown, sendAction, t, costType, depleted, costClass }: DirectionalDropdownProps) {
  const towardKey = name === "dash" ? "game:dash_toward" : "game:move_toward"
  const awayKey = name === "dash" ? "game:dash_away" : "game:move_away"
  const dataAttrs: Record<string, string> = {}
  if (costType) dataAttrs["data-cost-type"] = costType
  if (depleted) dataAttrs["data-depleted"] = ""

  return (
    <div className="relative">
      <Button
        size="sm"
        variant="secondary"
        disabled={disabled}
        title={description}
        className={costClass}
        {...dataAttrs}
        onClick={() => setOpenDropdown(openDropdown === name ? null : name)}
      >
        {getActionLabel(t, name)}
        <ChevronDown className="ml-1 size-3" />
      </Button>
      {openDropdown === name && (
        <div className="absolute bottom-full left-0 z-10 mb-1 min-w-[180px] rounded border border-border bg-popover p-1 shadow-md">
          {enemies.map((e) => (
            <div key={e.id} className="flex gap-1">
              <button
                className="flex-1 rounded px-2 py-1 text-left text-xs hover:bg-accent"
                onClick={() => sendAction(name, { toward: e.id })}
              >
                {t(towardKey, { target: e.id })}
              </button>
              <button
                className="flex-1 rounded px-2 py-1 text-left text-xs hover:bg-accent"
                onClick={() => sendAction(name, { away_from: e.id })}
              >
                {t(awayKey, { target: e.id })}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
