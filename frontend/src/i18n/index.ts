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

i18n.use(initReactI18next).init({
  resources,
  lng: navigator.language.startsWith("ru") ? "ru" : "en",
  fallbackLng: "en",
  defaultNS,
  interpolation: { escapeValue: false },
})

export default i18n
