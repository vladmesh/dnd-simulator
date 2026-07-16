import { useTranslation } from "react-i18next"
import type { TFunction } from "i18next"
import { cn } from "@/lib/utils"
import type { ItemProps } from "@/types/game"

interface ItemLike {
  props?: ItemProps | null
  description?: string
  price?: number | null
}

function formatModifier(t: TFunction, m: { stat: string; op: string; value: number }): string {
  const stat = t(`game:stat_${m.stat}`, { defaultValue: m.stat })
  if (m.op === "add") return `${m.value > 0 ? "+" : ""}${m.value} ${stat}`
  if (m.op === "override") return `${stat} = ${m.value}`
  return `${stat}: ${t(`game:${m.op}`, { defaultValue: m.op })}`
}

function detailLines(t: TFunction, props: ItemProps | null | undefined): string[] {
  if (!props) return []
  switch (props.kind) {
    case "weapon": {
      const dmg = props.damage
        .map((d) => `${d.dice} ${t(`game:dmg_${d.type}`, { defaultValue: d.type })}`)
        .join(" + ")
      const lines = [
        `${t("game:damage")}: ${dmg}${props.modifier ? ` +${props.modifier}` : ""}`,
        t("game:item_reach", { ft: props.reach }),
        t(`game:wpn_cat_${props.category}`, { defaultValue: props.category }),
      ]
      if (props.ability) {
        lines.push(
          t("game:item_ability", {
            ability: t(`game:source_${props.ability}`, { defaultValue: props.ability.toUpperCase() }),
          }),
        )
      }
      const flags: string[] = []
      if (props.is_finesse) flags.push(t("game:prop_finesse"))
      if (props.is_two_handed) flags.push(t("game:prop_two_handed"))
      if (props.is_light) flags.push(t("game:prop_light"))
      if (props.is_heavy) flags.push(t("game:prop_heavy"))
      if (props.is_magic) flags.push(t("game:prop_magic"))
      if (flags.length > 0) lines.push(flags.join(", "))
      for (const c of props.conditions ?? []) {
        lines.push(t(`game:condition_${c}`, { defaultValue: c }))
      }
      return lines
    }
    case "armor": {
      const lines = [t("game:item_base_ac", { n: props.base_ac })]
      if (props.max_dex_bonus != null) lines.push(t("game:item_max_dex", { n: props.max_dex_bonus }))
      lines.push(t(`game:armor_cat_${props.category}`, { defaultValue: props.category }))
      return lines
    }
    case "shield":
      return [`+${props.ac_bonus} ${t("game:stat_ac")}`]
    case "accessory": {
      const lines = [t(`game:slot_${props.slot}`, { defaultValue: props.slot })]
      for (const m of props.modifiers) lines.push(formatModifier(t, m))
      return lines
    }
    case "potion":
      return [t("game:item_heals", { dice: props.heal_dice })]
  }
}

/**
 * CSS-hover details card around an item name. Content is always in the DOM
 * (hidden via `invisible`), so tests can assert on it without hover simulation.
 * The card uses `fixed` with auto offsets: it renders at its static position
 * (under the item row) but is positioned against the viewport, so the
 * `overflow-y-auto` panel columns don't clip it.
 */
export function ItemDetails({
  item,
  align = "left",
  hint,
  className,
  children,
}: {
  item: ItemLike
  align?: "left" | "right"
  hint?: string
  className?: string
  children: React.ReactNode
}) {
  const { t } = useTranslation(["game"])
  const lines = detailLines(t, item.props)

  return (
    <span className={cn("group/item relative", className)}>
      {children}
      <span
        className={cn(
          "invisible fixed z-50 mt-1 block w-max max-w-52 space-y-0.5 rounded border border-border bg-popover p-2",
          "text-left text-[11px] font-normal normal-case text-popover-foreground shadow-md",
          "pointer-events-none group-hover/item:visible",
          align === "right" && "-translate-x-1/2",
        )}
      >
        {lines.length > 0 ? (
          lines.map((line, i) => (
            <span key={i} className="block">
              {line}
            </span>
          ))
        ) : item.description ? (
          <span className="block">{item.description}</span>
        ) : null}
        {item.price != null && (
          <span className="block text-muted-foreground">{t("game:item_price", { n: item.price })}</span>
        )}
        {hint && <span className="block text-muted-foreground">{hint}</span>}
      </span>
    </span>
  )
}
