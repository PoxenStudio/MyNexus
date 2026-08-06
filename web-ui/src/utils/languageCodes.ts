// Book content-language codes — mirrors MyBooks' app/src/utils/languageCodes.js
// (3-letter codes; "zha" is MyBooks' own non-ISO code for Traditional
// Chinese, not a typo) so books.language stays wire-compatible with a
// future MyBooks integration. Same list worker/src/util/lang_detect.py's
// title-based detection can produce ("zho"/"zha"/"jpn"/"eng"), plus the
// rest of MyBooks' set for books whose language was set some other way
// (e.g. a future MyBooks import) — see BookDetailView.vue's language editor.
export const languageCodes: Record<string, string> = {
  zho: "中文",
  zha: "繁體中文",
  eng: "English",
  fra: "French",
  deu: "German",
  spa: "Spanish",
  rus: "Russian",
  jpn: "Japanese",
  ita: "Italian",
  por: "Portuguese",
  kor: "Korean",
  nld: "Dutch",
  ara: "Arabic",
  mon: "Mongolian",
  mnc: "满文",
  bod: "Tibetan",
  hin: "Hindi",
  tur: "Turkish",
  vie: "Vietnamese",
  tha: "Thai",
  ell: "Greek",
  pol: "Polish",
};

export const languageOptions = Object.entries(languageCodes).map(([code, name]) => ({ code, name }));

// Falls back to the raw code (e.g. an unrecognized/future value) rather
// than hiding it, so an admin can still see what's actually stored.
export function languageName(code: string): string {
  if (!code) return "";
  return languageCodes[code] ?? code;
}
