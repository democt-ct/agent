import type {
  CreateRequirementInput,
  StructuredPayload,
  TripRequirement
} from "../types";
import { createId } from "../utils/id";
import { first, run } from "../utils/db";

function serializeJson(value: unknown): string | null {
  return value == null ? null : JSON.stringify(value);
}

export class RequirementRepository {
  constructor(private readonly db: D1Database) {}

  async getLatestVersion(sessionId: string): Promise<number> {
    const row = await first<{ version: number }>(
      this.db
        .prepare(
          "SELECT version FROM trip_requirements WHERE session_id = ? ORDER BY version DESC LIMIT 1"
        )
        .bind(sessionId)
    );
    return row?.version ?? 0;
  }

  async create(
    sessionId: string,
    input: CreateRequirementInput
  ): Promise<TripRequirement> {
    const nextVersion = (await this.getLatestVersion(sessionId)) + 1;
    const id = createId("req");
    const payload: StructuredPayload = input.structured_payload ?? {};

    await run(
      this.db
        .prepare(
          `INSERT INTO trip_requirements (
            id, session_id, version, raw_input, origin_city, destination,
            start_date, end_date, trip_days, budget_min, budget_max,
            travelers_summary, interests_json, constraints_json,
            structured_payload_json
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
        )
        .bind(
          id,
          sessionId,
          nextVersion,
          input.raw_input,
          payload.origin_city ?? null,
          payload.destination ?? null,
          payload.start_date ?? null,
          payload.end_date ?? null,
          payload.trip_days ?? null,
          payload.budget_min ?? null,
          payload.budget_max ?? null,
          payload.travelers_summary ?? null,
          serializeJson(payload.interests ?? null),
          serializeJson(payload.constraints ?? null),
          JSON.stringify(payload)
        )
    );

    const created = await this.getById(id);
    if (!created) {
      throw new Error("failed to load created requirement");
    }
    return created;
  }

  async getById(id: string): Promise<TripRequirement | null> {
    return first<TripRequirement>(
      this.db.prepare("SELECT * FROM trip_requirements WHERE id = ?").bind(id)
    );
  }

  async getLatestBySessionId(sessionId: string): Promise<TripRequirement | null> {
    return first<TripRequirement>(
      this.db
        .prepare(
          "SELECT * FROM trip_requirements WHERE session_id = ? ORDER BY version DESC LIMIT 1"
        )
        .bind(sessionId)
    );
  }

  async getLatestIdBySessionId(sessionId: string): Promise<string | null> {
    const row = await first<{ id: string }>(
      this.db
        .prepare(
          "SELECT id FROM trip_requirements WHERE session_id = ? ORDER BY version DESC LIMIT 1"
        )
        .bind(sessionId)
    );
    return row?.id ?? null;
  }
}
