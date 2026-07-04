import { describe, it, expect } from "vitest"
import { decodeLocalized, encodeLocalized } from "../localizedCodec"

describe("localizedCodec", () => {
  it("decodes {lang: text} to the flat string for that lang", () => {
    expect(decodeLocalized({ en: "hi", ru: "прив" }, "en")).toBe("hi")
    expect(decodeLocalized({ en: "hi" }, "ru")).toBe("")
  })

  it("decodes a plain string as-is", () => {
    expect(decodeLocalized("legacy", "en")).toBe("legacy")
  })

  it("decodes missing/non-object to empty string", () => {
    expect(decodeLocalized(undefined, "en")).toBe("")
    expect(decodeLocalized(null, "en")).toBe("")
  })

  it("encodes a flat string back into {lang: text}", () => {
    expect(encodeLocalized("hi", "en")).toEqual({ en: "hi" })
  })

  it("round-trips", () => {
    expect(decodeLocalized(encodeLocalized("x", "ru"), "ru")).toBe("x")
  })
})
