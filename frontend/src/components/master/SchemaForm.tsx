import { useEffect, useCallback } from "react"
import { useForm, useFieldArray, Controller } from "react-hook-form"
import type { UseFormRegister, Control, FieldValues, Path } from "react-hook-form"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import type { JsonSchema, RefOption } from "@/types/api"
import { Plus, Trash2 } from "lucide-react"
import { RefSelect } from "./RefSelect"

// ---------------------------------------------------------------------------
// Schema resolution helpers
// ---------------------------------------------------------------------------

/** Resolve a $ref like "#/$defs/Foo" against the root schema's $defs. */
function resolveRef(ref: string, rootDefs: Record<string, JsonSchema>): JsonSchema {
  const name = ref.replace("#/$defs/", "")
  const resolved = rootDefs[name]
  if (!resolved) throw new Error(`Unresolved $ref: ${ref}`)
  return resolved
}

/** Resolve a property schema: follow $ref, unwrap anyOf-with-null. */
function resolveProperty(
  prop: JsonSchema,
  rootDefs: Record<string, JsonSchema>,
): JsonSchema {
  // Follow $ref
  if (prop.$ref) {
    const resolved = resolveRef(prop.$ref, rootDefs)
    // Merge title/default from the referencing property
    return { ...resolved, title: prop.title || resolved.title, default: prop.default ?? resolved.default }
  }
  // Unwrap anyOf [{type: X}, {type: null}] → {type: X}
  if (prop.anyOf) {
    const nonNull = prop.anyOf.filter((s) => s.type !== "null")
    if (nonNull.length === 1) {
      const unwrapped = nonNull[0]
      // If the non-null branch is a $ref, resolve it
      if (unwrapped.$ref) {
        const resolved = resolveRef(unwrapped.$ref, rootDefs)
        return { ...resolved, title: prop.title || resolved.title, default: prop.default ?? resolved.default }
      }
      // Check if it's an array with $ref items
      if (unwrapped.type === "array" && unwrapped.items?.$ref) {
        const resolvedItems = resolveRef(unwrapped.items.$ref, rootDefs)
        return {
          ...unwrapped,
          items: resolvedItems,
          title: prop.title || unwrapped.title,
          default: prop.default ?? unwrapped.default,
        }
      }
      return { ...unwrapped, title: prop.title || unwrapped.title, default: prop.default ?? unwrapped.default }
    }
  }
  return prop
}

/** Check if a schema represents a localized text field (object with additionalProperties: {type: string}). */
function isLocalizedText(schema: JsonSchema): boolean {
  if (schema["x-localized"]) return true
  if (schema.type !== "object") return false
  if (schema.properties && Object.keys(schema.properties).length > 0) return false
  const ap = schema.additionalProperties
  return typeof ap === "object" && ap.type === "string"
}

/** Build default values from a JSON schema. */
function buildDefaults(
  schema: JsonSchema,
  rootDefs: Record<string, JsonSchema>,
): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  const props = schema.properties ?? {}
  for (const [key, rawProp] of Object.entries(props)) {
    const prop = resolveProperty(rawProp, rootDefs)
    if (prop.default !== undefined) {
      result[key] = prop.default
    } else if (prop.type === "boolean") {
      result[key] = false
    } else if (prop.type === "array") {
      result[key] = []
    }
  }
  return result
}

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
  const rootDefs = schema.$defs ?? {}
  const defaults = buildDefaults(schema, rootDefs)
  const merged = { ...defaults, ...initialValues }

  // For localized text fields in initialValues, unwrap {lang: value} → value
  const formDefaults: Record<string, unknown> = {}
  const props = schema.properties ?? {}
  for (const [key, rawProp] of Object.entries(props)) {
    const prop = resolveProperty(rawProp, rootDefs)
    const val = merged[key]
    if (isLocalizedText(prop) && typeof val === "object" && val !== null) {
      formDefaults[key] = (val as Record<string, string>)[lang] ?? ""
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
          result[key] = { [lang]: val as string }
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
      <div className="space-y-1">
        <Label htmlFor={name}>
          {title}
          {required && <span className="text-destructive ml-1">*</span>}
        </Label>
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
      </div>
    )
  }

  // Enum → native select
  if (schema.enum) {
    return (
      <div className="space-y-1">
        <Label htmlFor={name}>
          {title}
          {required && <span className="text-destructive ml-1">*</span>}
        </Label>
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
      </div>
    )
  }

  // Localized text
  if (isLocalizedText(schema)) {
    return (
      <div className="space-y-1">
        <Label htmlFor={name}>
          {title}
          {required && <span className="text-destructive ml-1">*</span>}
        </Label>
        <Input
          id={name}
          type="text"
          {...register(name as Path<FieldValues>)}
        />
      </div>
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
      <div className="space-y-1">
        <Label htmlFor={name}>
          {title}
          {required && <span className="text-destructive ml-1">*</span>}
        </Label>
        <Input
          id={name}
          type="text"
          placeholder="comma-separated"
          {...register(name as Path<FieldValues>)}
        />
      </div>
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
      <div className="space-y-1">
        <Label htmlFor={name}>
          {title}
          {required && <span className="text-destructive ml-1">*</span>}
        </Label>
        <Input
          id={name}
          type="number"
          {...register(name as Path<FieldValues>, { valueAsNumber: true })}
        />
      </div>
    )
  }

  // Default: string
  return (
    <div className="space-y-1">
      <Label htmlFor={name}>
        {title}
        {required && <span className="text-destructive ml-1">*</span>}
      </Label>
      <Input
        id={name}
        type="text"
        {...register(name as Path<FieldValues>)}
      />
    </div>
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

  // Build defaults for a new row
  const rowDefaults: Record<string, unknown> = {}
  for (const [key, rawProp] of Object.entries(itemProps)) {
    const prop = resolveProperty(rawProp, rootDefs)
    if (prop.default !== undefined) {
      rowDefaults[key] = prop.default
    } else if (prop.type === "boolean") {
      rowDefaults[key] = false
    }
  }

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
