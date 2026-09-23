import { useTranslation } from "react-i18next"
import { Button } from "@/components/ui/button"
import { Languages } from "lucide-react"

const LANGS = [
  { code: "en", label: "EN" },
  { code: "ru", label: "RU" },
] as const

/** Switches the UI language; an open game session follows it (see GameScreen). */
export function LanguageToggle() {
  const { i18n } = useTranslation()

  async function changeLanguage(lang: "en" | "ru") {
    await i18n.changeLanguage(lang)
  }

  return (
    <div className="flex items-center gap-1">
      <Languages className="size-4 text-muted-foreground" />
      {LANGS.map((lang) => (
        <Button
          key={lang.code}
          size="xs"
          variant={i18n.language === lang.code ? "default" : "ghost"}
          onClick={() => void changeLanguage(lang.code)}
        >
          {lang.label}
        </Button>
      ))}
    </div>
  )
}
