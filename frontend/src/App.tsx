import { Outlet } from "react-router"
import { api } from "@/transport/apiClient"
import { wsClient } from "@/transport/wsClient"
import { useGameStore } from "@/store/gameStore"

// Expose for console testing
declare global {
  interface Window {
    api: typeof api
    ws: typeof wsClient
    store: typeof useGameStore
  }
}
window.api = api
window.ws = wsClient
window.store = useGameStore

function App() {
  return <Outlet />
}

export default App
