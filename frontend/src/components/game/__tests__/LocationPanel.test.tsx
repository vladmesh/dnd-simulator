import { act, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import "@/i18n"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import type { LocationData, PlayerStatus } from "@/types/game"
import { LocationPanel } from "../LocationPanel"

vi.mock("@/transport/wsClient", () => ({
  wsClient: {
    send: vi.fn(),
    onStatus: vi.fn(),
    onMessage: vi.fn(),
    getStatus: vi.fn(() => "disconnected"),
    connect: vi.fn(),
    disconnect: vi.fn(),
  },
}))

const sendMock = wsClient.send as unknown as ReturnType<typeof vi.fn>

const location: LocationData = {
  current_location: "Old Road",
  current_location_id: "road",
  description: "A dusty road",
  region_id: "r",
  paths: [{ target_id: "bridge", target_name: "Stone Bridge", distance_m: 500 }],
}

const player: PlayerStatus = {
  player_id: "p1",
  name: "Hero",
  race: "human",
  char_class: "fighter",
  level: 1,
  experience: 0,
  level_up_available: false,
  xp_to_next_level: 300,
  alignment: "neutral",
  hp: 10,
  max_hp: 10,
  ac: 12,
  gold: 0,
  location_id: "road",
  ability_scores: { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 },
}

beforeEach(() => {
  sendMock.mockReset()
  useGameStore.setState({ location, player, isMyTurn: true, waitingForAction: false })
})

describe("LocationPanel journey", () => {
  it("starts first-class travel instead of a zero-hour wait", async () => {
    render(<LocationPanel />)

    await userEvent.click(screen.getByRole("button", { name: /Stone Bridge/i }))

    expect(sendMock).toHaveBeenCalledWith({
      type: "action",
      name: "travel",
      params: { destination_id: "bridge" },
    })
  })

  it("shows persisted route progress and clears it on arrival status", () => {
    useGameStore.setState({
      player: {
        ...player,
        journey: {
          destination_id: "keep",
          destination_name: "Hill Keep",
          current_location_name: "Old Road",
          next_location_name: "Stone Bridge",
          remaining_route: ["Stone Bridge", "Hill Keep"],
          next_arrival_seconds: 460,
        },
      },
    })
    render(<LocationPanel />)
    expect(screen.getByText(/Old Road.*Stone Bridge.*Hill Keep/)).toBeInTheDocument()

    act(() => {
      useGameStore.setState({
        player: { ...player, location_id: "keep" },
        location: { ...location, current_location: "Hill Keep", current_location_id: "keep" },
      })
    })

    expect(screen.queryByText(/Old Road.*Stone Bridge.*Hill Keep/)).not.toBeInTheDocument()
    expect(screen.getByText("Hill Keep")).toBeInTheDocument()
  })
})
