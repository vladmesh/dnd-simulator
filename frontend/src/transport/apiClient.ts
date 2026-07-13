import { get } from "@/transport/requestCore"
import { masterContentClient } from "@/transport/masterContentClient"
import { masterCreatureClient } from "@/transport/masterCreatureClient"
import { masterSessionClient } from "@/transport/masterSessionClient"
import { masterWorldClient } from "@/transport/masterWorldClient"
import { playerClient } from "@/transport/playerClient"

export { ApiError } from "@/transport/requestCore"

const master = {
  ...masterWorldClient,
  ...masterSessionClient,
  ...masterCreatureClient,
  ...masterContentClient,
}

export const api = {
  master,
  player: playerClient,
  health: () => get<{ status: string }>("/health"),
}
