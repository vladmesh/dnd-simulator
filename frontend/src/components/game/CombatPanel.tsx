import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import type { CombatAwareness, ResourcePoolInfo } from "@/types/game"

export function CombatPanel() {
  const { t } = useTranslation(["game"])
  const awareness = useGameStore((s) => s.awareness)

  if (!awareness || !("self_hp" in awareness)) return null
  const combat = awareness as CombatAwareness

  const hpPct = combat.self_max_hp > 0 ? (combat.self_hp / combat.self_max_hp) * 100 : 0
  const hpColor = hpPct > 50 ? "bg-green-500" : hpPct > 25 ? "bg-yellow-500" : "bg-red-500"

  // Filter spell slot pools (id starts with "spell_slot_")
  const spellSlots = (combat.self_resource_pools ?? []).filter((p) => p.id.startsWith("spell_slot_"))

  return (
    <div className="space-y-3">
      {/* Round indicator */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-medium uppercase text-muted-foreground">
          {t("game:combat_info")}
        </h3>
        <span className="rounded bg-red-500/20 px-2 py-0.5 text-xs font-medium text-red-400">
          {t("game:round", { n: combat.round_number })}
        </span>
      </div>

      {/* Self stats */}
      <div className="space-y-1 rounded border border-border p-2 text-xs">
        <p className="font-medium">{t("game:self_stats")}</p>
        {/* HP bar */}
        <div className="relative h-3 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={`absolute inset-y-0 left-0 transition-all ${hpColor}`}
            style={{ width: `${hpPct}%` }}
          />
          <span className="absolute inset-0 flex items-center justify-center text-[10px] font-medium">
            {t("game:hp_display", { hp: combat.self_hp, max: combat.self_max_hp })}
          </span>
        </div>
        <div className="flex flex-wrap gap-x-3 text-muted-foreground">
          <span>{t("game:ac_display", { n: combat.self_ac })}</span>
          <span>{t("game:speed_display", { n: combat.self_speed })}</span>
        </div>
        {combat.self_conditions && combat.self_conditions.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {combat.self_conditions.map((c) => (
              <span key={c} className="rounded bg-orange-500/20 px-1.5 py-0.5 text-[10px] font-medium text-orange-400">
                {c}
              </span>
            ))}
          </div>
        )}
        <p className="text-muted-foreground">
          {t("game:weapon_display", { name: combat.self_weapon, damage: combat.self_weapon_damage })}
        </p>
      </div>

      {/* Spell slots */}
      {spellSlots.length > 0 && (
        <div className="space-y-1 rounded border border-border p-2 text-xs">
          <p className="font-medium">{t("game:spell_slots")}</p>
          {spellSlots.map((pool) => (
            <SpellSlotRow key={pool.id} pool={pool} />
          ))}
        </div>
      )}
    </div>
  )
}

function SpellSlotRow({ pool }: { pool: ResourcePoolInfo }) {
  const { t } = useTranslation(["game"])
  const level = pool.id.replace("spell_slot_", "")

  return (
    <div className="flex items-center gap-2">
      <span className="w-8 text-muted-foreground">{t("game:spell_slot_level", { level })}</span>
      <div className="flex gap-0.5">
        {Array.from({ length: pool.max_uses }, (_, i) => (
          <div
            key={i}
            className={`h-3 w-3 rounded-full border ${
              i < pool.current_uses
                ? "border-amber-400 bg-amber-400"
                : "border-muted-foreground/40 bg-transparent"
            }`}
          />
        ))}
      </div>
    </div>
  )
}
