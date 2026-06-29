import { useState } from "react"
import { Link } from "react-router"
import { useTranslation } from "react-i18next"
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { LanguageToggle } from "@/components/setup/LanguageToggle"
import { useGameStore } from "@/store/gameStore"
import { ROLES, type Role } from "@/store/slices/identitySlice"

export function LandingPage() {
  const { t } = useTranslation(["common", "master"])
  const setIdentity = useGameStore((s) => s.setIdentity)
  const storedUserId = useGameStore((s) => s.userId)
  const storedRole = useGameStore((s) => s.role)
  const [name, setName] = useState(storedUserId ?? "")
  const [role, setRole] = useState<Role>(storedRole ?? "player")

  function apply(nextName: string, nextRole: Role) {
    setName(nextName)
    setRole(nextRole)
    if (nextName.trim()) setIdentity(nextName.trim(), nextRole)
  }

  return (
    <div className="dark mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center bg-background px-4 text-foreground">
      <h1 className="mb-8 text-4xl font-bold">{t("common:app_title")}</h1>

      <div className="mb-6 flex w-full flex-col gap-2 sm:flex-row sm:items-center">
        <Input
          aria-label={t("common:identity_name_label")}
          placeholder={t("common:identity_name_placeholder")}
          value={name}
          onChange={(e) => apply(e.target.value, role)}
          className="sm:flex-1"
        />
        <select
          aria-label={t("common:identity_role_label")}
          value={role}
          onChange={(e) => apply(name, e.target.value as Role)}
          className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {t(`common:role_${r}`)}
            </option>
          ))}
        </select>
      </div>

      <div className="grid w-full gap-4 sm:grid-cols-2">
        <Link to="/play" className="no-underline">
          <Card className="cursor-pointer transition-colors hover:bg-muted/50">
            <CardHeader>
              <CardTitle>{t("common:play")}</CardTitle>
              <CardDescription>{t("common:play_description")}</CardDescription>
            </CardHeader>
          </Card>
        </Link>

        <Link to="/master" className="no-underline">
          <Card className="cursor-pointer transition-colors hover:bg-muted/50">
            <CardHeader>
              <CardTitle>{t("master:title")}</CardTitle>
              <CardDescription>{t("master:dm_description")}</CardDescription>
            </CardHeader>
          </Card>
        </Link>
      </div>

      <div className="mt-8">
        <LanguageToggle />
      </div>
    </div>
  )
}
