import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { api } from "@/transport/apiClient"
import type { WorldListItem } from "@/types/api"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Loader2 } from "lucide-react"

interface Props {
  onWorldSelected: (worldId: string) => void
}

export function WorldPicker({ onWorldSelected }: Props) {
  const { t, i18n } = useTranslation(["setup", "common"])
  const [worlds, setWorlds] = useState<WorldListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    api.master
      .getWorlds(i18n.language)
      .then(setWorlds)
      .catch(() => setError(t("setup:load_worlds_error")))
      .finally(() => setLoading(false))
  }, [i18n.language, t])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return <div className="py-8 text-center text-sm text-destructive">{error}</div>
  }

  if (worlds.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        {t("setup:no_worlds")}
      </div>
    )
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {worlds.map((world) => (
        <Card key={world.id} className="cursor-pointer transition-colors hover:bg-accent/50">
          <CardHeader>
            <CardTitle>{world.name}</CardTitle>
            <CardDescription>{world.description || world.id}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              size="sm"
              disabled={creating !== null}
              onClick={() => {
                setCreating(world.id)
                setError(null)
                api.master
                  .createSession({ world_name: world.id, lang: i18n.language })
                  .then((res) => onWorldSelected(res.session_id))
                  .catch(() => {
                    setError(t("setup:create_session_error"))
                    setCreating(null)
                  })
              }}
            >
              {creating === world.id && <Loader2 className="mr-1 size-3 animate-spin" />}
              {t("setup:new_session")}
            </Button>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
