import type { ReactNode } from "react"
import { Label } from "@/components/ui/label"

interface FieldShellProps {
  htmlFor: string
  label: string
  required: boolean
  children: ReactNode
}

/** Standard labelled field wrapper: `<Label>` (with required marker) above the control. */
export function FieldShell({ htmlFor, label, required, children }: FieldShellProps) {
  return (
    <div className="space-y-1">
      <Label htmlFor={htmlFor}>
        {label}
        {required && <span className="text-destructive ml-1">*</span>}
      </Label>
      {children}
    </div>
  )
}
