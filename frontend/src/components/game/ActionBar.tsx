import { useState, useRef, useCallback, useEffect } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import { BudgetDisplay } from "./BudgetDisplay"
import { Button } from "@/components/ui/button"
import { Loader2 } from "lucide-react"
import { categorizeActions } from "@/lib/actionCategories"
import type { CombatAwareness, ActionInfo } from "@/types/game"
import { hasParam, getActionLabel, isCostDepleted, getButtonVariant, getCostTypeClass } from "./action-bar/utils"
import { TargetDropdown } from "./action-bar/TargetDropdown"
import { DirectionalDropdown } from "./action-bar/DirectionalDropdown"
import { ConsumableDrawer } from "./action-bar/ConsumableDrawer"
import { ClassFeatureDrawer } from "./action-bar/ClassFeatureDrawer"
import { InventoryDrawer } from "./action-bar/InventoryDrawer"

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
          <ConsumableDrawer
            items={consumableItems}
            isOpen={openDropdown === "drawer:consumables"}
            onToggle={() => setOpenDropdown(openDropdown === "drawer:consumables" ? null : "drawer:consumables")}
            disabled={isDisabled()}
            sendAction={sendAction}
          />
        )}

        {showClassFeatureDrawer && (
          <ClassFeatureDrawer
            actions={groups.classFeatures}
            isOpen={openDropdown === "drawer:class-features"}
            onToggle={() => setOpenDropdown(openDropdown === "drawer:class-features" ? null : "drawer:class-features")}
            disabled={isDisabled()}
            sendAction={sendAction}
          />
        )}

        {showInventoryDrawer && (
          <InventoryDrawer
            actions={groups.inventory}
            items={availableItems}
            isOpen={openDropdown === "drawer:inventory"}
            onToggle={() => setOpenDropdown(openDropdown === "drawer:inventory" ? null : "drawer:inventory")}
            disabled={isDisabled()}
            sendAction={sendAction}
          />
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
