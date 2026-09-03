import type { Piece } from "../game/types";

/**
 * 二期 GLB 资产清单：以 `${type}_${camp}` 为键。
 * 未登记的棋子自动回退到一期程序化造型。
 * 模型规范：米制、原点在底座底面中心、面向 three.js +Z。
 */
const MODELS: Partial<Record<string, string>> = {
  general_red: "/assets/models/general_red.glb",
  general_black: "/assets/models/general_black.glb",
  advisor_red: "/assets/models/advisor_red.glb",
  advisor_black: "/assets/models/advisor_black.glb",
  elephant_red: "/assets/models/elephant_red.glb",
  elephant_black: "/assets/models/elephant_black.glb",
  horse_red: "/assets/models/horse_red.glb",
  horse_black: "/assets/models/horse_black.glb",
  chariot_red: "/assets/models/chariot_red.glb",
  chariot_black: "/assets/models/chariot_black.glb",
  cannon_red: "/assets/models/cannon_red.glb",
  cannon_black: "/assets/models/cannon_black.glb",
  soldier_red: "/assets/models/soldier_red.glb",
  soldier_black: "/assets/models/soldier_black.glb",
};

export function getModelUrl(piece: Pick<Piece, "type" | "camp">): string | null {
  return MODELS[`${piece.type}_${piece.camp}`] ?? null;
}

export const MODEL_URLS: string[] = Object.values(MODELS).filter(
  (url): url is string => typeof url === "string",
);
