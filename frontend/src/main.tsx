import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter, Routes, Route } from "react-router"
import "./index.css"
import "./i18n"

// Report uncaught errors to backend for server-side debugging
function reportError(message: string, stack?: string) {
  fetch("/api/frontend-error", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, stack }),
  }).catch(() => {})
}
window.addEventListener("error", (e) => reportError(e.message, e.error?.stack))
window.addEventListener("unhandledrejection", (e) => reportError(String(e.reason), e.reason?.stack))
import App from "./App"
import { ErrorBoundary } from "./components/ErrorBoundary"
import { SetupScreen } from "./components/setup/SetupScreen"
import { GameScreen } from "./components/game/GameScreen"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route element={<App />}>
            <Route index element={<SetupScreen />} />
            <Route path="play/:sessionId" element={<GameScreen />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
)
