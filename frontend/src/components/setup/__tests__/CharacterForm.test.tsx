import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import "@/i18n"
import { CharacterForm } from "../CharacterForm"
import { api } from "@/transport/apiClient"

vi.mock("@/transport/apiClient", () => ({
  api: {
    player: {
      getSetupConfig: vi.fn().mockResolvedValue({
        starting_gold: 100,
        point_buy_budget: 27,
      }),
      createCharacter: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api.player)

const SESSION_ID = "test-session-123"

function setup() {
  const onCreated = vi.fn()
  // delay: null skips the per-event wait; click-heavy tests otherwise flake on the 5s timeout under full-suite load
  const user = userEvent.setup({ delay: null })
  render(<CharacterForm sessionId={SESSION_ID} onCreated={onCreated} />)
  return { onCreated, user }
}

/** Click a button N times. */
async function clickTimes(user: ReturnType<typeof userEvent.setup>, button: HTMLElement, n: number) {
  for (let i = 0; i < n; i++) {
    await user.click(button)
  }
}

describe("CharacterForm — Point Buy", () => {
  beforeEach(() => vi.clearAllMocks())

  it("starts all scores at 10 with 5 remaining points", () => {
    setup()
    // Default: all 10 = 6×2pts = 12 spent, 27-12 = 15 remaining
    expect(screen.getByTestId("remaining-points")).toHaveTextContent("15")
  })

  it("increments score and decreases remaining points", async () => {
    const { user } = setup()
    const strPlus = screen.getByTestId("str-plus")
    await user.click(strPlus) // 10→11 costs 1 more point

    // STR should now be 11
    expect(screen.getByTestId("str-score")).toHaveTextContent("11")
    // Remaining: 15 - 1 = 14
    expect(screen.getByTestId("remaining-points")).toHaveTextContent("14")
  })

  it("decrements score and increases remaining points", async () => {
    const { user } = setup()
    const strMinus = screen.getByTestId("str-minus")
    await user.click(strMinus) // 10→9 frees 1 point

    expect(screen.getByTestId("str-score")).toHaveTextContent("9")
    // Remaining: 15 + 1 = 16
    expect(screen.getByTestId("remaining-points")).toHaveTextContent("16")
  })

  it("disables + button at score 15", async () => {
    const { user } = setup()
    const strPlus = screen.getByTestId("str-plus")
    // 10→15 = 5 clicks
    await clickTimes(user, strPlus, 5)
    expect(screen.getByTestId("str-score")).toHaveTextContent("15")
    expect(strPlus).toBeDisabled()
  })

  it("disables - button at score 8", async () => {
    const { user } = setup()
    const strMinus = screen.getByTestId("str-minus")
    // 10→8 = 2 clicks
    await clickTimes(user, strMinus, 2)
    expect(screen.getByTestId("str-score")).toHaveTextContent("8")
    expect(strMinus).toBeDisabled()
  })

  it("disables + when not enough points remain", async () => {
    const { user } = setup()
    // Start: all at 10 → 12 spent, 15 remaining.
    // STR 10→15 (+7) and DEX 10→15 (+7) leave 1 point; CON 10→11 (+1) exhausts it.
    await clickTimes(user, screen.getByTestId("str-plus"), 5)
    await clickTimes(user, screen.getByTestId("dex-plus"), 5)
    await clickTimes(user, screen.getByTestId("con-plus"), 1)

    expect(screen.getByTestId("remaining-points")).toHaveTextContent("0")
    // INT is at 10, raising to 11 costs 1 point, but 0 remain → disabled
    expect(screen.getByTestId("int-plus")).toBeDisabled()
  })

  it("shows modifier for each score", () => {
    setup()
    // Score 10 → modifier +0
    expect(screen.getByTestId("str-modifier")).toHaveTextContent("+0")
  })
})

describe("CharacterForm — Class Restrictions", () => {
  beforeEach(() => vi.clearAllMocks())

  it("shows Fighter, Rogue and Paladin as class options", () => {
    setup()
    const classSelect = screen.getByTestId("class-select")
    const options = classSelect.querySelectorAll("option")
    expect(options).toHaveLength(3)
    expect(options[0]).toHaveValue("fighter")
    expect(options[1]).toHaveValue("rogue")
    expect(options[2]).toHaveValue("paladin")
  })
})

describe("CharacterForm — Fighting Style", () => {
  beforeEach(() => vi.clearAllMocks())

  it("shows fighting style selector for Fighter", () => {
    setup()
    // Default class is fighter
    expect(screen.getByTestId("fighting-style-select")).toBeInTheDocument()
  })

  it("hides fighting style selector for Rogue", async () => {
    const { user } = setup()
    const classSelect = screen.getByTestId("class-select")
    await user.selectOptions(classSelect, "rogue")
    expect(screen.queryByTestId("fighting-style-select")).not.toBeInTheDocument()
  })

  it("offers Defense, Dueling, Great Weapon Fighting options", () => {
    setup()
    const styleSelect = screen.getByTestId("fighting-style-select")
    const options = styleSelect.querySelectorAll("option")
    // Placeholder + 3 styles
    const values = Array.from(options).map((o) => o.value)
    expect(values).toContain("defense")
    expect(values).toContain("dueling")
    expect(values).toContain("great_weapon_fighting")
  })

  it("shows the selected fighting style description", async () => {
    const { user } = setup()

    expect(screen.queryByTestId("fighting-style-description")).not.toBeInTheDocument()
    await user.selectOptions(screen.getByTestId("fighting-style-select"), "dueling")

    expect(screen.getByTestId("fighting-style-description")).toHaveTextContent(
      "When wielding a melee weapon in one hand and no other weapons, you gain +2 to damage rolls.",
    )
  })
})

describe("CharacterForm — Preview", () => {
  beforeEach(() => vi.clearAllMocks())

  it("shows correct HP preview for Fighter with CON 14", async () => {
    const { user } = setup()
    // Default class is fighter. Raise CON from 10 to 14 (+4 clicks)
    await clickTimes(user, screen.getByTestId("con-plus"), 4)
    // Fighter HP = d10 + CON mod(+2) = 12
    expect(screen.getByTestId("preview-hp")).toHaveTextContent("12")
  })

  it("shows correct HP preview for Rogue with CON 12", async () => {
    const { user } = setup()
    await user.selectOptions(screen.getByTestId("class-select"), "rogue")
    // Raise CON from 10 to 12 (+2 clicks)
    await clickTimes(user, screen.getByTestId("con-plus"), 2)
    // Rogue HP = d8 + CON mod(+1) = 9
    expect(screen.getByTestId("preview-hp")).toHaveTextContent("9")
  })

  it("shows correct AC preview for Fighter with Defense style", async () => {
    const { user } = setup()
    // Fighter: chain mail(16) + shield(+2) = 18. With defense: +1 = 19
    await user.selectOptions(screen.getByTestId("fighting-style-select"), "defense")
    expect(screen.getByTestId("preview-ac")).toHaveTextContent("19")
  })

  it("shows correct AC preview for Fighter without style", () => {
    setup()
    // Fighter: chain mail(16) + shield(+2) = 18
    expect(screen.getByTestId("preview-ac")).toHaveTextContent("18")
  })

  it("shows correct AC preview for Fighter with GWF (no shield)", async () => {
    const { user } = setup()
    // GWF: chain mail(16), no shield → AC 16
    await user.selectOptions(screen.getByTestId("fighting-style-select"), "great_weapon_fighting")
    expect(screen.getByTestId("preview-ac")).toHaveTextContent("16")
  })

  it("shows greatsword equipment for Fighter with GWF", async () => {
    const { user } = setup()
    await user.selectOptions(screen.getByTestId("fighting-style-select"), "great_weapon_fighting")
    const equipText = screen.getByTestId("preview-equipment").textContent
    expect(equipText).toContain("Greatsword")
    expect(equipText).not.toContain("Shield")
    expect(equipText).not.toContain("Longsword")
  })

  it("shows correct AC preview for Rogue with DEX 15", async () => {
    const { user } = setup()
    await user.selectOptions(screen.getByTestId("class-select"), "rogue")
    // Raise DEX from 10 to 15 (+5 clicks)
    await clickTimes(user, screen.getByTestId("dex-plus"), 5)
    // Rogue: leather(11) + DEX mod(+2) = 13
    expect(screen.getByTestId("preview-ac")).toHaveTextContent("13")
  })

  it("shows starting equipment text", () => {
    setup()
    // Fighter equipment
    expect(screen.getByTestId("preview-equipment")).toBeInTheDocument()
  })

  it("shows gold as 100", () => {
    setup()
    expect(screen.getByTestId("preview-gold")).toHaveTextContent("100")
  })
})

describe("CharacterForm — Submission", () => {
  beforeEach(() => vi.clearAllMocks())

  it("sends correct payload for Fighter", async () => {
    mockApi.createCharacter.mockResolvedValue({
      player_id: "p-1",
      name: "Adventurer",
      race: "human",
      char_class: "fighter",
      level: 1,
      alignment: "true_neutral",
      hp: 10,
      max_hp: 10,
      ac: 18,
      gold: 100,
      location_id: "",
      appearance: "",
      ability_scores: { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 },
    })

    const { user, onCreated } = setup()

    // Select defense fighting style
    await user.selectOptions(screen.getByTestId("fighting-style-select"), "defense")

    // Submit
    await user.click(screen.getByRole("button", { name: /create character/i }))

    await waitFor(() => {
      expect(mockApi.createCharacter).toHaveBeenCalledWith(SESSION_ID, {
        name: "Adventurer",
        race: "human",
        char_class: "fighter",
        alignment: "true_neutral",
        ability_scores: { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 },
        fighting_style: "defense",
      })
    })

    await waitFor(() => {
      expect(onCreated).toHaveBeenCalledWith("p-1")
    })
  })

  it("sends correct payload for Rogue (no fighting_style)", async () => {
    mockApi.createCharacter.mockResolvedValue({
      player_id: "p-2",
      name: "Adventurer",
      race: "human",
      char_class: "rogue",
      level: 1,
      alignment: "true_neutral",
      hp: 9,
      max_hp: 9,
      ac: 10,
      gold: 100,
      location_id: "",
      appearance: "",
      ability_scores: { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 },
    })

    const { user, onCreated } = setup()
    await user.selectOptions(screen.getByTestId("class-select"), "rogue")

    await user.click(screen.getByRole("button", { name: /create character/i }))

    await waitFor(() => {
      expect(mockApi.createCharacter).toHaveBeenCalledWith(SESSION_ID, {
        name: "Adventurer",
        race: "human",
        char_class: "rogue",
        alignment: "true_neutral",
        ability_scores: { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 },
      })
    })

    await waitFor(() => {
      expect(onCreated).toHaveBeenCalledWith("p-2")
    })
  })

  it("does not include level, hp, ac, gold in payload", async () => {
    mockApi.createCharacter.mockResolvedValue({
      player_id: "p-3",
      name: "Adventurer",
      race: "human",
      char_class: "fighter",
      level: 1,
      alignment: "true_neutral",
      hp: 10,
      max_hp: 10,
      ac: 18,
      gold: 100,
      location_id: "",
      appearance: "",
      ability_scores: { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 },
    })

    const { user } = setup()
    await user.selectOptions(screen.getByTestId("fighting-style-select"), "defense")
    await user.click(screen.getByRole("button", { name: /create character/i }))

    await waitFor(() => {
      const payload = mockApi.createCharacter.mock.calls[0][1]
      expect(payload).not.toHaveProperty("level")
      expect(payload).not.toHaveProperty("hp")
      expect(payload).not.toHaveProperty("ac")
      expect(payload).not.toHaveProperty("gold")
    })
  })

  it("does not have level, hp, ac, gold input fields", () => {
    setup()
    expect(screen.queryByLabelText(/^level$/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/^hp$/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/^ac$/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/^gold$/i)).not.toBeInTheDocument()
  })
})
