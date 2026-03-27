import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect } from "vitest"
import { MemoryRouter, Routes, Route } from "react-router"
import "@/i18n"
import { LandingPage } from "../LandingPage"

function setup() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/play" element={<div>SetupScreen</div>} />
        <Route path="/master" element={<div>MasterScreen</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe("LandingPage", () => {
  it("renders Play and Dungeon Master cards", () => {
    setup()
    expect(screen.getByRole("link", { name: /play/i })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /dungeon master/i })).toBeInTheDocument()
  })

  it("navigates to /play when Play is clicked", async () => {
    const user = userEvent.setup()
    setup()
    await user.click(screen.getByRole("link", { name: /play/i }))
    expect(screen.getByText("SetupScreen")).toBeInTheDocument()
  })

  it("navigates to /master when Dungeon Master is clicked", async () => {
    const user = userEvent.setup()
    setup()
    await user.click(screen.getByRole("link", { name: /dungeon master/i }))
    expect(screen.getByText("MasterScreen")).toBeInTheDocument()
  })
})
