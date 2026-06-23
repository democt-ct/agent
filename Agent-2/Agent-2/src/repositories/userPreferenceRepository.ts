import type {
  PreferenceOwnerType,
  UserPreferencePayload,
  UserPreferenceRecord
} from "../types";
import { createId } from "../utils/id";
import { first, run } from "../utils/db";
import { mergePreferences } from "../services/preferences/preferenceExtractor";

export interface PreferenceOwner {
  ownerType: PreferenceOwnerType;
  ownerId: string;
}

function serializeInterests(interests?: string[]): string | null {
  return interests?.length ? JSON.stringify(interests) : null;
}

function parseRecord(record: UserPreferenceRecord | null): UserPreferencePayload {
  if (!record) {
    return {};
  }

  return {
    preferredPace: record.preferred_pace ?? undefined,
    distanceTolerance: record.distance_tolerance ?? undefined,
    interests: record.interests_json
      ? (JSON.parse(record.interests_json) as string[])
      : undefined
  };
}

export class UserPreferenceRepository {
  constructor(private readonly db: D1Database) {}

  async getRecord(owner: PreferenceOwner): Promise<UserPreferenceRecord | null> {
    return first<UserPreferenceRecord>(
      this.db
        .prepare(
          `SELECT * FROM user_preferences
           WHERE owner_type = ? AND owner_id = ?
           LIMIT 1`
        )
        .bind(owner.ownerType, owner.ownerId)
    );
  }

  async get(owner: PreferenceOwner): Promise<UserPreferencePayload> {
    return parseRecord(await this.getRecord(owner));
  }

  async upsert(
    owner: PreferenceOwner,
    update: UserPreferencePayload,
    source = "conversation"
  ): Promise<UserPreferencePayload> {
    const currentRecord = await this.getRecord(owner);
    const merged = mergePreferences(parseRecord(currentRecord), update);

    if (currentRecord) {
      await run(
        this.db
          .prepare(
            `UPDATE user_preferences
             SET preferred_pace = ?,
                 interests_json = ?,
                 distance_tolerance = ?,
                 source = ?,
                 confidence = ?,
                 updated_at = CURRENT_TIMESTAMP
             WHERE owner_type = ? AND owner_id = ?`
          )
          .bind(
            merged.preferredPace ?? null,
            serializeInterests(merged.interests),
            merged.distanceTolerance ?? null,
            source,
            0.8,
            owner.ownerType,
            owner.ownerId
          )
      );
      return merged;
    }

    await run(
      this.db
        .prepare(
          `INSERT INTO user_preferences (
            id, owner_type, owner_id, preferred_pace, interests_json,
            distance_tolerance, source, confidence
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
        )
        .bind(
          createId("pref"),
          owner.ownerType,
          owner.ownerId,
          merged.preferredPace ?? null,
          serializeInterests(merged.interests),
          merged.distanceTolerance ?? null,
          source,
          0.8
        )
    );

    return merged;
  }
}

export function resolvePreferenceOwner(params: {
  sessionId: string;
  userId?: string | null;
  visitorId?: string | null;
}): PreferenceOwner {
  if (params.userId) {
    return { ownerType: "user", ownerId: params.userId };
  }
  if (params.visitorId) {
    return { ownerType: "visitor", ownerId: params.visitorId };
  }
  return { ownerType: "session", ownerId: params.sessionId };
}
