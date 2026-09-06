import type { Piece } from "../game/types";
import type { ModelTier } from "./quality";

export const PIECE_ASSET_IDS = [
  "general_red", "general_black", "advisor_red", "advisor_black",
  "elephant_red", "elephant_black", "horse_red", "horse_black",
  "chariot_red", "chariot_black", "cannon_red", "cannon_black",
  "soldier_red", "soldier_black",
] as const;

export type AssetCategory = "piece" | "motion" | "board" | "surface";
const vehicleMotionRevisions:Record<string,number>={horse_red:6,horse_black:4,chariot_red:6,chariot_black:4,cannon_red:6,cannon_black:7};
export const motionAssetRevision=(asset:string)=>vehicleMotionRevisions[asset]??0;

/** Versioned KTX2 assets; paired WebP GLBs provide decoder fallback. */
export function getAssetUrl(category: AssetCategory, asset: string, tier: ModelTier, fallback = false) {
  const root = category === "motion" ? "models/motion" : category === "piece" ? "models/production" : category === "surface" ? "environment/materials" : "board/production";
  const revision=category==='motion'?motionAssetRevision(asset):0;
  return `/assets/${root}/${asset}/${tier}${fallback ? ".webp" : ""}.glb${revision?`?v=${revision}`:''}`;
}

export function getModelUrl(piece: Pick<Piece, "type" | "camp">, tier: ModelTier = "mobile") {
  return getAssetUrl("piece", `${piece.type}_${piece.camp}`, tier);
}

export const MODEL_URLS = PIECE_ASSET_IDS.map(asset => getAssetUrl("piece", asset, "mobile"));
