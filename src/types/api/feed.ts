import type { FeedEvent } from "../feedEvent";

export type LifecycleStage = "stage_a" | "stage_b" | "stage_c";

export interface FeedResponse {
  items: FeedEvent[];
  next_cursor: string | null;
  lifecycle_stage: LifecycleStage;
}
