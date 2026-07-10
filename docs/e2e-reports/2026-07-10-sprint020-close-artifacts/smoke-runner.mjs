import { createRequire } from "node:module"
import fs from "node:fs/promises"
import path from "node:path"

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url))
const { chromium } = require("playwright")

const BASE = "http://localhost:5173"
const API = "http://localhost:8001/api"
const OUT = "docs/e2e-reports/2026-07-10-sprint020-close-artifacts"

const steps = []
const sessions = []

async function api(method, url, body) {
  const res = await fetch(`${API}${url}`, {
    method,
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    throw new Error(`${method} ${url} failed ${res.status}: ${await res.text()}`)
  }
  return res.status === 204 ? null : res.json()
}

async function createCharacter(world, charClass, overrides = {}) {
  const session = await api("POST", "/master/sessions", { world_name: world, lang: "en" })
  sessions.push(session.session_id)
  const payload = {
    name: overrides.name ?? `Smoke ${charClass}`,
    race: "human",
    char_class: charClass,
    alignment: "true_neutral",
    start_location: overrides.start_location ?? "combat_floor",
    ability_scores: overrides.ability_scores ?? { str: 15, dex: 11, con: 14, int: 10, wis: 10, cha: 9 },
    ...overrides.extra,
  }
  const player = await api("POST", `/player/sessions/${session.session_id}/character`, payload)
  return { sessionId: session.session_id, playerId: player.player_id }
}

async function cleanup() {
  for (const sid of sessions.reverse()) {
    try {
      await api("DELETE", `/master/sessions/${sid}`)
    } catch {
      // Best-effort cleanup; report keeps the session ids if deletion fails.
    }
  }
}

async function waitStore(page, predicate, timeout = 15000) {
  await page.waitForFunction(predicate, undefined, { timeout })
}

async function shot(page, name) {
  const file = path.join(OUT, `${name}.png`)
  await page.screenshot({ path: file, fullPage: true })
  return file
}

function record(name, status, notes, screenshot) {
  steps.push({ name, status, notes, screenshot })
}

async function openGame(page, sessionId, playerId) {
  await page.goto(BASE)
  await page.evaluate(
    ([sid, pid]) => localStorage.setItem(`player_id:${sid}`, pid),
    [sessionId, playerId],
  )
  await page.goto(`${BASE}/play/${sessionId}`)
  await waitStore(page, () => window.store?.getState().player != null)
}

async function scenarioSetup(page) {
  await page.goto(BASE)
  await page.getByRole("link", { name: /play/i }).click()
  await page.getByRole("button", { name: /new session/i }).first().click()
  await page.locator("form input").first().fill("Smoke UI Fighter")
  await page.getByTestId("fighting-style-select").selectOption("defense")
  await page.getByRole("button", { name: /create character/i }).click()
  await page.waitForURL(/\/play\/[a-z0-9]+/, { timeout: 20000 })
  await waitStore(page, () => window.store?.getState().player?.name === "Smoke UI Fighter")
  const state = await page.evaluate(() => window.store.getState())
  sessions.push(state.sessionId)
  record("session + character", "pass", `Created ${state.player.name}, AC ${state.player.ac}`, await shot(page, "01-session-character"))
}

async function scenarioCombat(page) {
  const { sessionId, playerId } = await createCharacter("level_up_test", "fighter", {
    start_location: "arena_floor",
    extra: { fighting_style: "defense" },
  })
  await openGame(page, sessionId, playerId)
  await api("PATCH", `/master/sessions/${sessionId}/creatures/xp_dummy`, { current_hp: 8, xp_value: 50 })
  await page.getByRole("button", { name: /attack/i }).first().click()
  await waitStore(page, () => {
    const s = window.store.getState()
    return s.mode === "combat" || s.logEntries?.some((e) => e.event?.event_type === "entity_attack")
  })
  const state = await page.evaluate(() => window.store.getState())
  record("combat attack", "pass", `Mode ${state.mode}; log entries ${state.log.length}`, await shot(page, "02-combat-attack"))
}

async function scenarioEquipment(page) {
  const { sessionId, playerId } = await createCharacter("level_up_test", "fighter", {
    start_location: "arena_floor",
    extra: { fighting_style: "defense" },
  })
  await api("POST", `/master/sessions/${sessionId}/creatures/${playerId}/items`, {
    name: "Smoke Rapier",
    type: "weapon",
    weapon_id: "smoke_rapier",
    attack_name: "Smoke Rapier",
    category: "martial",
    damage: [{ dice: "1d8", type: "piercing" }],
    ability: "dex",
  })
  await openGame(page, sessionId, playerId)
  await page.getByRole("button", { name: /^equip$/i }).first().click()
  await waitStore(page, () => {
    const equipped = window.store.getState().player?.equipped ?? []
    return equipped.some((item) => item.name === "Smoke Rapier")
  })
  record("equipment", "pass", "Equipped Smoke Rapier from bag through UI", await shot(page, "03-equipment"))
}

async function scenarioLevelUp(page) {
  const { sessionId, playerId } = await createCharacter("level_up_test", "paladin", {
    start_location: "arena_floor",
    ability_scores: { str: 15, dex: 10, con: 14, int: 10, wis: 10, cha: 13 },
  })
  await api("PATCH", `/master/sessions/${sessionId}/creatures/xp_dummy`, { current_hp: 1, ac: 1 })
  await openGame(page, sessionId, playerId)
  await page.getByRole("button", { name: /attack/i }).first().click()
  await waitStore(page, () => window.store.getState().player?.level_up_available === true, 20000)
  await page.getByTestId("level-up-modal").waitFor({ timeout: 10000 })
  await page.getByLabel(/fighting style/i).selectOption("dueling")
  await page.getByRole("button", { name: /^ok$/i }).click()
  await waitStore(page, () => window.store.getState().player?.level === 2)
  const player = await page.evaluate(() => window.store.getState().player)
  record("level-up", "pass", `Level ${player.level}, HP ${player.max_hp}, resources ${player.resource_pools?.length ?? 0}`, await shot(page, "04-level-up"))
}

async function scenarioWait(page) {
  const { sessionId, playerId } = await createCharacter("test_vale", "fighter", {
    start_location: "crossroads_tavern",
    ability_scores: { str: 12, dex: 12, con: 12, int: 10, wis: 10, cha: 10 },
    extra: { fighting_style: "defense" },
  })
  const creatures = await api("GET", `/master/sessions/${sessionId}/creatures`)
  for (const c of creatures) {
    if (c.id !== playerId && c.location_id === "village_square") {
      await api("DELETE", `/master/sessions/${sessionId}/creatures/${c.id}`).catch(() => {})
    }
  }
  await openGame(page, sessionId, playerId)
  const before = await page.evaluate(() => window.store.getState().gameTime)
  await page.getByRole("button", { name: /wait/i }).click()
  await waitStore(page, (oldTime) => window.store.getState().gameTime !== oldTime, 20000)
  const after = await page.evaluate(() => window.store.getState().gameTime, before)
  record("wait / time", "pass", `Time changed from ${JSON.stringify(before)} to ${JSON.stringify(after)}`, await shot(page, "05-wait-time"))
}

async function main() {
  await fs.mkdir(OUT, { recursive: true })
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  page.setDefaultTimeout(20000)
  try {
    for (const fn of [scenarioSetup, scenarioCombat, scenarioEquipment, scenarioLevelUp, scenarioWait]) {
      try {
        await fn(page)
      } catch (error) {
        const screenshot = await shot(page, `failure-${steps.length + 1}`)
        record(fn.name.replace("scenario", "").toLowerCase(), "fail", error instanceof Error ? error.message : String(error), screenshot)
      }
    }
  } finally {
    await browser.close()
    await cleanup()
  }
  await fs.writeFile(path.join(OUT, "smoke-results.json"), JSON.stringify({ steps }, null, 2))
  const failed = steps.filter((s) => s.status !== "pass")
  if (failed.length > 0) {
    console.error(JSON.stringify({ failed }, null, 2))
    process.exit(1)
  }
  console.log(JSON.stringify({ steps }, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
