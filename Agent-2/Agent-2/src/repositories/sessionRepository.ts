import type { CreateSessionInput, Session } from "../types";
import { createId } from "../utils/id";
import { first, run } from "../utils/db";

export class SessionRepository {
  constructor(private readonly db: D1Database) {}

  async create(input: CreateSessionInput): Promise<Session> {
    const id = createId("sess");
    await run(
      this.db
        .prepare(
          `INSERT INTO sessions (
            id, user_id, visitor_id, title, status, source
          ) VALUES (?, ?, ?, ?, 'active', ?)`
        )
        .bind(
          id,
          input.user_id ?? null,
          input.visitor_id ?? null,
          input.title ?? "新的旅行规划",
          input.source ?? "web"
        )
    );

    const created = await this.getById(id);
    if (!created) {
      throw new Error("failed to load created session");
    }
    return created;
  }

  async getById(id: string): Promise<Session | null> {
    return first<Session>(
      this.db.prepare("SELECT * FROM sessions WHERE id = ?").bind(id)
    );
  }

  async bumpRequirementVersion(id: string, version: number): Promise<void> {
    await run(
      this.db
        .prepare(
          `UPDATE sessions
           SET current_requirement_version = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?`
        )
        .bind(version, id)
    );
  }

  async bumpItineraryVersion(id: string, version: number): Promise<void> {
    await run(
      this.db
        .prepare(
          `UPDATE sessions
           SET current_itinerary_version = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?`
        )
        .bind(version, id)
    );
  }
}
