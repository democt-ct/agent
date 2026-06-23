export type LlmProvider = "ollama" | "openai";

export interface LlmProfileConfig {
  provider: LlmProvider;
  baseUrl: string;
  model: string;
  apiKey: string;
}

export const LLM_PROFILES = {
  // Official OpenAI endpoint. Fill in apiKey before using.
  openai: {
    provider: "openai",
    baseUrl: "https://api.openai.com/v1",
    model: "gpt-5.2",
    apiKey: ""
  },
  // Local Ollama endpoint. Usually no apiKey is required.
  ollama: {
    provider: "ollama",
    baseUrl: "http://127.0.0.1:11434/v1",
    model: "qwen3.5-9b-local:latest",
    apiKey: ""
  },
  // Any OpenAI-compatible provider.
  modelscape: {
    provider: "openai",
    baseUrl: "https://api-inference.modelscope.cn/v1",
    model: "Qwen/Qwen3-235B-A22B-Instruct-2507",
    apiKey: "ms-ada96072-1abc-43a8-bce5-5a4ba620e3a2"
  }
} satisfies Record<string, LlmProfileConfig>;

export const ACTIVE_LLM_PROFILE: keyof typeof LLM_PROFILES = "ollama";

export function getActiveLlmProfileName(): keyof typeof LLM_PROFILES {
  return ACTIVE_LLM_PROFILE;
}

export function getActiveLlmProfile(): LlmProfileConfig {
  return LLM_PROFILES[ACTIVE_LLM_PROFILE];
}

export interface AmapConfig {
  browserKey: string;
  securityJsCode: string;
  webServiceKey: string;
  defaultCity: string;
  defaultCenter: [number, number];
}

export const AMAP_CONFIG: AmapConfig = {
  // AMap JS API browser key for map rendering and client-side POI search.
  browserKey: "8fce01674d324cdaadc2a236215ae942",
  // AMap security JS code, required only when enabled in the AMap console.
  securityJsCode: "02146b49959c4d8209f11b3c404506e7",
  // AMap Web Service key. Keep it server-side; do not expose it to browsers.
  webServiceKey: "54a6190658e4c5cdff928f2dcbdbdd3f",
  defaultCity: "\u7ef5\u9633",
  defaultCenter: [104.679127, 31.467673]
};

export function getPublicAmapConfig() {
  return {
    enabled: Boolean(AMAP_CONFIG.browserKey),
    browserKey: AMAP_CONFIG.browserKey,
    securityJsCode: AMAP_CONFIG.securityJsCode,
    defaultCity: AMAP_CONFIG.defaultCity,
    defaultCenter: AMAP_CONFIG.defaultCenter
  };
}
