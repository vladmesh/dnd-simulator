import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import { Button } from "@/components/ui/button"
import { MapPin } from "lucide-react"

export function LocationPanel() {
  const { t } = useTranslation(["game"])
  const location = useGameStore((s) => s.location)
  const journey = useGameStore((s) => s.player?.journey)
  const isMyTurn = useGameStore((s) => s.isMyTurn)

  if (!location) return null

  const sendGo = (locationId: string) => {
    wsClient.send({ type: "action", name: "travel", params: { destination_id: locationId } })
    useGameStore.getState().setWaitingForAction(true)
  }

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-medium uppercase text-muted-foreground">{t("game:location")}</h3>
      <div className="space-y-1">
        <div className="flex items-center gap-1 text-sm font-medium">
          <MapPin className="size-3.5" />
          {location.current_location}
        </div>
        {location.description && (
          <p className="text-xs text-muted-foreground">{location.description}</p>
        )}
      </div>
      {journey && (
        <div className="space-y-1 text-xs" data-testid="journey-status">
          <p className="font-medium">{t("game:journey_to", { destination: journey.destination_name })}</p>
          <p className="text-muted-foreground">
            {t("game:journey_route", {
              route: [journey.current_location_name, ...journey.remaining_route].join(" → "),
            })}
          </p>
        </div>
      )}
      {location.paths.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">{t("game:paths")}</p>
          <div className="flex flex-col gap-1">
            {location.paths.map((p) => (
              <Button
                key={p.target_id}
                size="xs"
                variant="outline"
                className="justify-start text-xs"
                disabled={!isMyTurn}
                onClick={() => sendGo(p.target_id)}
              >
                {p.target_name}
                <span className="ml-auto text-muted-foreground">{p.distance_m}m</span>
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
