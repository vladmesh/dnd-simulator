import type { AttackRollData, DamageComponentData, DieRollData } from "@/types/game"

// ---------------------------------------------------------------------------
// Type guards for untyped event data
// ---------------------------------------------------------------------------

function isAttackRollData(v: unknown): v is AttackRollData {
  if (typeof v !== "object" || v === null) return false
  const o = v as Record<string, unknown>
  return typeof o.natural === "number" && typeof o.total === "number" && o.d20 != null
}

function isDamageComponentArray(v: unknown): v is DamageComponentData[] {
  return Array.isArray(v) && v.every((c) => typeof c === "object" && c !== null && "source" in c)
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function DieDisplay({ die }: { die: DieRollData }) {
  if (die.original != null) {
    return (
      <span className="font-mono">
        <span className="line-through opacity-50">{die.original}</span>→{die.result}
      </span>
    )
  }
  return <span className="font-mono">[{die.result}]</span>
}

function AttackRollSection({ roll, ac, hit, critical }: {
  roll: AttackRollData
  ac: number
  hit: boolean
  critical: boolean
}) {
  const verdict = critical ? "CRIT" : hit ? "HIT" : "MISS"
  const verdictColor = hit ? "text-green-400" : "text-red-400"

  return (
    <div className="space-y-0.5">
      {/* d20 line */}
      <div className="flex flex-wrap items-center gap-1">
        <span className="text-muted-foreground">d20:</span>
        <span className="font-mono font-bold">[{roll.natural}]</span>
        {roll.components.map((c, i) => (
          <span key={i} className="text-muted-foreground">
            {c.value >= 0 ? "+" : ""}{c.value} <span className="text-[10px] italic">{c.source}</span>
          </span>
        ))}
        <span className="text-muted-foreground">=</span>
        <span className="font-bold">{roll.total}</span>
        <span className="text-muted-foreground">vs AC {ac}</span>
        <span className={`font-bold ${verdictColor}`}>{verdict}</span>
      </div>

      {/* Advantage/disadvantage line */}
      {(roll.advantage || roll.disadvantage) && roll.d20_alt && (
        <div className="ml-4 text-[10px] text-muted-foreground">
          ({roll.advantage ? "advantage" : "disadvantage"}: kept {roll.natural}, dropped {roll.d20_alt.result})
        </div>
      )}
    </div>
  )
}

function DamageSection({ components, total }: {
  components: DamageComponentData[]
  total?: number
}) {
  return (
    <div className="space-y-0.5">
      <div className="flex items-center gap-1">
        <span className="text-muted-foreground">Damage:</span>
        {total != null && <span className="font-bold">{total}</span>}
      </div>
      {components.map((comp, i) => (
        <div key={i} className="ml-4 flex flex-wrap items-center gap-1 text-[10px]">
          {comp.dice ? (
            <span className="text-muted-foreground">{comp.dice} {comp.type}</span>
          ) : (
            <span className="text-muted-foreground">+{comp.amount}</span>
          )}
          {comp.dice_detail && comp.dice_detail.length > 0 && (
            <span>
              {comp.dice_detail.map((die, j) => (
                <span key={j} className="mx-0.5">
                  <DieDisplay die={die} />
                </span>
              ))}
            </span>
          )}
          <span className="italic text-muted-foreground/70">{comp.source}</span>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main breakdown component
// ---------------------------------------------------------------------------

export function RollBreakdown({ data }: { data: Record<string, unknown> }) {
  const attackRoll = data.attack_roll
  if (!isAttackRollData(attackRoll)) return null

  const ac = typeof data.ac === "number" ? data.ac : 0
  const hit = data.hit === true
  const critical = data.critical === true
  const damageComponents = isDamageComponentArray(data.damage_components)
    ? data.damage_components
    : undefined
  const totalDamage = typeof data.damage === "number" ? data.damage : undefined

  return (
    <div
      data-testid="roll-breakdown"
      className="ml-6 mt-0.5 space-y-1 border-l border-border/30 pl-2 text-[11px]"
    >
      <AttackRollSection roll={attackRoll} ac={ac} hit={hit} critical={critical} />
      {hit && damageComponents && damageComponents.length > 0 && (
        <DamageSection components={damageComponents} total={totalDamage} />
      )}
    </div>
  )
}
