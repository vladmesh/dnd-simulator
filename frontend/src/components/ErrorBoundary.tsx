import { Component } from "react"
import type { ErrorInfo, ReactNode } from "react"

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack)
    // Report to backend so we can see it in server logs
    fetch("/api/frontend-error", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: error.message,
        stack: error.stack,
        component: info.componentStack,
      }),
    }).catch(() => {})
  }

  render() {
    if (this.state.error) {
      return (
        <div className="dark flex min-h-screen items-center justify-center bg-background p-8 text-foreground">
          <div className="max-w-lg space-y-4">
            <h1 className="text-xl font-bold text-destructive">Something went wrong</h1>
            <pre className="overflow-auto rounded border border-border bg-muted p-4 text-xs">
              {this.state.error.message}
              {"\n\n"}
              {this.state.error.stack}
            </pre>
            <button
              className="rounded bg-primary px-4 py-2 text-sm text-primary-foreground"
              onClick={() => {
                this.setState({ error: null })
                window.location.href = "/"
              }}
            >
              Back to start
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
