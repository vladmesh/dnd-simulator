import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter, Routes, Route, Navigate } from "react-router"
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
import { LandingPage } from "./components/LandingPage"
import { SetupScreen } from "./components/setup/SetupScreen"
import { GameScreen } from "./components/game/GameScreen"
import { MasterScreen } from "./components/master/MasterScreen"
import { SessionView } from "./components/master/SessionView"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route element={<App />}>
            <Route index element={<LandingPage />} />
            <Route path="play" element={<SetupScreen />} />
            <Route path="play/:sessionId" element={<GameScreen />} />
            <Route path="master" element={<MasterScreen />} />
            <Route path="master/:sessionId" element={<SessionView />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
)
