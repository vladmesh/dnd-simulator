import { useState, useCallback } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import { BudgetDisplay } from "./BudgetDisplay"
import { Button } from "@/components/ui/button"
import { Loader2 } from "lucide-react"
import { categorizeActions } from "@/lib/actionCategories"
import { getActionLabel } from "./action-bar/utils"
import { ActionButton } from "./action-bar/ActionButton"
import { ConsumableDrawer } from "./action-bar/ConsumableDrawer"
import { ClassFeatureDrawer } from "./action-bar/ClassFeatureDrawer"
import { InventoryDrawer } from "./action-bar/InventoryDrawer"

export function ActionBar() {
  const { t } = useTranslation(["game", "common"])
  const isMyTurn = useGameStore((s) => s.isMyTurn)
  const waitingForAction = useGameStore((s) => s.waitingForAction)
  const budget = useGameStore((s) => s.budget) ?? undefined
  const mode = useGameStore((s) => s.mode)
  const awareness = useGameStore((s) => s.awareness)
  const player = useGameStore((s) => s.player)
  const [openDropdown, setOpenDropdown] = useState<string | null>(null)

  const sendAction = useCallback((name: string, params?: Record<string, unknown>) => {
    wsClient.send({ type: "action", name, params })
    useGameStore.getState().setWaitingForAction(true)
    setOpenDropdown(null)
  }, [])

  if (!isMyTurn) {
    return (
      <div className="flex items-center gap-2 border-t border-border px-4 py-2 text-sm text-muted-foreground">
        {waitingForAction && <Loader2 className="size-4 animate-spin" />}
        {t("common:waiting_for_turn")}
      </div>
    )
  }

  const ALWAYS_HIDDEN = new Set(["buy", "sell", "take", "move", "move_to", "travel"])
  const PEACEFUL_ONLY_HIDDEN = new Set(["use_item", "equip", "unequip"])
  const available = (awareness?.available_actions ?? []).filter(
    (a) => !ALWAYS_HIDDEN.has(a.name) && !(mode === "peaceful" && PEACEFUL_ONLY_HIDDEN.has(a.name)),
  )
  const availableItems = awareness?.available_items ?? []

  const isCombat = mode === "combat" && awareness && "self_hp" in awareness
  const nearby = awareness?.nearby ?? []
  const selfId = player?.player_id
  const spellSlots =
    (isCombat && "self_resource_pools" in awareness ? awareness.self_resource_pools : undefined) ??
    player?.resource_pools

  const groups = categorizeActions(available)

  const consumableItems = availableItems.filter((item) => {
    const t = item.item_type ?? item.type
    return t === "potion" || t === "scroll" || t === "bomb"
  })

  const showConsumableDrawer = groups.consumables.length > 0 && consumableItems.length > 0
  const showClassFeatureDrawer = groups.classFeatures.length > 0
  const showInventoryDrawer = isCombat && groups.inventory.length > 0
  // Drawer stays open when a child action's sub-dropdown (target, smite) is active
  const classFeatureNames = new Set(groups.classFeatures.map((a) => a.name))
  const stripChildSuffix = (key: string) => key.replace(/-(smite|amount)$/, "")
  const isClassFeatureChildOpen = openDropdown != null && (classFeatureNames.has(openDropdown) || classFeatureNames.has(stripChildSuffix(openDropdown)))
  const hasDrawers = showConsumableDrawer || showClassFeatureDrawer || showInventoryDrawer

  const actionButtonProps = {
    nearby,
    selfId,
    disabled: waitingForAction,
    budget,
    openDropdown,
    setOpenDropdown,
    sendAction,
    t,
    spellSlots,
  }

  return (
    <div className="border-t border-border px-4 py-2" tabIndex={-1}
      onKeyDown={(e) => { if (e.key === "Escape") setOpenDropdown(null) }}
    >
      {budget && (
        <div className="mb-2">
          <BudgetDisplay budget={budget} />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {groups.core.map((action) => (
          <ActionButton key={action.name} action={action} {...actionButtonProps} />
        ))}

        {groups.other.map((action) => (
          <ActionButton key={action.name} action={action} {...actionButtonProps} />
        ))}

        {hasDrawers && <div className="mx-1 h-6 w-px bg-border" />}

        {showConsumableDrawer && (
          <ConsumableDrawer
            items={consumableItems}
            isOpen={openDropdown === "drawer:consumables"}
            onToggle={() => setOpenDropdown(openDropdown === "drawer:consumables" ? null : "drawer:consumables")}
            disabled={waitingForAction}
            sendAction={sendAction}
          />
        )}

        {showClassFeatureDrawer && (
          <ClassFeatureDrawer
            actions={groups.classFeatures}
            isOpen={openDropdown === "drawer:class-features" || isClassFeatureChildOpen}
            onToggle={() => setOpenDropdown(openDropdown === "drawer:class-features" || isClassFeatureChildOpen ? null : "drawer:class-features")}
            disabled={waitingForAction}
            nearby={nearby}
            selfId={selfId}
            budget={budget}
            openDropdown={openDropdown}
            setOpenDropdown={setOpenDropdown}
            sendAction={sendAction}
            spellSlots={spellSlots}
          />
        )}

        {showInventoryDrawer && (
          <InventoryDrawer
            actions={groups.inventory}
            items={availableItems}
            isOpen={openDropdown === "drawer:inventory"}
            onToggle={() => setOpenDropdown(openDropdown === "drawer:inventory" ? null : "drawer:inventory")}
            disabled={waitingForAction}
            sendAction={sendAction}
          />
        )}

        {groups.endTurn ? (
          <ActionButton action={groups.endTurn} {...actionButtonProps} />
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
