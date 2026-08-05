import { createI18n } from "vue-i18n";
import zhCN from "./zh-CN.json";
import zhTW from "./zh-TW.json";
import enUS from "./en-US.json";

export const SUPPORTED_LOCALES = ["zh-CN", "zh-TW", "en-US"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];

function detectLocale(): Locale {
  const saved = localStorage.getItem("mynexus_locale");
  if (saved && (SUPPORTED_LOCALES as readonly string[]).includes(saved)) return saved as Locale;

  const browser = navigator.language;
  if (browser.startsWith("zh-TW") || browser.startsWith("zh-HK")) return "zh-TW";
  if (browser.startsWith("zh")) return "zh-CN";
  if (browser.startsWith("en")) return "en-US";
  return "zh-CN";
}

export const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: "zh-CN",
  messages: {
    "zh-CN": zhCN,
    "zh-TW": zhTW,
    "en-US": enUS,
  },
});

export function setLocale(locale: Locale) {
  i18n.global.locale.value = locale;
  localStorage.setItem("mynexus_locale", locale);
}
