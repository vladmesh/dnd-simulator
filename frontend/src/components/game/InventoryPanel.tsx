import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import { ChevronDown, ChevronRight, Package, Sword, Shield, Crown, Footprints, Gem, ShieldPlus } from "lucide-react"
import type { EquippedInfo, ItemInfo } from "@/types/game"
import { ItemDetails } from "./ItemDetails"
import { isCostDepleted } from "./action-bar/utils"

const SLOT_ORDER = ["weapon", "armor", "shield", "head", "feet", "ring"] as const
const SLOT_ICONS: Record<string, React.ElementType> = {
  weapon: Sword,
  armor: Shield,
  shield: ShieldPlus,
  head: Crown,
  feet: Footprints,
  ring: Gem,
}

function sendAction(name: string, params?: Record<string, unknown>) {
  wsClient.send({ type: "action", name, params })
  useGameStore.getState().setWaitingForAction(true)
}

const UNEQUIP_ACTION: Record<string, string> = {
  weapon: "unequip",
  armor: "unequip_armor",
  shield: "unequip_shield",
  head: "unequip_head",
  feet: "unequip_feet",
  ring: "unequip_ring",
}

const EQUIP_ACTION: Record<string, { action: string; paramKey: string }> = {
  weapon: { action: "equip", paramKey: "weapon_id" },
  armor: { action: "equip_armor", paramKey: "armor_id" },
  shield: { action: "equip_shield", paramKey: "shield_id" },
  head: { action: "equip_head", paramKey: "head_id" },
  feet: { action: "equip_feet", paramKey: "feet_id" },
  ring: { action: "equip_ring", paramKey: "ring_id" },
}

function getEquipSlot(item: ItemInfo): string | undefined {
  if (item.type === "weapon") return "weapon"
  if (item.type === "armor") return "armor"
  if (item.type === "shield") return "shield"
  if (item.type === "accessory" && item.slot) return item.slot
  return undefined
}

/**
 * Why an equip/unequip action cannot be taken right now, or null. Only combat restricts it:
 * the server withholds the action from `available_actions` and says why in `blocked_actions`
 * (armor/accessories: wrong mode; shield: no Action left). Frontend text is keyed by the
 * server's `reason_key`, falling back to its localised `reason`.
 */
function useEquipBlockedReason(action: string | undefined): string | null {
  const { t } = useTranslation(["game"])
  const mode = useGameStore((s) => s.mode)
  const isMyTurn = useGameStore((s) => s.isMyTurn)
  const budget = useGameStore((s) => s.budget)
  const awareness = useGameStore((s) => s.awareness)

  if (mode !== "combat" || !action) return null
  const blocked = (awareness && "blocked_actions" in awareness ? awareness.blocked_actions : undefined) ?? []
  const block = blocked.find((b) => b.name === action)
  const blockText = block
    ? t(`game:equip_reason_${block.reason_key.toLowerCase()}`, { defaultValue: block.reason })
    : null
  // Not available in combat at all outranks "not your turn": waiting will not help.
  if (block?.reason_key === "WRONG_MODE") return blockText
  if (!isMyTurn) return t("game:equip_not_your_turn")
  if (blockText) return blockText
  const info = (awareness?.available_actions ?? []).find((a) => a.name === action)
  if (info && isCostDepleted(info.cost_type, budget ?? undefined)) return t("game:equip_reason_insufficient_budget")
  return null
}

