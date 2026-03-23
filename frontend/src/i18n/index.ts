import i18n from "i18next"
import { initReactI18next } from "react-i18next"

import commonEn from "./locales/en/common.json"
import setupEn from "./locales/en/setup.json"
import gameEn from "./locales/en/game.json"

import commonRu from "./locales/ru/common.json"
import setupRu from "./locales/ru/setup.json"
import gameRu from "./locales/ru/game.json"

export const defaultNS = "common"
export const resources = {
  en: { common: commonEn, setup: setupEn, game: gameEn },
  ru: { common: commonRu, setup: setupRu, game: gameRu },
} as const

function detectLanguage(): string {
  const saved = localStorage.getItem("i18n_lang")
  if (saved && (saved === "en" || saved === "ru")) return saved
  return navigator.language.startsWith("ru") ? "ru" : "en"
}

i18n.use(initReactI18next).init({
  resources,
  lng: detectLanguage(),
  fallbackLng: "en",
  defaultNS,
  interpolation: { escapeValue: false },
})

// Persist language changes
i18n.on("languageChanged", (lng) => {
  localStorage.setItem("i18n_lang", lng)
})

export default i18n
