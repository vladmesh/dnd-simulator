import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi } from "vitest"
import { SchemaForm } from "../SchemaForm"
import type { JsonSchema } from "@/types/api"

// Helper: build a minimal schema with given properties
function makeSchema(
  properties: Record<string, JsonSchema>,
  required: string[] = [],
  $defs?: Record<string, JsonSchema>,
): JsonSchema {
  return {
    type: "object",
    properties,
    required,
    ...($defs ? { $defs } : {}),
  }
}

describe("SchemaForm", () => {
  describe("primitive fields", () => {
    it("renders string field as text input", () => {
      const schema = makeSchema({
        name: { type: "string", title: "Name" },
      })
      render(<SchemaForm schema={schema} onSubmit={vi.fn()} />)
      const input = screen.getByLabelText("Name")
      expect(input).toBeInTheDocument()
      expect(input).toHaveAttribute("type", "text")
    })

    it("renders integer field as number input", () => {
      const schema = makeSchema({
        hp: { type: "integer", title: "HP" },
      })
      render(<SchemaForm schema={schema} onSubmit={vi.fn()} />)
      const input = screen.getByLabelText("HP")
      expect(input).toHaveAttribute("type", "number")
    })

    it("renders number field as number input", () => {
      const schema = makeSchema({
        speed: { type: "number", title: "Speed" },
      })
      render(<SchemaForm schema={schema} onSubmit={vi.fn()} />)
      expect(screen.getByLabelText("Speed")).toHaveAttribute("type", "number")
    })

    it("renders boolean field as checkbox", () => {
      const schema = makeSchema({
        is_magic: { type: "boolean", title: "Is Magic" },
      })
      render(<SchemaForm schema={schema} onSubmit={vi.fn()} />)
      expect(screen.getByLabelText("Is Magic")).toHaveAttribute("type", "checkbox")
    })
  })

  describe("enum fields", () => {
    it("renders enum as native select with options", () => {
      const schema = makeSchema({
        race: {
          type: "string",
          title: "Race",
          enum: ["human", "elf", "dwarf"],
        },
      })
      render(<SchemaForm schema={schema} onSubmit={vi.fn()} />)
      const select = screen.getByLabelText("Race")
      expect(select.tagName).toBe("SELECT")
      const options = within(select as HTMLSelectElement).getAllByRole("option")
      // empty option + 3 enum values
      expect(options).toHaveLength(4)
      expect(options[1]).toHaveTextContent("human")
      expect(options[2]).toHaveTextContent("elf")
    })

    it("renders $ref to enum $def as select", () => {
      const schema = makeSchema(
        {
          role: { $ref: "#/$defs/NpcRole", title: "Role" },
        },
        [],
        {
          NpcRole: {
            type: "string",
            enum: ["commoner", "blacksmith", "guard"],
            title: "NpcRole",
          },
        },
      )
      render(<SchemaForm schema={schema} onSubmit={vi.fn()} />)
      const select = screen.getByLabelText("Role")
      expect(select.tagName).toBe("SELECT")
      const options = within(select as HTMLSelectElement).getAllByRole("option")
      expect(options).toHaveLength(4) // empty + 3
    })
  })

  describe("nested objects", () => {
    it("renders nested object fields in a fieldset", () => {
      const schema = makeSchema({
        ability_scores: {
          type: "object",
          title: "Ability Scores",
          properties: {
            str: { type: "integer", title: "Str", default: 10 },
            dex: { type: "integer", title: "Dex", default: 10 },
          },
        },
      })
      render(<SchemaForm schema={schema} onSubmit={vi.fn()} />)
      // Should have a fieldset with legend
      expect(screen.getByText("Ability Scores")).toBeInTheDocument()
      expect(screen.getByLabelText("Str")).toHaveAttribute("type", "number")
      expect(screen.getByLabelText("Dex")).toHaveAttribute("type", "number")
    })

    it("renders $ref to object $def as nested fields", () => {
      const schema = makeSchema(
        {
          ability_scores: { $ref: "#/$defs/AbilityScoresContent" },
        },
        [],
        {
          AbilityScoresContent: {
            type: "object",
            title: "Ability Scores",
            properties: {
              str: { type: "integer", title: "Str", default: 10 },
              dex: { type: "integer", title: "Dex", default: 10 },
            },
          },
        },
      )
      render(<SchemaForm schema={schema} onSubmit={vi.fn()} />)
      expect(screen.getByText("Ability Scores")).toBeInTheDocument()
      expect(screen.getByLabelText("Str")).toBeInTheDocument()
    })
  })

  describe("localized text (object with additionalProperties: string)", () => {
    it("renders localized text field as single text input", () => {
      const schema = makeSchema({
        name: {
          type: "object",
          title: "Name",
          additionalProperties: { type: "string" },
        },
      })
      render(<SchemaForm schema={schema} onSubmit={vi.fn()} lang="en" />)
      const input = screen.getByLabelText("Name")
      expect(input).toHaveAttribute("type", "text")
    })

    it("submits localized text as {lang: value}", async () => {
      const user = userEvent.setup()
      const onSubmit = vi.fn()
      const schema = makeSchema(
        { name: { type: "object", title: "Name", additionalProperties: { type: "string" } } },
        ["name"],
      )
      render(<SchemaForm schema={schema} onSubmit={onSubmit} lang="en" />)
      await user.type(screen.getByLabelText(/^Name/), "Goblin")
      await user.click(screen.getByRole("button", { name: /save/i }))
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ name: { en: "Goblin" } }),
      )
    })
  })

  describe("array of objects", () => {
    it("renders add button for array field", () => {
      const schema = makeSchema({
        attacks: {
          type: "array",
          title: "Attacks",
          items: {
            type: "object",
            title: "AttackContent",
            properties: {
              name: { type: "string", title: "Name" },
              reach: { type: "integer", title: "Reach", default: 5 },
            },
            required: ["name"],
          },
        },
      })
      render(<SchemaForm schema={schema} onSubmit={vi.fn()} />)
      expect(screen.getByText("Attacks")).toBeInTheDocument()
      expect(screen.getByRole("button", { name: /add/i })).toBeInTheDocument()
    })

    it("adds and removes array rows", async () => {
      const user = userEvent.setup()
      const schema = makeSchema({
        attacks: {
          type: "array",
          title: "Attacks",
          items: {
            type: "object",
            properties: {
              name: { type: "string", title: "Name" },
            },
          },
        },
      })
      render(<SchemaForm schema={schema} onSubmit={vi.fn()} />)

      // Add a row
      await user.click(screen.getByRole("button", { name: /add/i }))
      expect(screen.getAllByLabelText("Name")).toHaveLength(1)

      // Add another
      await user.click(screen.getByRole("button", { name: /add/i }))
      expect(screen.getAllByLabelText("Name")).toHaveLength(2)

      // Remove first row
      const removeButtons = screen.getAllByRole("button", { name: /remove/i })
      await user.click(removeButtons[0])
      expect(screen.getAllByLabelText("Name")).toHaveLength(1)
    })

    it("submits array data correctly", async () => {
      const user = userEvent.setup()
      const onSubmit = vi.fn()
      const schema = makeSchema({
        attacks: {
          type: "array",
          title: "Attacks",
          items: {
            type: "object",
            properties: {
              name: { type: "string", title: "Name" },
              reach: { type: "integer", title: "Reach", default: 5 },
            },
          },
        },
      })
      render(<SchemaForm schema={schema} onSubmit={onSubmit} />)
      await user.click(screen.getByRole("button", { name: /add/i }))
      await user.type(screen.getByLabelText("Name"), "Bite")
      await user.click(screen.getByRole("button", { name: /save/i }))

      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          attacks: [expect.objectContaining({ name: "Bite" })],
        }),
      )
    })
  })

  describe("array of strings", () => {
    it("renders string array as comma-separated input", () => {
      const schema = makeSchema({
        tags: {
          type: "array",
          title: "Tags",
          items: { type: "string" },
        },
      })
      render(<SchemaForm schema={schema} onSubmit={vi.fn()} />)
      expect(screen.getByLabelText("Tags")).toHaveAttribute("type", "text")
    })

    it("submits string array as split values", async () => {
      const user = userEvent.setup()
      const onSubmit = vi.fn()
      const schema = makeSchema({
        tags: {
          type: "array",
          title: "Tags",
          items: { type: "string" },
        },
      })
      render(<SchemaForm schema={schema} onSubmit={onSubmit} />)
      await user.type(screen.getByLabelText("Tags"), "hostile, undead, boss")
      await user.click(screen.getByRole("button", { name: /save/i }))
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ tags: ["hostile", "undead", "boss"] }),
      )
    })
  })

  describe("x-ref-type fields", () => {
    it("renders ref field as select with fetched options", async () => {
      const schema = makeSchema({
        start_location: {
          type: "string",
          title: "Start Location",
          "x-ref-type": "locations",
        },
      })
      const refOptions = [
        { id: "town_square", name: "Town Square" },
        { id: "forest", name: "Forest" },
      ]
      render(
        <SchemaForm
          schema={schema}
          onSubmit={vi.fn()}
          worldId="test_world"
          fetchRefs={vi.fn().mockResolvedValue(refOptions)}
        />,
      )
      // Should show a select that loads ref options
      const select = await screen.findByLabelText("Start Location")
      expect(select.tagName).toBe("SELECT")
      const options = within(select as HTMLSelectElement).getAllByRole("option")
      // empty + 2 ref options
      expect(options).toHaveLength(3)
      expect(options[1]).toHaveTextContent("Town Square")
    })
  })

  describe("nullable fields (anyOf with null)", () => {
    it("handles anyOf [{type: string}, {type: null}] as optional string", () => {
      const schema = makeSchema({
        weapon_id: {
          title: "Weapon Id",
          anyOf: [{ type: "string" }, { type: "null" }],
          default: null,
        },
      })
      render(<SchemaForm schema={schema} onSubmit={vi.fn()} />)
      expect(screen.getByLabelText("Weapon Id")).toHaveAttribute("type", "text")
    })

    it("handles anyOf [{type: integer}, {type: null}] as optional number", () => {
      const schema = makeSchema({
        price: {
          title: "Price",
          anyOf: [{ type: "integer" }, { type: "null" }],
          default: null,
        },
      })
      render(<SchemaForm schema={schema} onSubmit={vi.fn()} />)
      expect(screen.getByLabelText("Price")).toHaveAttribute("type", "number")
    })
  })

  describe("defaults", () => {
    it("pre-fills fields from schema defaults", () => {
      const schema = makeSchema({
        hp: { type: "integer", title: "HP", default: 10 },
        race: { type: "string", title: "Race", enum: ["human", "elf"], default: "human" },
      })
      render(<SchemaForm schema={schema} onSubmit={vi.fn()} />)
      expect(screen.getByLabelText("HP")).toHaveValue(10)
      expect(screen.getByLabelText("Race")).toHaveValue("human")
    })
  })

  describe("initial values", () => {
    it("pre-fills from initialValues prop", () => {
      const schema = makeSchema({
        hp: { type: "integer", title: "HP", default: 10 },
        name: { type: "string", title: "Name" },
      })
      render(
        <SchemaForm
          schema={schema}
          onSubmit={vi.fn()}
          initialValues={{ hp: 25, name: "Goblin" }}
        />,
      )
      expect(screen.getByLabelText("HP")).toHaveValue(25)
      expect(screen.getByLabelText("Name")).toHaveValue("Goblin")
    })
  })

  describe("form submission", () => {
    it("calls onSubmit with correctly shaped data", async () => {
      const user = userEvent.setup()
      const onSubmit = vi.fn()
      const schema = makeSchema(
        {
          name: { type: "string", title: "Name" },
          hp: { type: "integer", title: "HP", default: 10 },
          is_magic: { type: "boolean", title: "Is Magic" },
          race: { type: "string", title: "Race", enum: ["human", "elf"], default: "human" },
        },
        ["name"],
      )
      render(<SchemaForm schema={schema} onSubmit={onSubmit} />)

      await user.type(screen.getByLabelText(/^Name/), "Goblin")
      await user.click(screen.getByLabelText("Is Magic"))
      await user.click(screen.getByRole("button", { name: /save/i }))

      expect(onSubmit).toHaveBeenCalledWith({
        name: "Goblin",
        hp: 10,
        is_magic: true,
        race: "human",
      })
    })
  })

  describe("required fields", () => {
    it("marks required fields", () => {
      const schema = makeSchema(
        {
          name: { type: "string", title: "Name" },
          hp: { type: "integer", title: "HP" },
        },
        ["name"],
      )
      render(<SchemaForm schema={schema} onSubmit={vi.fn()} />)
      // Required marker should be visible
      expect(screen.getByText("*")).toBeInTheDocument()
    })
  })
})
