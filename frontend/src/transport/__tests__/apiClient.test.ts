import { describe, it, expect } from "vitest"
import { ApiError } from "@/transport/apiClient"

describe("ApiError.detailMessage", () => {
  it("returns a plain string detail as-is", () => {
    expect(new ApiError(400, { detail: "bad request" }).detailMessage()).toBe("bad request")
  })

  it("joins pydantic {loc, msg} error arrays", () => {
    const err = new ApiError(422, {
      detail: [
        { loc: ["body", "name"], msg: "field required" },
        { loc: ["body", "hp"], msg: "must be positive" },
      ],
    })
    expect(err.detailMessage()).toBe("name: field required; hp: must be positive")
  })

  it("stringifies a non-string, non-array detail", () => {
    expect(new ApiError(400, { detail: 42 }).detailMessage()).toBe("42")
  })

  it("falls back to the generic message when there is no detail", () => {
    expect(new ApiError(500, {}).detailMessage()).toBe("API error 500")
    expect(new ApiError(500, "plain text body").detailMessage()).toBe("API error 500")
  })
})