function EquipmentSlot({ slot, item, align }: { slot: string; item?: EquippedInfo; align?: "left" | "right" }) {
  const { t } = useTranslation(["game"])
  const Icon = SLOT_ICONS[slot] ?? Package
  const waitingForAction = useGameStore((s) => s.waitingForAction)
  const unequipAction = UNEQUIP_ACTION[slot] ?? "unequip"
  const blockedReason = useEquipBlockedReason(item ? unequipAction : undefined)

  return (
    <div className="flex items-center gap-2 rounded border border-border px-2 py-1">
      <Icon className="size-3 shrink-0 text-muted-foreground" />
      {item ? (
        <ItemDetails
          item={item}
          align={align}
          hint={blockedReason ?? t("game:click_to_unequip")}
          className="min-w-0 flex-1"
        >
          <button
            className="block w-full truncate text-left text-xs hover:text-primary disabled:opacity-50"
            disabled={waitingForAction || !!blockedReason}
            title={blockedReason ?? undefined}
            data-testid={`unequip-${slot}`}
            onClick={() => sendAction(unequipAction)}
          >
            {item.name}
          </button>
        </ItemDetails>
      ) : (
        <span className="flex-1 text-xs text-muted-foreground">
          {t(`game:slot_${slot}`, { defaultValue: slot })}
        </span>
      )}
    </div>
  )
}

function BagItem({ item }: { item: ItemInfo }) {
  const { t } = useTranslation(["game"])
  const waitingForAction = useGameStore((s) => s.waitingForAction)

  const equipSlot = getEquipSlot(item)
  const isConsumable = item.type === "potion"
  const blockedReason = useEquipBlockedReason(equipSlot ? EQUIP_ACTION[equipSlot]?.action : undefined)

  const handleEquip = () => {
    if (!equipSlot) return
    const cfg = EQUIP_ACTION[equipSlot]
    if (!cfg) return
    sendAction(cfg.action, { [cfg.paramKey]: item.id })
  }

  return (
    <div data-testid={`bag-${item.id}`}>
      <div className="flex items-center gap-1 text-xs">
        <ItemDetails item={item} className="min-w-0 flex-1">
          <span className="block truncate">
            {item.name}
            {item.price != null && (
              <span className="ml-1 text-muted-foreground">{item.price}g</span>
            )}
          </span>
        </ItemDetails>
        {isConsumable && (
          <button
            className="shrink-0 rounded bg-accent px-1.5 py-0.5 text-[10px] hover:bg-accent/80 disabled:opacity-50"
            disabled={waitingForAction}
            onClick={() => sendAction("use_item", { item_id: item.id })}
          >
            {t("game:use")}
          </button>
        )}
        {equipSlot && (
          <button
            className="shrink-0 rounded bg-accent px-1.5 py-0.5 text-[10px] hover:bg-accent/80 disabled:opacity-50"
            disabled={waitingForAction || !!blockedReason}
            title={blockedReason ?? undefined}
            onClick={handleEquip}
          >
            {t("game:equip")}
          </button>
        )}
      </div>
      {equipSlot && blockedReason && (
        <div className="text-[10px] text-muted-foreground" data-testid="equip-reason">
          {blockedReason}
        </div>
      )}
    </div>
  )
}

export function InventoryPanel() {
  const { t } = useTranslation(["game"])
  const player = useGameStore((s) => s.player)
  const [expanded, setExpanded] = useState(true)

  if (!player) return null

  const equipped = player.equipped ?? []
  const inventory = player.inventory ?? []
  const equippedBySlot = new Map(equipped.map((e) => [e.slot, e]))

  return (
    <div className="space-y-2">
      <button
        className="flex w-full items-center gap-1 text-xs font-medium uppercase text-muted-foreground"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        {t("game:inventory")}
      </button>
      {expanded && (
        <div className="space-y-2">
          {/* Equipment slots */}
          <div className="grid grid-cols-2 gap-1">
            {SLOT_ORDER.map((slot, i) => (
              <EquipmentSlot key={slot} slot={slot} item={equippedBySlot.get(slot)} align={i % 2 === 1 ? "right" : "left"} />
            ))}
          </div>

          {/* Bag */}
          {inventory.length > 0 && (
            <div className="space-y-1">
              <div className="flex items-center gap-1 text-[10px] uppercase text-muted-foreground">
                <Package className="size-3" />
                {t("game:bag")}
              </div>
              <div className="max-h-32 space-y-0.5 overflow-y-auto">
                {inventory.map((item) => (
                  <BagItem key={item.id} item={item} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
