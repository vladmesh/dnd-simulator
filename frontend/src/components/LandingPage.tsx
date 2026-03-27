import { Link } from "react-router"
import { useTranslation } from "react-i18next"
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { LanguageToggle } from "@/components/setup/LanguageToggle"

export function LandingPage() {
  const { t } = useTranslation(["common", "master"])

  return (
    <div className="dark mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center bg-background px-4 text-foreground">
      <h1 className="mb-8 text-4xl font-bold">{t("common:app_title")}</h1>

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
