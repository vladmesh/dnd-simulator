import { useState, useRef } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import { BudgetDisplay } from "./BudgetDisplay"
import { Button } from "@/components/ui/button"
import { Loader2, ChevronDown } from "lucide-react"
import type { CombatAwareness, Awareness, ActionInfo } from "@/types/game"

// Visual variants for specific actions
const ACTION_VARIANT: Record<string, "destructive" | "secondary" | "outline"> = {
  attack: "destructive",
  end_turn: "outline",
}

/** Check if an action has a specific param by name. */
function hasParam(action: ActionInfo, paramName: string): boolean {
  return action.params.some((p) => p.name === paramName)
}

function getActionLabel(t: (key: string) => string, name: string): string {
  const key = `game:${name}`
  const result = t(key)
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
  const [sayOpen, setSayOpen] = useState(false)
  const [sayText, setSayText] = useState("")
  const sayInputRef = useRef<HTMLInputElement>(null)

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

  // buy/sell always handled by TradePanel; use_item/equip/unequip handled by
  // InventoryPanel in peaceful mode, but must stay in ActionBar during combat
  // (sidebar switches to CombatPanel, InventoryPanel not visible)
  const ALWAYS_HIDDEN = new Set(["buy", "sell"])
  const PEACEFUL_ONLY_HIDDEN = new Set(["use_item", "equip", "unequip"])
  const available = (awareness?.available_actions ?? []).filter(
    (a) => !ALWAYS_HIDDEN.has(a.name) && !(mode === "peaceful" && PEACEFUL_ONLY_HIDDEN.has(a.name)),
  )
  const availableItems = awareness?.available_items ?? []
  const hasAction = (name: string) => available.some((a) => a.name === name)

  const isCombat = mode === "combat" && awareness && "self_hp" in awareness
  const enemies = isCombat ? (awareness as CombatAwareness).nearby : []

  const isDisabled = () => waitingForAction

  return (
    <div className="border-t border-border px-4 py-2">
      {budget && (
        <div className="mb-2">
          <BudgetDisplay budget={budget} />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {available.map((action) => {
          const { name } = action

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
              />
            )
          }

          // Has item_id param → item dropdown
          if (hasParam(action, "item_id") && availableItems.length > 0) {
            return (
              <ItemDropdown
                key={name}
                description={action.description}
                items={availableItems}
                disabled={isDisabled()}
                openDropdown={openDropdown}
                setOpenDropdown={setOpenDropdown}
                sendAction={sendAction}
                t={t}
              />
            )
          }

          // Has weapon_id param → weapon dropdown
          if (hasParam(action, "weapon_id")) {
            const weapons = availableItems.filter((i) => i.description.toLowerCase().includes("weapon"))
            if (weapons.length > 0) {
              return (
                <div key={name} className="relative">
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={isDisabled()}
                    title={action.description}
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
              variant={ACTION_VARIANT[name] ?? "secondary"}
              disabled={isDisabled()}
              title={action.description}
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
        })}

        {/* end_turn is always available even if not in the list */}
        {!hasAction("end_turn") && (
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
  description: string
}

interface TargetDropdownProps extends DropdownProps {
  name: string
  enemies: { id: string; distance_ft?: number }[]
}

function TargetDropdown({ name, description, enemies, disabled, openDropdown, setOpenDropdown, sendAction, t }: TargetDropdownProps) {
  return (
    <div className="relative">
      <Button
        size="sm"
        variant={ACTION_VARIANT[name] ?? "secondary"}
        disabled={disabled}
        title={description}
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

function DirectionalDropdown({ name, description, enemies, disabled, openDropdown, setOpenDropdown, sendAction, t }: DirectionalDropdownProps) {
  const towardKey = name === "dash" ? "game:dash_toward" : "game:move_toward"
  const awayKey = name === "dash" ? "game:dash_away" : "game:move_away"

  return (
    <div className="relative">
      <Button
        size="sm"
        variant="secondary"
        disabled={disabled}
        title={description}
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

interface ItemDropdownProps extends Omit<DropdownProps, "description"> {
  items: { id: string; name: string; description: string }[]
  description: string
}

function ItemDropdown({ items, description, disabled, openDropdown, setOpenDropdown, sendAction, t }: ItemDropdownProps) {
  return (
    <div className="relative">
      <Button
        size="sm"
        variant="secondary"
        disabled={disabled}
        title={description}
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
