import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { Button } from "@/components/ui/button"
import { Swords, X } from "lucide-react"

export function ReactionPrompt() {
  const { t } = useTranslation(["game"])
  const reactionPrompt = useGameStore((s) => s.reactionPrompt)
  const submitReaction = useGameStore((s) => s.submitReaction)

  if (!reactionPrompt) return null

  return (
    <div
      data-testid="reaction-prompt"
      className="border-t border-yellow-500/30 bg-yellow-500/10 px-4 py-2"
    >
      <div className="flex items-center gap-2">
        <Swords className="size-4 text-yellow-500" />
        <span className="text-sm font-medium text-yellow-200">
          {t("game:reaction_prompt_title", { defaultValue: "Reaction!" })}
        </span>
        <div className="ml-auto flex gap-2">
          {reactionPrompt.options.map((opt) => (
            <Button
              key={opt.action_type}
              size="sm"
              variant="default"
              data-testid={`reaction-option-${opt.action_type}`}
              onClick={() => submitReaction(opt.action_type, opt.params as Record<string, unknown>)}
            >
              {opt.description}
            </Button>
          ))}
          <Button
            size="sm"
            variant="outline"
            data-testid="reaction-skip"
            onClick={() => submitReaction("skip")}
          >
            <X className="mr-1 size-3" />
            {t("game:reaction_skip", { defaultValue: "Skip" })}
          </Button>
        </div>
      </div>
    </div>
  )
}
