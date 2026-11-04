import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter, Route, Routes, useParams } from "react-router"
import i18n from "@/i18n"
import { api } from "@/transport/apiClient"
import type { PlayerStatusResponse, SessionResponse, WorldListItem } from "@/types/api"
import { SetupScreen } from "../SetupScreen"

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: { getWorlds: vi.fn(), createSession: vi.fn() },
    player: { getSetupConfig: vi.fn(), createCharacter: vi.fn() },
  },
}))

const master = vi.mocked(api.master)
const player = vi.mocked(api.player)
const worlds: WorldListItem[] = [
  { id: "forest", name: "Enchanted Forest", description: "An ancient woodland", editable: false },
  { id: "desert", name: "Desert Kingdom", description: "", editable: true },
]
const session: SessionResponse = {
  session_id: "new-session", player_name: "", player_location: "", time: "",
}
const scores = { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 }
const character: PlayerStatusResponse = {
  player_id: "new-player", name: "Adventurer", race: "human", char_class: "fighter",
  level: 1, experience: 0, level_up_available: false, xp_to_next_level: 300,
  alignment: "true_neutral", hp: 10, max_hp: 10, ac: 18, gold: 100,
  location_id: "forest", ability_scores: scores,
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

function GameDestination() {
  const { sessionId } = useParams()
  return <h1>Playing session {sessionId}</h1>
}

function setup() {
  return render(
    <MemoryRouter initialEntries={["/play"]}>
      <Routes>
        <Route path="/play" element={<SetupScreen />} />
        <Route path="/play/:sessionId" element={<GameDestination />} />
      </Routes>
    </MemoryRouter>,
  )
}

// The current form labels are not associated with their selects; locate them
// through the visible option text rather than test IDs or DOM structure.
function selectWithOption(name: string) {
  const select = screen.getAllByRole("combobox").find((element) =>
    within(element).queryByRole("option", { name }),
  )
  if (!select) throw new Error(`Missing select with option ${name}`)
  return select
}

async function openCharacterForm(user: ReturnType<typeof userEvent.setup>) {
  setup()
  await user.click((await screen.findAllByRole("button", { name: "New Session" }))[0])
  await screen.findByRole("button", { name: "Create Character" })
}

describe("SetupScreen remaining branches", () => {
  beforeEach(async () => {
    vi.resetAllMocks()
    localStorage.clear()
    await i18n.changeLanguage("en")
    master.getWorlds.mockResolvedValue(worlds)
    master.createSession.mockResolvedValue(session)
    player.getSetupConfig.mockResolvedValue({ starting_gold: 175, point_buy_budget: 30 })
    player.createCharacter.mockResolvedValue(character)
  })

  afterEach(async () => {
    cleanup()
    await i18n.changeLanguage("en")
    localStorage.clear()
  })

  it("keeps the chooser and disabled join visible while worlds load, then renders descriptions and ID fallbacks", async () => {
    const loading = deferred<WorldListItem[]>()
    master.getWorlds.mockReturnValue(loading.promise)
    const user = userEvent.setup()
    setup()

    expect(screen.getByRole("heading", { name: "D&D Simulator" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Choose a World" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "New Session" })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Join" })).toBeDisabled()
    await user.type(screen.getByRole("textbox"), "   {Enter}")
    expect(screen.getByRole("button", { name: "Join" })).toBeDisabled()
    expect(screen.queryByRole("heading", { name: /Playing session/ })).not.toBeInTheDocument()

    await act(async () => loading.resolve(worlds))
    expect(await screen.findByText("Enchanted Forest")).toBeInTheDocument()
    expect(screen.getByText("An ancient woodland")).toBeInTheDocument()
    expect(screen.getByText("Desert Kingdom")).toBeInTheDocument()
    expect(screen.getByText("desert")).toBeInTheDocument()
    expect(screen.getAllByRole("button", { name: "New Session" })).toHaveLength(2)
    expect(master.getWorlds).toHaveBeenCalledWith("en")
  })

  it("shows the empty-world message without disabling joining an existing session", async () => {
    master.getWorlds.mockResolvedValue([])
    const user = userEvent.setup()
    setup()
    expect(await screen.findByText("No worlds available. Create one via the Master API.")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "New Session" })).not.toBeInTheDocument()
    await user.type(screen.getByRole("textbox"), "existing-session")
    expect(screen.getByRole("button", { name: "Join" })).toBeEnabled()
    expect(master.createSession).not.toHaveBeenCalled()
  })

  it("shows a load error while leaving the join controls available", async () => {
    master.getWorlds.mockRejectedValue(new Error("offline"))
    setup()
    expect(await screen.findByText("Failed to load worlds")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "New Session" })).not.toBeInTheDocument()
    expect(screen.getByRole("textbox")).toBeEnabled()
    expect(screen.getByRole("button", { name: "Join" })).toBeDisabled()
    expect(player.getSetupConfig).not.toHaveBeenCalled()
  })

  it("disables all world buttons during creation and reports a failed session request", async () => {
    const creating = deferred<SessionResponse>()
    master.createSession.mockReturnValue(creating.promise)
    const user = userEvent.setup()
    setup()
    await user.click((await screen.findAllByRole("button", { name: "New Session" }))[1])
    expect(master.createSession).toHaveBeenCalledExactlyOnceWith({ world_name: "desert", lang: "en" })
    for (const button of screen.getAllByRole("button", { name: "New Session" })) {
      expect(button).toBeDisabled()
      await user.click(button)
    }
    expect(master.createSession).toHaveBeenCalledTimes(1)
    await act(async () => creating.reject(new Error("offline")))
    expect(await screen.findByText("Failed to create session")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Create Character" })).not.toBeInTheDocument()
    expect(player.getSetupConfig).not.toHaveBeenCalled()
  })

  it("reloads worlds in the selected language and uses that language for the session", async () => {
    const user = userEvent.setup()
    setup()
    await screen.findByText("Enchanted Forest")
    await user.click(screen.getByRole("button", { name: "RU" }))
    expect(await screen.findByRole("heading", { name: "Выберите мир" })).toBeInTheDocument()
    await waitFor(() => expect(master.getWorlds).toHaveBeenLastCalledWith("ru"))
    await user.click(screen.getAllByRole("button", { name: "Новая сессия" })[0])
    expect(master.createSession).toHaveBeenCalledExactlyOnceWith({ world_name: "forest", lang: "ru" })
    expect(await screen.findByRole("button", { name: "Создать персонажа" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "EN" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "RU" })).not.toBeInTheDocument()
    expect(screen.queryByText("Подключиться к сессии")).not.toBeInTheDocument()
  })

  it("joins a trimmed session ID by button without overwriting its saved player", async () => {
    localStorage.setItem("player_id:existing-session", "saved-player")
    const user = userEvent.setup()
    setup()
    await screen.findByText("Enchanted Forest")
    await user.type(screen.getByRole("textbox"), "  existing-session  ")
    await user.click(screen.getByRole("button", { name: "Join" }))
    expect(await screen.findByRole("heading", { name: "Playing session existing-session" })).toBeInTheDocument()
    expect(localStorage.getItem("player_id:existing-session")).toBe("saved-player")
    expect(master.createSession).not.toHaveBeenCalled()
    expect(player.createCharacter).not.toHaveBeenCalled()
  })

  it("joins a trimmed session ID with Enter without creating a player ID", async () => {
    const user = userEvent.setup()
    setup()
    await screen.findByText("Enchanted Forest")
    await user.type(screen.getByRole("textbox"), "  keyboard-session  {Enter}")
    expect(await screen.findByRole("heading", { name: "Playing session keyboard-session" })).toBeInTheDocument()
    expect(localStorage.getItem("player_id:keyboard-session")).toBeNull()
    expect(master.createSession).not.toHaveBeenCalled()
    expect(player.createCharacter).not.toHaveBeenCalled()
  })

  it("submits edited fighter details once, then stores the player for the new session and navigates", async () => {
    const saving = deferred<PlayerStatusResponse>()
    player.createCharacter.mockReturnValue(saving.promise)
    localStorage.setItem("player_id:other-session", "other-player")
    const user = userEvent.setup()
    await openCharacterForm(user)
    expect(player.getSetupConfig).toHaveBeenCalledExactlyOnceWith()
    expect(screen.getByText("Session: new-session")).toBeInTheDocument()
    expect(screen.getByText(/Remaining points/)).toHaveTextContent("Remaining points: 18 / 30")
    expect(screen.getByText("Gold:")).toHaveTextContent("Gold: 175")
    await user.clear(screen.getByRole("textbox"))
    await user.type(screen.getByRole("textbox"), "Aria")
    await user.selectOptions(selectWithOption("Elf"), "elf")
    await user.selectOptions(selectWithOption("Lawful Good"), "lawful_good")
    await user.selectOptions(selectWithOption("Defense"), "defense")
    await user.click(screen.getByRole("button", { name: "Create Character" }))
    expect(player.createCharacter).toHaveBeenCalledExactlyOnceWith("new-session", {
      name: "Aria", race: "elf", char_class: "fighter", alignment: "lawful_good",
      ability_scores: scores, fighting_style: "defense",
    })
    expect(screen.getByRole("button", { name: "Create Character" })).toBeDisabled()
    await user.click(screen.getByRole("button", { name: "Create Character" }))
    expect(player.createCharacter).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem("player_id:new-session")).toBeNull()
    await act(async () => saving.resolve(character))
    expect(await screen.findByRole("heading", { name: "Playing session new-session" })).toBeInTheDocument()
    expect(localStorage.getItem("player_id:new-session")).toBe("new-player")
    expect(localStorage.getItem("player_id:other-session")).toBe("other-player")
  })

  it("omits a previously selected fighting style when submitting a rogue", async () => {
    const user = userEvent.setup()
    await openCharacterForm(user)
    await user.selectOptions(selectWithOption("Defense"), "dueling")
    await user.selectOptions(selectWithOption("Fighter"), "rogue")
    expect(screen.queryByText("Fighting Style")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Create Character" }))
    expect(player.createCharacter).toHaveBeenCalledExactlyOnceWith("new-session", {
      name: "Adventurer", race: "human", char_class: "rogue", alignment: "true_neutral", ability_scores: scores,
    })
    expect(await screen.findByRole("heading", { name: "Playing session new-session" })).toBeInTheDocument()
  })

  it.each([
    { reason: new Error("That name is already taken"), message: "That name is already taken" },
    { reason: "unstructured server failure", message: "Failed to create character" },
  ])("shows '$message' on character failure and allows a successful retry", async ({ reason, message }) => {
    player.createCharacter.mockRejectedValueOnce(reason)
    const user = userEvent.setup()
    await openCharacterForm(user)
    await user.selectOptions(selectWithOption("Defense"), "defense")
    await user.click(screen.getByRole("button", { name: "Create Character" }))
    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Create Character" })).toBeEnabled()
    expect(localStorage.getItem("player_id:new-session")).toBeNull()
    expect(screen.queryByRole("heading", { name: /Playing session/ })).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Create Character" }))
    expect(await screen.findByRole("heading", { name: "Playing session new-session" })).toBeInTheDocument()
    expect(player.createCharacter).toHaveBeenCalledTimes(2)
    expect(player.createCharacter).toHaveBeenLastCalledWith("new-session", {
      name: "Adventurer", race: "human", char_class: "fighter", alignment: "true_neutral",
      ability_scores: scores, fighting_style: "defense",
    })
    expect(localStorage.getItem("player_id:new-session")).toBe("new-player")
  })
})
