import { useState } from "react"
import { useTranslation } from "react-i18next"
import { toast } from "sonner"
import { api } from "@/transport/apiClient"
import type { GiveItemRequest } from "@/types/api"
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
import { Loader2 } from "lucide-react"

type ItemType = "weapon" | "potion"

interface Props {
  sessionId: string
  entityId: string
  onClose: () => void
  onGiven: () => void
}

export function GiveItemDialog({ sessionId, entityId, onClose, onGiven }: Props) {
  const { t } = useTranslation(["master", "common"])
  const [itemType, setItemType] = useState<ItemType>("weapon")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [name, setName] = useState("")

  // Weapon fields
  const [weaponId, setWeaponId] = useState("")
  const [attackName, setAttackName] = useState("")
  const [category, setCategory] = useState("simple")
  const [damageDice, setDamageDice] = useState("1d8")
  const [damageType, setDamageType] = useState("slashing")
  const [reach, setReach] = useState(5)
  const [isMagic, setIsMagic] = useState(false)
  const [isFinesse, setIsFinesse] = useState(false)

  // Potion fields
  const [healDice, setHealDice] = useState("2d4+2")

  const submit = () => {
    setSaving(true)
    setError(null)

    const data: GiveItemRequest = { name, type: itemType }

    if (itemType === "weapon") {
      data.weapon_id = weaponId || name.toLowerCase().replace(/\s+/g, "_")
      data.attack_name = attackName || name
      data.category = category
      data.damage = [{ dice: damageDice, type: damageType }]
      data.reach = reach
      data.is_magic = isMagic
      data.is_finesse = isFinesse
    } else {
      data.heal_dice = healDice
    }

    api.master
      .giveItem(sessionId, entityId, data)
      .then(() => {
        onGiven()
        toast.success(t("master:item_given"))
      })
      .catch((err) => setError(String(err.body?.detail ?? err.message)))
      .finally(() => setSaving(false))
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="sm:max-w-md max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t("master:give_item")}</DialogTitle>
        </DialogHeader>

        {error && (
          <div className="rounded border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <Label>{t("master:item_type")}</Label>
            <div className="flex gap-1 mt-1">
              {(["weapon", "potion"] as const).map((tp) => (
                <Button
                  key={tp}
                  size="sm"
                  variant={itemType === tp ? "default" : "outline"}
                  onClick={() => setItemType(tp)}
                  type="button"
                >
                  {t(`master:item_type_${tp}`)}
                </Button>
              ))}
            </div>
          </div>

          <div className="col-span-2">
            <Label>{t("master:field_name")}</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>

          {itemType === "weapon" && (
            <>
              <div>
                <Label>{t("master:weapon_id")}</Label>
                <Input
                  value={weaponId}
                  onChange={(e) => setWeaponId(e.target.value)}
                  placeholder={name.toLowerCase().replace(/\s+/g, "_")}
                />
              </div>
              <div>
                <Label>{t("master:weapon_attack_name")}</Label>
                <Input
                  value={attackName}
                  onChange={(e) => setAttackName(e.target.value)}
                  placeholder={name}
                />
              </div>
              <div>
                <Label>{t("master:weapon_category")}</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  <option value="simple">{t("master:weapon_simple")}</option>
                  <option value="martial">{t("master:weapon_martial")}</option>
                </select>
              </div>
              <div>
                <Label>{t("master:weapon_damage")}</Label>
                <Input value={damageDice} onChange={(e) => setDamageDice(e.target.value)} />
              </div>
              <div>
                <Label>{t("master:weapon_damage_type")}</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  value={damageType}
                  onChange={(e) => setDamageType(e.target.value)}
                >
                  {["slashing", "piercing", "bludgeoning", "fire", "cold", "lightning", "poison", "necrotic", "radiant"].map((dt) => (
                    <option key={dt} value={dt}>{dt}</option>
                  ))}
                </select>
              </div>
              <div>
                <Label>{t("master:weapon_reach")}</Label>
                <Input type="number" min={5} step={5} value={reach} onChange={(e) => setReach(parseInt(e.target.value) || 5)} />
              </div>
              <div className="flex items-end gap-3">
                <label className="flex items-center gap-1 text-sm">
                  <input type="checkbox" checked={isMagic} onChange={(e) => setIsMagic(e.target.checked)} />
                  {t("master:weapon_magic")}
                </label>
                <label className="flex items-center gap-1 text-sm">
                  <input type="checkbox" checked={isFinesse} onChange={(e) => setIsFinesse(e.target.checked)} />
                  {t("master:weapon_finesse")}
                </label>
              </div>
            </>
          )}

          {itemType === "potion" && (
            <div className="col-span-2">
              <Label>{t("master:potion_heal_dice")}</Label>
              <Input value={healDice} onChange={(e) => setHealDice(e.target.value)} />
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t("common:cancel")}</Button>
          <Button onClick={submit} disabled={saving || !name}>
            {saving && <Loader2 className="mr-1 size-3 animate-spin" />}
            {t("master:give_item")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
