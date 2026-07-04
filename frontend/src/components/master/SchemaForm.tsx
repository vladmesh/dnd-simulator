import { useEffect, useCallback, useMemo } from "react"
import { useForm, useFieldArray, Controller } from "react-hook-form"
import type { UseFormRegister, Control, FieldValues, Path } from "react-hook-form"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import type { JsonSchema, RefOption } from "@/types/api"
import { Plus, Trash2 } from "lucide-react"
import { RefSelect } from "./RefSelect"
import { FieldShell } from "./FieldShell"
import { resolveProperty, isLocalizedText, buildDefaults } from "./schemaResolve"
import { decodeLocalized, encodeLocalized } from "./localizedCodec"

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface SchemaFormProps {
  schema: JsonSchema
  onSubmit: (data: Record<string, unknown>) => void
  initialValues?: Record<string, unknown>
  lang?: string
  worldId?: string
  fetchRefs?: (worldId: string, refType: string) => Promise<RefOption[]>
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SchemaForm({
  schema,
  onSubmit,
  initialValues,
  lang = "en",
  worldId,
  fetchRefs,
}: SchemaFormProps) {
  const rootDefs = useMemo(() => schema.$defs ?? {}, [schema])
  const defaults = buildDefaults(schema, rootDefs)
  const merged = { ...defaults, ...initialValues }

  // For localized text fields in initialValues, unwrap {lang: value} → value
  const formDefaults: Record<string, unknown> = {}
  const props = useMemo(() => schema.properties ?? {}, [schema])
  for (const [key, rawProp] of Object.entries(props)) {
    const prop = resolveProperty(rawProp, rootDefs)
    const val = merged[key]
    if (isLocalizedText(prop) && typeof val === "object" && val !== null) {
      formDefaults[key] = decodeLocalized(val, lang)
    } else {
      formDefaults[key] = val
    }
  }

  const { register, control, handleSubmit, reset } = useForm({
    defaultValues: formDefaults as FieldValues,
  })

  useEffect(() => {
    reset(formDefaults as FieldValues)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialValues, reset])

  const onFormSubmit = useCallback(
    (data: FieldValues) => {
      // Post-process: wrap localized text, convert types
      const result: Record<string, unknown> = {}
      for (const [key, rawProp] of Object.entries(props)) {
        const prop = resolveProperty(rawProp, rootDefs)
        const val = data[key]

        if (isLocalizedText(prop)) {
          result[key] = encodeLocalized(val as string, lang)
        } else if (prop.type === "array" && prop.items?.type === "string") {
          // Comma-separated string → array
          result[key] =
            typeof val === "string"
              ? val
                  .split(",")
                  .map((s: string) => s.trim())
                  .filter(Boolean)
              : val ?? []
        } else if (prop.type === "integer" || prop.type === "number") {
          result[key] = val === "" || val === undefined ? undefined : Number(val)
        } else {
          result[key] = val
        }
      }
      onSubmit(result)
    },
    [onSubmit, props, rootDefs, lang],
  )

  return (
    <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-4">
      {Object.entries(props).map(([key, rawProp]) => {
        const prop = resolveProperty(rawProp, rootDefs)
        const required = schema.required?.includes(key) ?? false
        return (
          <SchemaField
            key={key}
            name={key}
            schema={prop}
            rootDefs={rootDefs}
            required={required}
            register={register}
            control={control}
            lang={lang}
            worldId={worldId}
            fetchRefs={fetchRefs}
          />
        )
      })}
      <Button type="submit">Save</Button>
    </form>
  )
}

// ---------------------------------------------------------------------------
// Field renderer
// ---------------------------------------------------------------------------

interface SchemaFieldProps {
  name: string
  schema: JsonSchema
  rootDefs: Record<string, JsonSchema>
  required: boolean
  register: UseFormRegister<FieldValues>
  control: Control<FieldValues>
  lang: string
  worldId?: string
  fetchRefs?: (worldId: string, refType: string) => Promise<RefOption[]>
}

function SchemaField({
  name,
  schema,
  rootDefs,
  required,
  register,
  control,
  lang,
  worldId,
  fetchRefs,
}: SchemaFieldProps) {
  const title = schema.title ?? name

  // x-ref-type → RefSelect
  if (schema["x-ref-type"] && worldId && fetchRefs) {
    return (
      <FieldShell htmlFor={name} label={title} required={required}>
        <Controller
          name={name as Path<FieldValues>}
          control={control}
          render={({ field }) => (
            <RefSelect
              id={name}
              worldId={worldId}
              refType={schema["x-ref-type"]!}
              value={field.value as string}
              onChange={field.onChange}
              fetchRefs={fetchRefs}
            />
          )}
        />
      </FieldShell>
    )
  }

  // Enum → native select
  if (schema.enum) {
    return (
      <FieldShell htmlFor={name} label={title} required={required}>
        <select
          id={name}
          {...register(name as Path<FieldValues>)}
          className="flex h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm"
        >
          <option value="">—</option>
          {schema.enum.map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
      </FieldShell>
    )
  }

  // Localized text
  if (isLocalizedText(schema)) {
    return (
      <FieldShell htmlFor={name} label={title} required={required}>
        <Input id={name} type="text" {...register(name as Path<FieldValues>)} />
      </FieldShell>
    )
  }

  // Array of objects
  if (schema.type === "array" && schema.items?.type === "object") {
    return (
      <ArrayOfObjectsField
        name={name}
        schema={schema}
        rootDefs={rootDefs}
        register={register}
        control={control}
        lang={lang}
        worldId={worldId}
        fetchRefs={fetchRefs}
      />
    )
  }

  // Array of strings → comma-separated input
  if (schema.type === "array" && schema.items?.type === "string") {
    return (
      <FieldShell htmlFor={name} label={title} required={required}>
        <Input
          id={name}
          type="text"
          placeholder="comma-separated"
          {...register(name as Path<FieldValues>)}
        />
      </FieldShell>
    )
  }

  // Nested object (non-localized, with known properties)
  if (schema.type === "object" && schema.properties) {
    return (
      <fieldset className="space-y-3 rounded-lg border border-input p-3">
        <legend className="px-1 text-sm font-medium">{title}</legend>
        {Object.entries(schema.properties).map(([childKey, childRawProp]) => {
          const childProp = resolveProperty(childRawProp, rootDefs)
          return (
            <SchemaField
              key={childKey}
              name={`${name}.${childKey}`}
              schema={childProp}
              rootDefs={rootDefs}
              required={schema.required?.includes(childKey) ?? false}
              register={register}
              control={control}
              lang={lang}
              worldId={worldId}
              fetchRefs={fetchRefs}
            />
          )
        })}
      </fieldset>
    )
  }

  // Boolean
  if (schema.type === "boolean") {
    return (
      <div className="flex items-center gap-2">
        <input
          id={name}
          type="checkbox"
          {...register(name as Path<FieldValues>)}
          className="h-4 w-4 rounded border-input"
        />
        <Label htmlFor={name}>{title}</Label>
      </div>
    )
  }

  // Integer / number
  if (schema.type === "integer" || schema.type === "number") {
    return (
      <FieldShell htmlFor={name} label={title} required={required}>
        <Input
          id={name}
          type="number"
          {...register(name as Path<FieldValues>, { valueAsNumber: true })}
        />
      </FieldShell>
    )
  }

  // Default: string
  return (
    <FieldShell htmlFor={name} label={title} required={required}>
      <Input id={name} type="text" {...register(name as Path<FieldValues>)} />
    </FieldShell>
  )
}

// ---------------------------------------------------------------------------
// Array of objects sub-component
// ---------------------------------------------------------------------------

interface ArrayOfObjectsFieldProps {
  name: string
  schema: JsonSchema
  rootDefs: Record<string, JsonSchema>
  register: UseFormRegister<FieldValues>
  control: Control<FieldValues>
  lang: string
  worldId?: string
  fetchRefs?: (worldId: string, refType: string) => Promise<RefOption[]>
}

function ArrayOfObjectsField({
  name,
  schema,
  rootDefs,
  register,
  control,
  lang,
  worldId,
  fetchRefs,
}: ArrayOfObjectsFieldProps) {
  const { fields, append, remove } = useFieldArray({
    control,
    name: name as Path<FieldValues>,
  })

  const itemSchema = schema.items!
  const itemProps = itemSchema.properties ?? {}
  const title = schema.title ?? name

  // Defaults for a new row — same builder as the top-level form.
  const rowDefaults = buildDefaults(itemSchema, rootDefs)

  return (
    <fieldset className="space-y-3 rounded-lg border border-input p-3">
      <legend className="px-1 text-sm font-medium">{title}</legend>
      {fields.map((field, index) => (
        <div key={field.id} className="space-y-2 rounded border border-input/50 p-2">
          {Object.entries(itemProps).map(([childKey, childRawProp]) => {
            const childProp = resolveProperty(childRawProp, rootDefs)
            return (
              <SchemaField
                key={childKey}
                name={`${name}.${index}.${childKey}`}
                schema={childProp}
                rootDefs={rootDefs}
                required={itemSchema.required?.includes(childKey) ?? false}
                register={register}
                control={control}
                lang={lang}
                worldId={worldId}
                fetchRefs={fetchRefs}
              />
            )
          })}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => remove(index)}
          >
            <Trash2 className="mr-1 h-3 w-3" />
            Remove
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => append(rowDefaults)}
      >
        <Plus className="mr-1 h-3 w-3" />
        Add
      </Button>
    </fieldset>
  )
}
