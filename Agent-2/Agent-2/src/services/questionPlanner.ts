import type { StructuredPayload } from "../types";

export function buildFollowUpQuestions(payload: StructuredPayload): string[] {
  const questions: string[] = [];

  if (!payload.destination) {
    if (payload.destination_hint) {
      questions.push(
        `你提到的是“${payload.destination_hint}”，我需要先确认具体目的地范围：你想去的是哪个城市、城区，还是这个城市周边的某个区域？`
      );
    } else {
      questions.push("你想去哪个城市或目的地？");
    }
  }
  if (!payload.trip_days) {
    questions.push("这次计划玩几天？");
  }

  return questions;
}

export function buildPreferenceFollowUpQuestion(payload: StructuredPayload): string | null {
  const hasPreference =
    Boolean(payload.interests?.length) ||
    Boolean(payload.constraints?.length) ||
    Boolean(payload.user_preferences);

  if (hasPreference || !payload.destination || !payload.trip_days) {
    return null;
  }

  return "我先给你一版通用行程。想再贴合一点的话，你更想偏美食、咖啡商场、自然风光，还是轻松citywalk？";
}

export function findMissingFields(payload: StructuredPayload): string[] {
  const fields: string[] = [];

  if (!payload.destination) {
    fields.push("destination");
  }
  if (!payload.trip_days) {
    fields.push("trip_days");
  }

  return fields;
}
