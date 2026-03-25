import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import { ChevronDown, ChevronRight, Package, Sword, Shield, Crown, Footprints, Gem, ShieldPlus } from "lucide-react"
import type { EquippedInfo, ItemInfo } from "@/types/game"

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

function EquipmentSlot({ slot, item }: { slot: string; item?: EquippedInfo }) {
  const { t } = useTranslation(["game"])
  const Icon = SLOT_ICONS[slot] ?? Package
  const waitingForAction = useGameStore((s) => s.waitingForAction)

  return (
    <div className="flex items-center gap-2 rounded border border-border px-2 py-1">
      <Icon className="size-3 shrink-0 text-muted-foreground" />
      {item ? (
        <button
          className="min-w-0 flex-1 truncate text-left text-xs hover:text-primary disabled:opacity-50"
          title={`${item.description}\n${t("game:click_to_unequip")}`}
          disabled={waitingForAction}
          onClick={() => sendAction(UNEQUIP_ACTION[slot] ?? "unequip")}
        >
          {item.name}
        </button>
      ) : (
        <span className="flex-1 text-xs text-muted-foreground">
          {t(`game:slot_${slot}`, { defaultValue: slot })}
        </span>
      )}
    </div>
  )
}

function BagItem({ item }: { item: ItemInfo }) {
  const waitingForAction = useGameStore((s) => s.waitingForAction)

  const equipSlot = getEquipSlot(item)
  const isConsumable = item.type === "potion"

  const handleEquip = () => {
    if (!equipSlot) return
    const cfg = EQUIP_ACTION[equipSlot]
    if (!cfg) return
    sendAction(cfg.action, { [cfg.paramKey]: item.id })
  }

  return (
    <div className="flex items-center gap-1 text-xs">
      <span className="min-w-0 flex-1 truncate" title={item.description}>
        {item.name}
        {item.price != null && (
          <span className="ml-1 text-muted-foreground">{item.price}g</span>
        )}
      </span>
      {isConsumable && (
        <button
          className="shrink-0 rounded bg-accent px-1.5 py-0.5 text-[10px] hover:bg-accent/80 disabled:opacity-50"
          disabled={waitingForAction}
          onClick={() => sendAction("use_item", { item_id: item.id })}
        >
          USE
        </button>
      )}
      {equipSlot && (
        <button
          className="shrink-0 rounded bg-accent px-1.5 py-0.5 text-[10px] hover:bg-accent/80 disabled:opacity-50"
          disabled={waitingForAction}
          onClick={handleEquip}
        >
          EQUIP
        </button>
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
            {SLOT_ORDER.map((slot) => (
              <EquipmentSlot key={slot} slot={slot} item={equippedBySlot.get(slot)} />
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
