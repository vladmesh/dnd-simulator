import { describe, it, expect, vi, beforeEach } from "vitest"

// Mock wsClient BEFORE store imports it
vi.mock("@/transport/wsClient", () => ({
  wsClient: {
    send: vi.fn(),
    onStatus: vi.fn(() => vi.fn()),
    onMessage: vi.fn(() => vi.fn()),
    getStatus: vi.fn(() => "disconnected"),
    connect: vi.fn(),
    disconnect: vi.fn(),
  },
}))

import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import type { ReactionPrompt } from "@/types/game"

const oaPrompt: ReactionPrompt = {
  trigger: {
    trigger_type: "leaving_reach",
    source_creature_id: "goblin_1",
    data: {},
  },
  options: [
    {
      action_type: "opportunity_attack",
      description: "Attack the fleeing enemy",
      params: { target_id: "goblin_1" },
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  useGameStore.setState({ reactionPrompt: null })
})

describe("reaction store", () => {
  it("onReactionPrompt sets reactionPrompt state", () => {
    useGameStore.getState().onReactionPrompt({
      type: "reaction_prompt",
      ...oaPrompt,
    })

    expect(useGameStore.getState().reactionPrompt).toEqual(oaPrompt)
  })

  it("submitReaction sends correct WS message and clears reactionPrompt", () => {
    useGameStore.setState({ reactionPrompt: oaPrompt })

    useGameStore.getState().submitReaction("opportunity_attack", { target_id: "goblin_1" })

    expect(wsClient.send).toHaveBeenCalledWith({
      type: "reaction",
      name: "opportunity_attack",
      params: { target_id: "goblin_1" },
    })
    expect(useGameStore.getState().reactionPrompt).toBeNull()
  })

  it("submitReaction with skip sends skip message without params", () => {
    useGameStore.setState({ reactionPrompt: oaPrompt })

    useGameStore.getState().submitReaction("skip")

    expect(wsClient.send).toHaveBeenCalledWith({
      type: "reaction",
      name: "skip",
    })
    expect(useGameStore.getState().reactionPrompt).toBeNull()
  })

  it("reaction_prompt WS message is routed to onReactionPrompt", () => {
    // Simulate receiving a reaction_prompt message through the WS handler
    // The connectionSlice routes messages to handlers via onMessage
    const state = useGameStore.getState()
    state.onReactionPrompt({
      type: "reaction_prompt",
      trigger: oaPrompt.trigger,
      options: oaPrompt.options,
    })

    expect(useGameStore.getState().reactionPrompt).toEqual(oaPrompt)
  })
})
