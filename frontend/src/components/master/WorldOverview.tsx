import { useTranslation } from "react-i18next"
import { api } from "@/transport/apiClient"
import type { Nation, Region, Settlement, WorldStateResponse } from "@/types/api"
import { EditableStatsTable } from "./EditableStatsTable"
import type { ColumnDef } from "./EditableStatsTable"

interface Props {
  sessionId: string
  worldState: WorldStateResponse
}

export function WorldOverview({ sessionId, worldState }: Props) {
  const { t } = useTranslation(["master"])
  const regionMap = Object.fromEntries(worldState.regions.map((r) => [r.id, r.name]))

  const regionColumns: ColumnDef<Region>[] = [
    { key: "id", label: t("master:col_id"), mono: true },
    { key: "name", label: t("master:col_name") },
    { key: "terrain", label: t("master:col_terrain"), render: (r) => r.terrain ?? "—" },
    {
      key: "weather",
      label: t("master:col_weather"),
      render: (r) => `${r.weather.condition}, ${r.weather.temperature}°`,
    },
  ]

  const nationColumns: ColumnDef<Nation>[] = [
    { key: "id", label: t("master:col_id"), mono: true },
    { key: "name", label: t("master:col_name") },
    { key: "wealth", label: t("master:col_wealth"), parse: parseFloat, inputProps: { step: "0.1" } },
    { key: "military", label: t("master:col_military"), parse: parseFloat, inputProps: { step: "0.1" } },
    {
      key: "stability",
      label: t("master:col_stability"),
      parse: parseFloat,
      inputProps: { step: "1", min: "0", max: "100" },
    },
  ]

  const settlementColumns: ColumnDef<Settlement>[] = [
    { key: "id", label: t("master:col_id"), mono: true },
    { key: "name", label: t("master:col_name") },
    { key: "region_id", label: t("master:col_region"), render: (s) => regionMap[s.region_id] ?? "—" },
    {
      key: "population",
      label: t("master:col_population"),
      parse: (raw) => parseInt(raw, 10),
      width: "w-24",
    },
    {
      key: "prosperity",
      label: t("master:col_prosperity"),
      parse: parseFloat,
      inputProps: { step: "1", min: "0", max: "100" },
    },
    {
      key: "defenses",
      label: t("master:col_defenses"),
      parse: parseFloat,
      inputProps: { step: "1", min: "0", max: "100" },
    },
  ]

  return (
    <div className="space-y-8">
      <EditableStatsTable
        title={t("master:regions")}
        columns={regionColumns}
        rows={worldState.regions}
        emptyMessage={t("master:no_regions")}
      />
      <EditableStatsTable
        title={t("master:nations")}
        columns={nationColumns}
        rows={worldState.nations}
        emptyMessage={t("master:no_nations")}
        patch={(id, values) => api.master.patchNation(sessionId, id, values)}
      />
      <EditableStatsTable
        title={t("master:settlements")}
        columns={settlementColumns}
        rows={worldState.settlements}
        emptyMessage={t("master:no_settlements")}
        patch={(id, values) => api.master.patchSettlement(sessionId, id, values)}
      />
    </div>
  )
}
