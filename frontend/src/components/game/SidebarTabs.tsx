import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { Perception } from "./Perception"
import { LocationPanel } from "./LocationPanel"
import { PlayerStats } from "./PlayerStats"
import { BattleMap } from "./BattleMap"
import { CombatPanel } from "./CombatPanel"
import { TradePanel } from "./TradePanel"

type PeacefulTab = "nearby" | "location" | "character"
type CombatTab = "map" | "nearby" | "character"

const PEACEFUL_TABS: { key: PeacefulTab; label: string }[] = [
  { key: "nearby", label: "game:nearby" },
  { key: "location", label: "game:location" },
  { key: "character", label: "game:character" },
]

const COMBAT_TABS: { key: CombatTab; label: string }[] = [
  { key: "map", label: "game:battle_map" },
  { key: "nearby", label: "game:nearby" },
  { key: "character", label: "game:character" },
]

export function SidebarTabs() {
  const { t } = useTranslation(["game"])
  const mode = useGameStore((s) => s.mode)
  const isCombat = mode === "combat"

  const [peacefulTab, setPeacefulTab] = useState<PeacefulTab>("nearby")
  const [combatTab, setCombatTab] = useState<CombatTab>("map")

  // Auto-reset to default tab when mode changes
  useEffect(() => {
    if (isCombat) {
      setCombatTab("map")
    } else {
      setPeacefulTab("nearby")
    }
  }, [isCombat])

  const tabs = isCombat ? COMBAT_TABS : PEACEFUL_TABS
  const activeTab = isCombat ? combatTab : peacefulTab
  const setTab = isCombat
    ? (key: string) => setCombatTab(key as CombatTab)
    : (key: string) => setPeacefulTab(key as PeacefulTab)

  return (
    <>
      {/* Tab bar */}
      <div className="flex border-b border-border" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={activeTab === tab.key}
            className={`flex-1 px-2 py-1.5 text-xs uppercase transition-colors ${
              activeTab === tab.key
                ? "border-b-2 border-primary text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setTab(tab.key)}
          >
            {t(tab.label)}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-3">
        {isCombat ? (
          <>
            {combatTab === "map" && (
              <>
                <BattleMap />
                <div className="my-3 border-t border-border" />
                <CombatPanel />
              </>
            )}
            {combatTab === "nearby" && <Perception />}
            {combatTab === "character" && <PlayerStats />}
          </>
        ) : (
          <>
            {peacefulTab === "nearby" && (
              <>
                <Perception />
                <div className="my-3 border-t border-border" />
                <TradePanel />
              </>
            )}
            {peacefulTab === "location" && <LocationPanel />}
            {peacefulTab === "character" && <PlayerStats />}
          </>
        )}
      </div>
    </>
  )
}
