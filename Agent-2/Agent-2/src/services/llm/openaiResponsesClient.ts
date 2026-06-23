import type { Env } from "../../types";
import { isLlmConfigured, resolveLlmRuntimeConfig } from "./modelConfig";

interface ResponsesApiOutput {
  output_text?: string;
}

interface ChatCompletionsOutput {
  choices?: Array<{
    message?: {
      content?: string;
    };
  }>;
}

export class OpenAIResponsesClient {
  constructor(private readonly env: Env) {}

  private getConfig() {
    return resolveLlmRuntimeConfig(this.env);
  }

  isEnabled(): boolean {
    return isLlmConfigured(this.env);
  }

  private buildHeaders(apiKey?: string): HeadersInit {
    return {
      "content-type": "application/json",
      ...(apiKey ? { authorization: `Bearer ${apiKey}` } : {})
    };
  }

  private async callResponsesApi<T>(input: {
    system: string;
    user: string;
    schemaName: string;
    schema: Record<string, unknown>;
  }): Promise<T> {
    const config = this.getConfig();
    const apiKey = config.apiKey;
    if (config.provider !== "ollama" && !apiKey) {
      throw new Error("LLM API key is not configured");
    }

    const response = await fetch(`${config.baseUrl}/responses`, {
      method: "POST",
      headers: this.buildHeaders(apiKey),
      body: JSON.stringify({
        model: config.model,
        input: [
          {
            role: "system",
            content: [{ type: "input_text", text: input.system }]
          },
          {
            role: "user",
            content: [{ type: "input_text", text: input.user }]
          }
        ],
        text: {
          format: {
            type: "json_schema",
            name: input.schemaName,
            strict: true,
            schema: input.schema
          }
        }
      })
    });

    if (!response.ok) {
      const message = await response.text();
      throw new Error(`responses api error: ${response.status} ${message}`);
    }

    const data = (await response.json()) as ResponsesApiOutput;
    if (!data.output_text) {
      throw new Error("responses api missing output_text");
    }

    return JSON.parse(data.output_text) as T;
  }

  private async callChatCompletionsApi<T>(input: {
    system: string;
    user: string;
  }): Promise<T> {
    const config = this.getConfig();
    const apiKey = config.apiKey;
    if (config.provider !== "ollama" && !apiKey) {
      throw new Error("LLM API key is not configured");
    }

    const response = await fetch(`${config.baseUrl}/chat/completions`, {
      method: "POST",
      headers: this.buildHeaders(apiKey),
      body: JSON.stringify({
        model: config.model,
        messages: [
          { role: "system", content: input.system },
          { role: "user", content: input.user }
        ],
        temperature: 0.2,
        response_format: { type: "json_object" }
      })
    });

    if (!response.ok) {
      const message = await response.text();
      throw new Error(`chat completions api error: ${response.status} ${message}`);
    }

    const data = (await response.json()) as ChatCompletionsOutput;
    const content = data.choices?.[0]?.message?.content;
    if (!content) {
      throw new Error("chat completions api missing message content");
    }

    return JSON.parse(content) as T;
  }

  async createStructuredJson<T>(input: {
    system: string;
    user: string;
    schemaName: string;
    schema: Record<string, unknown>;
  }): Promise<T> {
    try {
      return await this.callResponsesApi<T>(input);
    } catch (error) {
      const shouldFallback = this.getConfig().provider === "ollama";

      if (!shouldFallback) {
        throw error;
      }

      const schemaAwareUserPrompt = [
        input.user,
        "",
        "Return valid JSON only.",
        `Schema name: ${input.schemaName}`,
        `Schema: ${JSON.stringify(input.schema)}`
      ].join("\n");

      return this.callChatCompletionsApi<T>({
        system: input.system,
        user: schemaAwareUserPrompt
      });
    }
  }
}
