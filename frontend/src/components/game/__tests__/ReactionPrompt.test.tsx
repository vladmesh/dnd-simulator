import { render, screen, fireEvent } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import "@/i18n"

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
import { ReactionPrompt } from "../ReactionPrompt"
import { wsClient } from "@/transport/wsClient"
import type { ReactionPrompt as ReactionPromptData } from "@/types/game"

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const oaPrompt: ReactionPromptData = {
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

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks()
  useGameStore.setState({ reactionPrompt: null })
})

describe("ReactionPrompt", () => {
  it("renders trigger description and option buttons when prompt is set", () => {
    useGameStore.setState({ reactionPrompt: oaPrompt })
    render(<ReactionPrompt />)

    expect(screen.getByTestId("reaction-prompt")).toBeTruthy()
    // Should have Attack and Skip buttons
    expect(screen.getByTestId("reaction-option-opportunity_attack")).toBeTruthy()
    expect(screen.getByTestId("reaction-skip")).toBeTruthy()
  })

  it("clicking Attack calls submitReaction with correct params", () => {
    useGameStore.setState({ reactionPrompt: oaPrompt })
    render(<ReactionPrompt />)

    fireEvent.click(screen.getByTestId("reaction-option-opportunity_attack"))

    expect(wsClient.send).toHaveBeenCalledWith({
      type: "reaction",
      name: "opportunity_attack",
      params: { target_id: "goblin_1" },
    })
    // Prompt should be cleared
    expect(useGameStore.getState().reactionPrompt).toBeNull()
  })

  it("clicking Skip sends skip reaction", () => {
    useGameStore.setState({ reactionPrompt: oaPrompt })
    render(<ReactionPrompt />)

    fireEvent.click(screen.getByTestId("reaction-skip"))

    expect(wsClient.send).toHaveBeenCalledWith({
      type: "reaction",
      name: "skip",
    })
    expect(useGameStore.getState().reactionPrompt).toBeNull()
  })

  it("does not render when reactionPrompt is null", () => {
    useGameStore.setState({ reactionPrompt: null })
    render(<ReactionPrompt />)

    expect(screen.queryByTestId("reaction-prompt")).toBeNull()
  })
})
