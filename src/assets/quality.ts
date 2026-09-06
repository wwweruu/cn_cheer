import type { ModelQuality } from "../game/types";

export type ModelTier = "desktop" | "mobile" | "distant";

export function choosePieceTier(pixels: number, selected: boolean, quality: ModelQuality, mobile: boolean, current: ModelTier): ModelTier {
  if (quality === "low") return "distant";
  if (!mobile && selected && (quality === "high" || pixels > 160)) return "desktop";
  const threshold = current === "distant" ? 110 : 85;
  return pixels > threshold || (selected && quality === "high") ? "mobile" : "distant";
}
