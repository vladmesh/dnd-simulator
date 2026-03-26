import { useState } from "react"
import { useNavigate } from "react-router"
import { useTranslation } from "react-i18next"
import { WorldPicker } from "./WorldPicker"
import { WorldBuilder } from "./WorldBuilder"
import { CharacterForm } from "./CharacterForm"
import { SessionConnect } from "./SessionConnect"
import { LanguageToggle } from "./LanguageToggle"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

type Step = "pick-world" | "build-world" | "create-character"

export function SetupScreen() {
  const navigate = useNavigate()
  const { t } = useTranslation(["setup", "common"])
  const [step, setStep] = useState<Step>("pick-world")
  const [sessionId, setSessionId] = useState<string | null>(null)

  const goToGame = (sid: string, playerId?: string) => {
    if (playerId) {
      localStorage.setItem(`player_id:${sid}`, playerId)
    }
    navigate(`/play/${sid}`)
  }

  return (
    <div className="dark mx-auto min-h-screen max-w-2xl bg-background px-4 py-8 text-foreground">
      <div className="mb-8 flex items-center justify-center gap-4">
        <h1 className="text-3xl font-bold">{t("common:app_title")}</h1>
        {step === "pick-world" && <LanguageToggle />}
      </div>

      {step === "pick-world" && (
        <>
          <h2 className="mb-4 text-lg font-medium">{t("setup:choose_world")}</h2>
          <WorldPicker
            onWorldSelected={(sid) => {
              setSessionId(sid)
              setStep("create-character")
            }}
          />

          <div className="mt-8">
            <Button
              variant="outline"
              className="w-full"
              onClick={() => setStep("build-world")}
            >
              {t("setup:build_custom_world")}
            </Button>
          </div>

          <div className="mt-8">
            <Card>
              <CardHeader>
                <CardTitle>{t("setup:join_existing")}</CardTitle>
              </CardHeader>
              <CardContent>
                <SessionConnect onConnect={goToGame} />
              </CardContent>
            </Card>
          </div>
        </>
      )}

      {step === "build-world" && (
        <WorldBuilder
          onWorldAssembled={(sid) => {
            setSessionId(sid)
            setStep("create-character")
          }}
          onBack={() => setStep("pick-world")}
        />
      )}

      {step === "create-character" && sessionId && (
        <>
          <h2 className="mb-4 text-lg font-medium">{t("setup:create_character")}</h2>
          <Card>
            <CardContent className="pt-4">
              <CharacterForm sessionId={sessionId} onCreated={(playerId) => goToGame(sessionId, playerId)} />
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
