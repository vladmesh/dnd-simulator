import { useState } from "react"
import { useTranslation } from "react-i18next"
import { toast } from "sonner"
import { api, ApiError } from "@/transport/apiClient"
import type { CreatureResponse } from "@/types/api"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Loader2, Package } from "lucide-react"
import { GiveItemDialog } from "./GiveItemDialog"

interface Props {
  sessionId: string
  creature: CreatureResponse | null // null = spawn new
  onClose: () => void
  onSaved: () => void
}

const NPC_ROLES = [
  "commoner",
  "blacksmith",
  "tavern_keeper",
  "guard",
  "merchant",
  "farmer",
  "gladiator",
] as const

export function CreatureForm({ sessionId, creature, onClose, onSaved }: Props) {
  const { t } = useTranslation(["master", "common", "game"])
  const isEdit = creature !== null

  const ALL_CONDITIONS = [
    "blinded", "charmed", "deafened", "frightened", "grappled",
    "incapacitated", "invisible", "paralyzed", "petrified", "poisoned",
    "prone", "restrained", "stunned", "unconscious",
  ]

  const [form, setForm] = useState({
    id: creature?.id ?? "",
    name: creature?.name ?? "",
    entity_type: creature?.entity_type ?? "npc",
    current_hp: creature?.hp ?? 10,
    max_hp: creature?.max_hp ?? 10,
    ac: creature?.ac ?? 10,
    speed: 30,
    start_location: creature?.location_id ?? "",
    role: creature?.role ?? "commoner",
    personality: creature?.personality ?? "",
    settlement_id: creature?.settlement_id ?? "",
    ai: creature?.ai_type ?? "rule_based",
    gold: creature?.gold ?? 0,
    conditions: creature?.conditions ?? [],
  })

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showGiveItem, setShowGiveItem] = useState(false)
  const [liveCreature, setLiveCreature] = useState(creature)

  const set = (field: string, value: string | number) =>
    setForm((f) => ({ ...f, [field]: value }))

  const submit = () => {
    setSaving(true)
    setError(null)

    const promise = isEdit
      ? api.master.patchCreature(sessionId, creature.id, {
          current_hp: form.current_hp,
          max_hp: form.max_hp,
          ac: form.ac,
          location_id: form.start_location || null,
          gold: form.gold,
          personality: form.personality || null,
          conditions: form.conditions,
        })
      : api.master.spawnCreature(sessionId, {
          id: form.id,
          name: form.name,
          entity_type: form.entity_type,
          hp: form.current_hp,
          ac: form.ac,
          speed: form.speed,
          start_location: form.start_location,
          role: form.role,
          personality: form.personality,
          settlement_id: form.settlement_id,
          ai: form.ai,
        })

    promise
      .then(() => {
        onSaved()
        toast.success(isEdit ? t("master:creature_updated") : t("master:creature_spawned"))
      })
      .catch((err) => {
          setError(err instanceof ApiError ? err.detailMessage() : String(err?.message ?? err))
        })
      .finally(() => setSaving(false))
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="sm:max-w-md max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? t("master:edit_creature") : t("master:spawn_creature")}
          </DialogTitle>
        </DialogHeader>

        {error && (
          <div className="rounded border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          {!isEdit && (
            <>
              <div>
                <Label>{t("master:field_id")}</Label>
                <Input value={form.id} onChange={(e) => set("id", e.target.value)} />
              </div>
              <div>
                <Label>{t("master:field_entity_type")}</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  value={form.entity_type}
                  onChange={(e) => set("entity_type", e.target.value)}
                >
                  <option value="npc">{t("master:filter_npc")}</option>
                  <option value="monster">{t("master:filter_monster")}</option>
                </select>
              </div>
            </>
          )}

          <div className={isEdit ? "col-span-2" : ""}>
            <Label>{t("master:field_name")}</Label>
            <Input value={form.name} onChange={(e) => set("name", e.target.value)} disabled={isEdit} />
          </div>

          <div>
            <Label htmlFor="current_hp">{t("master:field_current_hp")}</Label>
            <Input id="current_hp" type="number" min={0} max={999} value={form.current_hp} onChange={(e) => set("current_hp", parseInt(e.target.value) || 0)} />
          </div>
          {isEdit && (
            <div>
              <Label htmlFor="max_hp">{t("master:field_max_hp")}</Label>
              <Input id="max_hp" type="number" min={1} max={999} value={form.max_hp} onChange={(e) => set("max_hp", parseInt(e.target.value) || 1)} />
            </div>
          )}
          <div>
            <Label>{t("master:field_ac")}</Label>
            <Input type="number" min={0} max={30} value={form.ac} onChange={(e) => set("ac", parseInt(e.target.value) || 0)} />
          </div>

          {!isEdit && (
            <div>
              <Label>{t("master:field_speed")}</Label>
              <Input type="number" min={0} value={form.speed} onChange={(e) => set("speed", parseInt(e.target.value) || 0)} />
            </div>
          )}

          <div>
            <Label>{t("master:field_location")}</Label>
            <Input value={form.start_location} onChange={(e) => set("start_location", e.target.value)} />
          </div>

          {!isEdit && (
            <div>
              <Label>{t("master:field_ai")}</Label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                value={form.ai}
                onChange={(e) => set("ai", e.target.value)}
              >
                <option value="rule_based">{t("master:brain_rule")}</option>
                <option value="llm">{t("master:brain_llm")}</option>
              </select>
            </div>
          )}

          <div>
            <Label>{t("master:field_gold")}</Label>
            <Input type="number" min={0} value={form.gold} onChange={(e) => set("gold", parseInt(e.target.value) || 0)} />
          </div>

          <div className="col-span-2">
            <Label htmlFor="creature-role">{t("master:field_role")}</Label>
            <select
              id="creature-role"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm disabled:cursor-not-allowed disabled:opacity-50"
              value={form.role}
              onChange={(e) => set("role", e.target.value)}
              disabled={isEdit}
            >
              {NPC_ROLES.map((role) => (
                <option key={role} value={role}>{t(`game:role_${role}`)}</option>
              ))}
            </select>
          </div>
          <div className="col-span-2">
            <Label>{t("master:field_personality")}</Label>
            <Input value={form.personality} onChange={(e) => set("personality", e.target.value)} />
          </div>

          {!isEdit && (
            <div className="col-span-2">
              <Label>{t("master:field_settlement")}</Label>
              <Input value={form.settlement_id} onChange={(e) => set("settlement_id", e.target.value)} />
            </div>
          )}

          {isEdit && (
            <div className="col-span-2">
              <Label>{t("master:field_conditions")}</Label>
              <div className="flex flex-wrap gap-1 mt-1">
                {ALL_CONDITIONS.map((c) => {
                  const active = form.conditions.includes(c)
                  return (
                    <button
                      key={c}
                      type="button"
                      className={`rounded px-2 py-0.5 text-xs font-medium transition-colors ${
                        active
                          ? "bg-orange-500/30 text-orange-300 border border-orange-500/50"
                          : "bg-muted text-muted-foreground border border-transparent hover:bg-muted/80"
                      }`}
                      onClick={() =>
                        setForm((f) => ({
                          ...f,
                          conditions: active
                            ? f.conditions.filter((x) => x !== c)
                            : [...f.conditions, c],
                        }))
                      }
                    >
                      {t(`master:cond_${c}`)}
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {isEdit && (
          <div className="col-span-2 border-t border-border pt-3 mt-1">
            <div className="flex items-center justify-between mb-2">
              <Label className="text-sm font-medium">{t("master:inventory")}</Label>
              <Button size="xs" variant="outline" onClick={() => setShowGiveItem(true)}>
                <Package className="mr-1 size-3" />
                {t("master:give_item")}
              </Button>
            </div>

            {liveCreature?.equipped_weapon && (
              <div className="mb-2 text-sm">
                <span className="text-muted-foreground">{t("master:equipped_weapon")}:</span>{" "}
                <Badge variant="secondary">
                  {liveCreature.equipped_weapon.attack_name} ({liveCreature.equipped_weapon.damage})
                </Badge>
              </div>
            )}

            {liveCreature?.inventory && liveCreature.inventory.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {liveCreature.inventory.map((item) => (
                  <Badge key={item.id} variant="outline">
                    {item.name}
                    <span className="ml-1 text-muted-foreground text-xs">{item.item_type}</span>
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">{t("master:no_items")}</p>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t("common:cancel")}</Button>
          <Button onClick={submit} disabled={saving || (!isEdit && !form.id)}>
            {saving && <Loader2 className="mr-1 size-3 animate-spin" />}
            {isEdit ? t("common:save") : t("master:spawn_creature")}
          </Button>
        </DialogFooter>
      </DialogContent>

      {showGiveItem && creature && (
        <GiveItemDialog
          sessionId={sessionId}
          entityId={creature.id}
          onClose={() => setShowGiveItem(false)}
          onGiven={() => {
            setShowGiveItem(false)
            api.master.getCreature(sessionId, creature.id).then(setLiveCreature)
          }}
        />
      )}
    </Dialog>
  )
}
