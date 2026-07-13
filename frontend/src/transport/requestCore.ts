export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown) {
    super(`API error ${status}`)
    this.name = "ApiError"
    this.status = status
    this.body = body
  }

  detailMessage(): string {
    const detail = (this.body as { detail?: unknown } | null | undefined)?.detail
    if (Array.isArray(detail)) {
      return detail
        .map((entry) => {
          const item = entry as { loc?: unknown[]; msg?: string }
          const location = Array.isArray(item.loc) ? item.loc.slice(-1).join(".") : ""
          return `${location}: ${item.msg}`
        })
        .join("; ")
    }
    if (detail != null) return String(detail)
    return this.message
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const options: RequestInit = {
    method,
    headers: { "Content-Type": "application/json" },
  }
  if (body !== undefined) options.body = JSON.stringify(body)
  const response = await fetch(path, options)
  if (!response.ok) {
    const text = await response.text().catch(() => "")
    let parsed: unknown = text
    try {
      parsed = JSON.parse(text)
    } catch {
      // Preserve a non-JSON response body for callers.
    }
    throw new ApiError(response.status, parsed)
  }
  return response.json() as Promise<T>
}

export const get = <T>(path: string) => request<T>("GET", path)
export const post = <T>(path: string, body?: unknown) => request<T>("POST", path, body)
export const put = <T>(path: string, body?: unknown) => request<T>("PUT", path, body)
export const patch = <T>(path: string, body?: unknown) => request<T>("PATCH", path, body)
export const del = <T>(path: string) => request<T>("DELETE", path)
