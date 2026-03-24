import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import { BudgetDisplay } from "./BudgetDisplay"
import { Button } from "@/components/ui/button"
import { Loader2, ChevronDown } from "lucide-react"
import type { CombatAwareness, Awareness } from "@/types/game"

// Actions that need a target dropdown (enemy selection)
const TARGET_ACTIONS = new Set(["attack"])

// Actions that need a directional dropdown (toward/away per enemy)
const DIRECTIONAL_ACTIONS = new Set(["move", "dash"])

// Actions that need an item dropdown
const ITEM_ACTIONS = new Set(["use_item"])

// Actions that need a weapon dropdown (pick from inventory weapons)
const WEAPON_ACTIONS = new Set(["equip"])

// Actions that are just a button click (no params)
const SIMPLE_ACTIONS = new Set(["dodge", "flee", "disengage", "bless", "second_wind", "unequip", "idle", "wait", "end_turn"])

// Visual variants for specific actions
const ACTION_VARIANT: Record<string, "destructive" | "secondary" | "outline"> = {
  attack: "destructive",
  end_turn: "outline",
}

function getActionLabel(t: (key: string) => string, name: string): string {
  const key = `game:${name}`
  const result = t(key)
  // If i18n returns the key itself, it's missing — use raw name
  return result === key ? name : result
}

