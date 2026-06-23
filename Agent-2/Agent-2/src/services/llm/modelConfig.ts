import {
  getActiveLlmProfile,
  getActiveLlmProfileName,
  type LlmProvider
} from "../../config/llm";
import type { Env } from "../../types";

export interface LlmRuntimeConfig {
  provider: LlmProvider;
  baseUrl: string;
  model: string;
  apiKey?: string;
  profileName: string;
}

function trimTrailingSlash(value: string): string {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

function normalizeApiKey(value: string): string | undefined {
  const trimmedValue = value.trim();
  return trimmedValue ? trimmedValue : undefined;
}

export function resolveLlmRuntimeConfig(_env: Env): LlmRuntimeConfig {
  const activeProfile = getActiveLlmProfile();
  const normalizedBaseUrl = trimTrailingSlash(activeProfile.baseUrl);
  return {
    provider: activeProfile.provider,
    baseUrl: normalizedBaseUrl,
    model: activeProfile.model.trim(),
    apiKey: normalizeApiKey(activeProfile.apiKey),
    profileName: getActiveLlmProfileName()
  };
}

export function isLlmConfigured(env: Env): boolean {
  const config = resolveLlmRuntimeConfig(env);
  return config.provider === "ollama" || Boolean(config.apiKey);
}

export function getDefaultRequirementStrategy(env: Env): "rule" | "llm" {
  return isLlmConfigured(env) ? "llm" : "rule";
}

export function getDefaultGeneratorType(env: Env): "template" | "agent" {
  return isLlmConfigured(env) ? "agent" : "template";
}
