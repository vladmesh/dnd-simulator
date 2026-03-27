import { CatalogBrowser } from "./CatalogBrowser"

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface Props {
  catalogType: string
  onPick: (entryId: string) => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Thin wrapper around CatalogBrowser with pick mode enabled.
 * Used inside ecology layer editing to pick monsters from catalog.
 */
export function CatalogPicker({ catalogType, onPick }: Props) {
  return <CatalogBrowser catalogType={catalogType} onPick={onPick} />
}
