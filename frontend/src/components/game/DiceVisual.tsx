import { cn } from "@/lib/utils"

// ---------------------------------------------------------------------------
// Damage type → color mapping
// ---------------------------------------------------------------------------

const DAMAGE_TYPE_COLORS: Record<string, string> = {
  slashing: "border-red-500/60 bg-red-950/40 text-red-300",
  bludgeoning: "border-orange-500/60 bg-orange-950/40 text-orange-300",
  piercing: "border-gray-400/60 bg-gray-900/40 text-gray-300",
  fire: "border-orange-400/60 bg-orange-950/40 text-orange-200",
  cold: "border-blue-400/60 bg-blue-950/40 text-blue-200",
  lightning: "border-yellow-400/60 bg-yellow-950/40 text-yellow-200",
  thunder: "border-purple-400/60 bg-purple-950/40 text-purple-200",
  poison: "border-green-500/60 bg-green-950/40 text-green-300",
  acid: "border-lime-500/60 bg-lime-950/40 text-lime-300",
  necrotic: "border-violet-500/60 bg-violet-950/40 text-violet-300",
  radiant: "border-amber-300/60 bg-amber-950/40 text-amber-200",
  force: "border-indigo-400/60 bg-indigo-950/40 text-indigo-200",
  psychic: "border-pink-400/60 bg-pink-950/40 text-pink-200",
}

const DEFAULT_DIE_COLOR = "border-border bg-muted text-foreground"

// ---------------------------------------------------------------------------
// DieVisual — a single styled die face
// ---------------------------------------------------------------------------

interface DieVisualProps {
  sides: number
  result: number
  original?: number | null
  critical?: boolean
  dropped?: boolean
  damageType?: string
}

export function DieVisual({
  sides,
  result,
  original,
  critical,
  dropped,
  damageType,
}: DieVisualProps) {
  const isD20 = sides === 20
  const sizeClass = isD20 ? "w-10 h-10 text-base" : "w-7 h-7 text-xs"
  const colorClass = damageType ? (DAMAGE_TYPE_COLORS[damageType] ?? DEFAULT_DIE_COLOR) : DEFAULT_DIE_COLOR

  if (original != null) {
    // Reroll: show original (dimmed) → arrow → new result
    return (
      <span className="inline-flex items-center gap-1">
        <span
          data-testid="die-original"
          className={cn(
            "inline-flex items-center justify-center rounded border font-mono font-bold opacity-40 line-through",
            sizeClass,
            colorClass,
          )}
        >
          {original}
        </span>
        <span className="text-muted-foreground">→</span>
        <span
          data-testid={`die-d${sides}`}
          className={cn(
            "inline-flex items-center justify-center rounded border font-mono font-bold shadow-sm",
            sizeClass,
            colorClass,
          )}
        >
          {result}
        </span>
      </span>
    )
  }

  return (
    <span
      data-testid={`die-d${sides}`}
      className={cn(
        "inline-flex items-center justify-center rounded border font-mono font-bold shadow-sm",
        sizeClass,
        colorClass,
        critical && "ring-2 ring-amber-400 border-amber-400",
        dropped && "opacity-40 line-through",
      )}
    >
      {result}
    </span>
  )
}
