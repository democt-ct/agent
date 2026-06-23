import type { ConversationMessage, CreateMessageInput } from "../types";
import { createId } from "../utils/id";
import { first, run } from "../utils/db";

export class MessageRepository {
  constructor(private readonly db: D1Database) {}

  async create(
    sessionId: string,
    input: CreateMessageInput
  ): Promise<ConversationMessage> {
    const id = createId("msg");
    await run(
      this.db
        .prepare(
          `INSERT INTO conversation_messages (
            id, session_id, role, message_type, content, metadata_json
          ) VALUES (?, ?, ?, ?, ?, ?)`
        )
        .bind(
          id,
          sessionId,
          input.role,
          input.message_type ?? "text",
          input.content,
          input.metadata ? JSON.stringify(input.metadata) : null
        )
    );

    const created = await first<ConversationMessage>(
      this.db
        .prepare("SELECT * FROM conversation_messages WHERE id = ?")
        .bind(id)
    );
    if (!created) {
      throw new Error("failed to load created message");
    }
    return created;
  }

  async listBySessionId(sessionId: string, limit = 50): Promise<ConversationMessage[]> {
    const result = await this.db
      .prepare(
        `SELECT * FROM conversation_messages
         WHERE session_id = ?
         ORDER BY created_at ASC, rowid ASC
         LIMIT ?`
      )
      .bind(sessionId, limit)
      .all<ConversationMessage>();

    return result.results ?? [];
  }
}
