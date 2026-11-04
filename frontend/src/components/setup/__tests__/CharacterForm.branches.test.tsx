import { act, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import "@/i18n"
import { api } from "@/transport/apiClient"
import { CharacterForm } from "../CharacterForm"

vi.mock("@/transport/apiClient", () => ({
  api: {
    player: {
      getSetupConfig: vi.fn(),
      createCharacter: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api.player)
const SESSION_ID = "branch-session"
type CreatedCharacter = Awaited<ReturnType<typeof api.player.createCharacter>>

const createdCharacter: CreatedCharacter = {
  player_id: "new-player",
  name: "Adventurer",
  race: "human",
  char_class: "fighter",
  alignment: "true_neutral",
  level: 1,
  experience: 0,
  level_up_available: false,
  xp_to_next_level: 300,
  hp: 10,
  max_hp: 10,
  ac: 18,
  gold: 100,
  location_id: "",
  ability_scores: { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 },
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function setup() {
  const onCreated = vi.fn()
  const user = userEvent.setup({ delay: null })
  render(<CharacterForm sessionId={SESSION_ID} onCreated={onCreated} />)
  return { user, onCreated }
}

beforeEach(() => {
  vi.resetAllMocks()
  mockApi.getSetupConfig.mockResolvedValue({ starting_gold: 100, point_buy_budget: 27 })
  mockApi.createCharacter.mockResolvedValue(createdCharacter)
})

afterEach(() => vi.restoreAllMocks())

describe("CharacterForm — uncovered branches", () => {
  it("keeps the form usable while config loads, then applies server gold and point-buy limits", async () => {
    const config = deferred<Awaited<ReturnType<typeof api.player.getSetupConfig>>>()
    mockApi.getSetupConfig.mockReturnValue(config.promise)
    const { user } = setup()

    expect(screen.getByText(`Session: ${SESSION_ID}`)).toBeVisible()
    expect(screen.getByRole("textbox")).toBeEnabled()
    expect(screen.getByRole("button", { name: "Create Character" })).toBeEnabled()
    expect(mockApi.getSetupConfig).toHaveBeenCalledExactlyOnceWith()

    await act(async () => config.resolve({ starting_gold: 250, point_buy_budget: 13 }))

    expect(screen.getByText(/Gold:/)).toHaveTextContent("Gold: 250")
    expect(screen.getByText(/Remaining points:/)).toHaveTextContent("Remaining points: 1 / 13")
    const abilities = screen.getByRole("group", { name: "Ability Scores" })
    await user.click(within(abilities).getAllByRole("button", { name: "+" })[0])
    expect(screen.getByText(/Remaining points:/)).toHaveTextContent("Remaining points: 0 / 13")
    for (const button of within(abilities).getAllByRole("button", { name: "+" })) {
      expect(button).toBeDisabled()
    }
    expect(mockApi.createCharacter).not.toHaveBeenCalled()
  })

  it("retains the fallback config when loading fails", async () => {
    const error = new Error("Setup service unavailable")
    const logError = vi.spyOn(console, "error").mockImplementation(() => {})
    mockApi.getSetupConfig.mockRejectedValue(error)
    setup()

    await waitFor(() => expect(logError).toHaveBeenCalledWith("Failed to fetch setup config:", error))

    expect(screen.getByText(/Gold:/)).toHaveTextContent("Gold: 100")
    expect(screen.getByText(/Remaining points:/)).toHaveTextContent("Remaining points: 15 / 27")
    expect(screen.getByRole("button", { name: "Create Character" })).toBeEnabled()
    expect(screen.queryByText(error.message)).not.toBeInTheDocument()
  })

  it("blocks a Fighter submission with no style, then accepts a selected style", async () => {
    const { user, onCreated } = setup()
    const submit = screen.getByRole("button", { name: "Create Character" })

    expect(screen.getByRole("option", { name: "— Select —" })).toBeDisabled()
    await user.click(submit)
    expect(mockApi.createCharacter).not.toHaveBeenCalled()
    expect(onCreated).not.toHaveBeenCalled()
    expect(submit).toBeEnabled()

    await user.selectOptions(screen.getByDisplayValue("— Select —"), "dueling")
    await user.click(submit)

    expect(mockApi.createCharacter).toHaveBeenCalledExactlyOnceWith(SESSION_ID, {
      name: "Adventurer",
      race: "human",
      char_class: "fighter",
      alignment: "true_neutral",
      ability_scores: { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 },
      fighting_style: "dueling",
    })
    await waitFor(() => expect(onCreated).toHaveBeenCalledExactlyOnceWith("new-player"))
  })

  it("forgets a Fighter's previous style after switching away and back", async () => {
    const { user, onCreated } = setup()
    await user.selectOptions(screen.getByDisplayValue("— Select —"), "defense")
    await user.selectOptions(screen.getByDisplayValue("Fighter"), "paladin")
    await user.selectOptions(screen.getByDisplayValue("Paladin"), "fighter")

    expect(screen.getByDisplayValue("— Select —")).toBeVisible()
    expect(screen.queryByText("While wearing armor, you gain +1 AC.")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Create Character" }))
    expect(mockApi.createCharacter).not.toHaveBeenCalled()
    expect(onCreated).not.toHaveBeenCalled()
  })

  it("submits edited Paladin details without a stale style after a blocked Fighter attempt", async () => {
    const { user, onCreated } = setup()
    await user.click(screen.getByRole("button", { name: "Create Character" }))
    await user.selectOptions(screen.getByDisplayValue("— Select —"), "great_weapon_fighting")
    await user.selectOptions(screen.getByDisplayValue("Fighter"), "paladin")
    await user.clear(screen.getByRole("textbox"))
    await user.type(screen.getByRole("textbox"), "Seren")
    await user.selectOptions(screen.getByDisplayValue("Human"), "elf")
    await user.selectOptions(screen.getByDisplayValue("True Neutral"), "lawful_good")
    // Abilities are displayed in STR, DEX, CON, INT, WIS, CHA order.
    const abilities = screen.getByRole("group", { name: "Ability Scores" })
    await user.click(within(abilities).getAllByRole("button", { name: "-" })[2])

    expect(within(abilities).getByText("-1")).toBeVisible()
    expect(screen.getByText(/HP:/)).toHaveTextContent("HP: 9")
    expect(screen.getByText(/AC:/)).toHaveTextContent("AC: 18")
    expect(screen.getByText(/Starting equipment:/)).toHaveTextContent("Chain Mail, Longsword, Shield")
    await user.click(screen.getByRole("button", { name: "Create Character" }))

    expect(mockApi.createCharacter).toHaveBeenCalledExactlyOnceWith(SESSION_ID, {
      name: "Seren",
      race: "elf",
      char_class: "paladin",
      alignment: "lawful_good",
      ability_scores: { str: 10, dex: 10, con: 9, int: 10, wis: 10, cha: 10 },
    })
    await waitFor(() => expect(onCreated).toHaveBeenCalledExactlyOnceWith("new-player"))
  })

  it("shows server errors, clears them on retry, and prevents duplicate in-flight submissions", async () => {
    mockApi.createCharacter.mockRejectedValueOnce(new Error("This session is full"))
    const retry = deferred<CreatedCharacter>()
    mockApi.createCharacter.mockReturnValueOnce(retry.promise)
    const { user, onCreated } = setup()
    await user.selectOptions(screen.getByDisplayValue("Fighter"), "rogue")
    const submit = screen.getByRole("button", { name: "Create Character" })
    await user.click(submit)

    expect(await screen.findByText("This session is full")).toBeVisible()
    expect(onCreated).not.toHaveBeenCalled()
    expect(submit).toBeEnabled()

    await user.click(submit)
    expect(screen.queryByText("This session is full")).not.toBeInTheDocument()
    expect(submit).toBeDisabled()
    await user.click(submit)
    expect(mockApi.createCharacter).toHaveBeenCalledTimes(2)
    expect(mockApi.createCharacter).toHaveBeenLastCalledWith(SESSION_ID, {
      name: "Adventurer",
      race: "human",
      char_class: "rogue",
      alignment: "true_neutral",
      ability_scores: { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 },
    })
    expect(onCreated).not.toHaveBeenCalled()

    await act(async () => retry.resolve({ ...createdCharacter, player_id: "retry-player" }))
    expect(onCreated).toHaveBeenCalledExactlyOnceWith("retry-player")
    expect(submit).toBeEnabled()
  })

  it("uses the translated fallback message for non-Error rejections", async () => {
    mockApi.createCharacter.mockRejectedValue({ detail: "Not an Error instance" })
    const { user, onCreated } = setup()
    await user.selectOptions(screen.getByDisplayValue("Fighter"), "paladin")
    await user.click(screen.getByRole("button", { name: "Create Character" }))

    expect(await screen.findByText("Failed to create character")).toBeVisible()
    expect(screen.queryByText("Not an Error instance")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Create Character" })).toBeEnabled()
    expect(onCreated).not.toHaveBeenCalled()
  })
})
