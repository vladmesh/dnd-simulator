import { Button } from "@/components/ui/button"

interface ActionDrawerProps {
  drawerKey: string
  icon: React.ReactNode
  count: number
  isOpen: boolean
  onToggle: () => void
  disabled: boolean
  title?: string
  children: React.ReactNode
}

export function ActionDrawer({ drawerKey, icon, count, isOpen, onToggle, disabled, title, children }: ActionDrawerProps) {
  return (
    <div className="relative">
      <Button
        size="sm"
        variant="secondary"
        disabled={disabled}
        data-drawer={drawerKey}
        onClick={onToggle}
        className="gap-1"
        title={title}
      >
        {icon}
        <span className="text-xs">{count}</span>
      </Button>
      {isOpen && (
        <div
          data-drawer-popup={drawerKey}
          className="absolute bottom-full left-0 z-10 mb-1 min-w-[200px] max-w-[280px] rounded border border-border bg-popover p-1 shadow-md"
        >
          {children}
        </div>
      )}
    </div>
  )
}
