import type { ItineraryDraft } from "../types";
import { createId } from "../utils/id";
import { first, run } from "../utils/db";

export interface CreateItineraryRecordInput {
  sessionId: string;
  requirementId: string;
  title: string;
  summary: string;
  itinerary: unknown;
  budgetEstimate?: unknown;
  warnings?: unknown;
  generatorType?: string;
}

function serializeJson(value: unknown): string | null {
  return value == null ? null : JSON.stringify(value);
}

export class ItineraryRepository {
  constructor(private readonly db: D1Database) {}

  async getLatestVersion(sessionId: string): Promise<number> {
    const row = await first<{ version: number }>(
      this.db
        .prepare(
          "SELECT version FROM itinerary_drafts WHERE session_id = ? ORDER BY version DESC LIMIT 1"
        )
        .bind(sessionId)
    );
    return row?.version ?? 0;
  }

  async create(input: CreateItineraryRecordInput): Promise<ItineraryDraft> {
    const nextVersion = (await this.getLatestVersion(input.sessionId)) + 1;
    const id = createId("iti");

    await run(
      this.db
        .prepare(
          `INSERT INTO itinerary_drafts (
            id, session_id, requirement_id, version, status, title,
            summary, itinerary_json, budget_estimate_json, warnings_json, generator_type
          ) VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?)`
        )
        .bind(
          id,
          input.sessionId,
          input.requirementId,
          nextVersion,
          input.title,
          input.summary,
          JSON.stringify(input.itinerary),
          serializeJson(input.budgetEstimate),
          serializeJson(input.warnings),
          input.generatorType ?? "template"
        )
    );

    const created = await this.getById(id);
    if (!created) {
      throw new Error("failed to load created itinerary");
    }
    return created;
  }

  async getById(id: string): Promise<ItineraryDraft | null> {
    return first<ItineraryDraft>(
      this.db.prepare("SELECT * FROM itinerary_drafts WHERE id = ?").bind(id)
    );
  }

  async getLatestBySessionId(sessionId: string): Promise<ItineraryDraft | null> {
    return first<ItineraryDraft>(
      this.db
        .prepare(
          "SELECT * FROM itinerary_drafts WHERE session_id = ? ORDER BY version DESC LIMIT 1"
        )
        .bind(sessionId)
    );
  }

  async getLatestIdBySessionId(sessionId: string): Promise<string | null> {
    const row = await first<{ id: string }>(
      this.db
        .prepare(
          "SELECT id FROM itinerary_drafts WHERE session_id = ? ORDER BY version DESC LIMIT 1"
        )
        .bind(sessionId)
    );
    return row?.id ?? null;
  }
}