export function ActionBar() {
  const { t } = useTranslation(["game", "common"])
  const isMyTurn = useGameStore((s) => s.isMyTurn)
  const waitingForAction = useGameStore((s) => s.waitingForAction)
  const budget = useGameStore((s) => s.budget)
  const mode = useGameStore((s) => s.mode)
  const awareness = useGameStore((s) => s.awareness)
  const [openDropdown, setOpenDropdown] = useState<string | null>(null)

  const sendAction = (name: string, params?: Record<string, unknown>) => {
    wsClient.send({ type: "action", name, params })
    useGameStore.getState().setWaitingForAction(true)
    setOpenDropdown(null)
  }

  if (!isMyTurn) {
    return (
      <div className="flex items-center gap-2 border-t border-border px-4 py-2 text-sm text-muted-foreground">
        {waitingForAction && <Loader2 className="size-4 animate-spin" />}
        {t("common:waiting_for_turn")}
      </div>
    )
  }

  const available = awareness?.available_actions ?? []
  const availableItems = awareness?.available_items ?? []
  const has = (name: string) => available.includes(name)

  const isCombat = mode === "combat" && awareness && "self_hp" in awareness
  const enemies = isCombat ? (awareness as CombatAwareness).nearby : []

  // Backend already filters available_actions by budget — if it's in the list, it's affordable.
  // Only disable while waiting for server response.
  const isDisabled = () => waitingForAction

  return (
    <div className="border-t border-border px-4 py-2">
      {budget && (
        <div className="mb-2">
          <BudgetDisplay budget={budget} />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {available.map((name) => {
          // Target dropdown: attack
          if (TARGET_ACTIONS.has(name) && enemies.length > 0) {
            return (
              <TargetDropdown
                key={name}
                name={name}
                enemies={enemies}
                disabled={isDisabled()}
                openDropdown={openDropdown}
                setOpenDropdown={setOpenDropdown}
                sendAction={sendAction}
                t={t}
              />
            )
          }

          // Directional dropdown: move, dash
          if (DIRECTIONAL_ACTIONS.has(name) && enemies.length > 0) {
            return (
              <DirectionalDropdown
                key={name}
                name={name}
                enemies={enemies}
                disabled={isDisabled()}
                openDropdown={openDropdown}
                setOpenDropdown={setOpenDropdown}
                sendAction={sendAction}
                t={t}
              />
            )
          }

          // Item dropdown: use_item
          if (ITEM_ACTIONS.has(name) && availableItems.length > 0) {
            return (
              <ItemDropdown
                key={name}
                items={availableItems}
                disabled={isDisabled()}
                openDropdown={openDropdown}
                setOpenDropdown={setOpenDropdown}
                sendAction={sendAction}
                t={t}
              />
            )
          }

          // Weapon dropdown: equip
          if (WEAPON_ACTIONS.has(name)) {
            const weapons = availableItems.filter((i) => i.description.toLowerCase().includes("weapon"))
            if (weapons.length > 0) {
              return (
                <div key={name} className="relative">
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={isDisabled()}
                    onClick={() => {
                      if (weapons.length === 1) {
                        sendAction("equip", { weapon_id: weapons[0].id })
                      } else {
                        setOpenDropdown(openDropdown === "equip" ? null : "equip")
                      }
                    }}
                  >
                    {getActionLabel(t, "equip")}
                    {weapons.length > 1 && <ChevronDown className="ml-1 size-3" />}
                  </Button>
                  {openDropdown === "equip" && weapons.length > 1 && (
                    <div className="absolute bottom-full left-0 z-10 mb-1 min-w-[180px] rounded border border-border bg-popover p-1 shadow-md">
                      {weapons.map((w) => (
                        <button
                          key={w.id}
                          className="w-full rounded px-2 py-1 text-left text-xs hover:bg-accent"
                          onClick={() => sendAction("equip", { weapon_id: w.id })}
                        >
                          {w.description || w.name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )
            }
            return null
          }

          // Simple button
          if (SIMPLE_ACTIONS.has(name) || !TARGET_ACTIONS.has(name) && !DIRECTIONAL_ACTIONS.has(name) && !ITEM_ACTIONS.has(name) && !WEAPON_ACTIONS.has(name)) {
            return (
              <Button
                key={name}
                size="sm"
                variant={ACTION_VARIANT[name] ?? "secondary"}
                disabled={isDisabled()}
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

          return null
        })}

        {/* end_turn is always available even if not in the list */}
        {!has("end_turn") && (
          <Button
            size="sm"
            variant="outline"
            disabled={waitingForAction}
            onClick={() => sendAction("end_turn")}
          >
            {getActionLabel(t, "end_turn")}
          </Button>
        )}
      </div>
    </div>
  )
}

// --- Sub-components for dropdowns ---

interface DropdownProps {
  openDropdown: string | null
  setOpenDropdown: (v: string | null) => void
  sendAction: (name: string, params?: Record<string, unknown>) => void
  t: (key: string, opts?: Record<string, unknown>) => string
  disabled: boolean
}

interface TargetDropdownProps extends DropdownProps {
  name: string
  enemies: { id: string; distance_ft?: number }[]
}

function TargetDropdown({ name, enemies, disabled, openDropdown, setOpenDropdown, sendAction, t }: TargetDropdownProps) {
  return (
    <div className="relative">
      <Button
        size="sm"
        variant={ACTION_VARIANT[name] ?? "secondary"}
        disabled={disabled}
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

function DirectionalDropdown({ name, enemies, disabled, openDropdown, setOpenDropdown, sendAction, t }: DirectionalDropdownProps) {
  const towardKey = name === "dash" ? "game:dash_toward" : "game:move_toward"
  const awayKey = name === "dash" ? "game:dash_away" : "game:move_away"

  return (
    <div className="relative">
      <Button
        size="sm"
        variant="secondary"
        disabled={disabled}
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

interface ItemDropdownProps extends DropdownProps {
  items: { id: string; name: string; description: string }[]
}

function ItemDropdown({ items, disabled, openDropdown, setOpenDropdown, sendAction, t }: ItemDropdownProps) {
  return (
    <div className="relative">
      <Button
        size="sm"
        variant="secondary"
        disabled={disabled}
        onClick={() => {
          if (items.length === 1) {
            sendAction("use_item", { item_id: items[0].id })
          } else {
            setOpenDropdown(openDropdown === "use_item" ? null : "use_item")
          }
        }}
      >
        {getActionLabel(t, "use_item")}
        {items.length > 1 && <ChevronDown className="ml-1 size-3" />}
      </Button>
      {openDropdown === "use_item" && items.length > 1 && (
        <div className="absolute bottom-full left-0 z-10 mb-1 min-w-[180px] rounded border border-border bg-popover p-1 shadow-md">
          {items.map((item) => (
            <button
              key={item.id}
              className="w-full rounded px-2 py-1 text-left text-xs hover:bg-accent"
              onClick={() => sendAction("use_item", { item_id: item.id })}
            >
              {item.description || item.name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
