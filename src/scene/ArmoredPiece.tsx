import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import {
  CanvasTexture,
  Color,
  DoubleSide,
  Group,
  LinearFilter,
  SRGBColorSpace,
} from "three";
import { boardToWorld } from "../game/coordinates";
import type { EffectLevel, MoveRecord, Piece, PieceType } from "../game/types";

interface ArmoredPieceProps {
  piece: Piece;
  selected: boolean;
  move: MoveRecord | null;
  effects: EffectLevel;
  onClick: () => void;
  onMoveComplete: () => void;
}

const LABELS: Record<PieceType, { red: string; black: string }> = {
  general: { red: "帅", black: "将" },
  advisor: { red: "仕", black: "士" },
  elephant: { red: "相", black: "象" },
  horse: { red: "马", black: "马" },
  chariot: { red: "车", black: "车" },
  cannon: { red: "炮", black: "炮" },
  soldier: { red: "兵", black: "卒" },
};

const labelTextureCache = new Map<string, CanvasTexture>();

function getLabelTexture(piece: Piece) {
  const cacheKey = `${piece.camp}-${piece.type}`;
  const cached = labelTextureCache.get(cacheKey);
  if (cached) return cached;

  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("无法创建棋子文字纹理");

  const red = piece.camp === "red";
  context.clearRect(0, 0, 256, 256);
  context.beginPath();
  context.arc(128, 128, 114, 0, Math.PI * 2);
  context.fillStyle = red ? "#e1d4bd" : "#d6ddd9";
  context.fill();
  context.lineWidth = 13;
  context.strokeStyle = red ? "#8f2925" : "#263331";
  context.stroke();
  context.beginPath();
  context.arc(128, 128, 91, 0, Math.PI * 2);
  context.lineWidth = 3;
  context.strokeStyle = red ? "rgba(143,41,37,.48)" : "rgba(38,51,49,.52)";
  context.stroke();
  context.fillStyle = red ? "#7f1f1d" : "#172321";
  context.font = "700 132px KaiTi, STKaiti, serif";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(LABELS[piece.type][piece.camp], 128, 136);

  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  texture.minFilter = LinearFilter;
  texture.magFilter = LinearFilter;
  texture.needsUpdate = true;
  labelTextureCache.set(cacheKey, texture);
  return texture;
}

const theme = {
  red: {
    armor: "#7d2725",
    armorLight: "#a94b3f",
    metal: "#b9a36f",
    cloth: "#5a1819",
    dark: "#32181a",
    ring: "#df7a62",
  },
  black: {
    armor: "#34413e",
    armorLight: "#5b6b66",
    metal: "#a6aeaa",
    cloth: "#222e2b",
    dark: "#151e1c",
    ring: "#9cb5ad",
  },
} as const;

function Weapon({ type, camp }: { type: PieceType; camp: Piece["camp"] }) {
  const colors = theme[camp];

  if (type === "soldier") {
    return (
      <group position={[0.31, 0.88, 0]} rotation={[0, 0, -0.08]}>
        <mesh castShadow>
          <cylinderGeometry args={[0.022, 0.026, 1.15, 8]} />
          <meshStandardMaterial color={colors.metal} metalness={0.7} roughness={0.28} />
        </mesh>
        <mesh position={[0, 0.65, 0]} castShadow>
          <coneGeometry args={[0.075, 0.25, 5]} />
          <meshStandardMaterial color={colors.metal} metalness={0.84} roughness={0.2} />
        </mesh>
      </group>
    );
  }

  if (type === "cannon") {
    return (
      <group position={[0, 0.86, -0.03]} rotation={[0, 0, Math.PI / 2]}>
        <mesh castShadow>
          <cylinderGeometry args={[0.095, 0.13, 0.74, 12]} />
          <meshStandardMaterial color={colors.metal} metalness={0.82} roughness={0.26} />
        </mesh>
        <mesh position={[0, 0.39, 0]} castShadow>
          <torusGeometry args={[0.13, 0.035, 8, 16]} />
          <meshStandardMaterial color={colors.dark} metalness={0.5} roughness={0.36} />
        </mesh>
      </group>
    );
  }

  if (type === "advisor") {
    return (
      <group position={[0, 1.03, 0.02]}>
        <mesh rotation={[0, 0, 0.72]} castShadow>
          <boxGeometry args={[0.045, 0.74, 0.07]} />
          <meshStandardMaterial color={colors.metal} metalness={0.78} roughness={0.2} />
        </mesh>
        <mesh rotation={[0, 0, -0.72]} castShadow>
          <boxGeometry args={[0.045, 0.74, 0.07]} />
          <meshStandardMaterial color={colors.metal} metalness={0.78} roughness={0.2} />
        </mesh>
      </group>
    );
  }

  return null;
}

function HelmetCrest({ type, camp }: { type: PieceType; camp: Piece["camp"] }) {
  const colors = theme[camp];

  if (type === "general") {
    return (
      <group position={[0, 1.46, 0]}>
        <mesh castShadow>
          <boxGeometry args={[0.42, 0.1, 0.17]} />
          <meshStandardMaterial color={colors.metal} metalness={0.72} roughness={0.24} />
        </mesh>
        {[-0.16, 0, 0.16].map((x) => (
          <mesh key={x} position={[x, 0.13, 0]} castShadow>
            <boxGeometry args={[0.045, 0.3, 0.05]} />
            <meshStandardMaterial color={colors.metal} metalness={0.72} roughness={0.24} />
          </mesh>
        ))}
      </group>
    );
  }

  if (type === "horse") {
    return (
      <group position={[0, 1.43, -0.02]}>
        <mesh rotation={[0.16, 0, 0]} castShadow>
          <coneGeometry args={[0.12, 0.46, 6]} />
          <meshStandardMaterial color={colors.armorLight} metalness={0.42} roughness={0.45} />
        </mesh>
        <mesh position={[0, 0.13, -0.13]} rotation={[0.3, 0, 0]} castShadow>
          <boxGeometry args={[0.08, 0.34, 0.06]} />
          <meshStandardMaterial color={colors.ring} roughness={0.65} />
        </mesh>
      </group>
    );
  }

  if (type === "chariot") {
    return (
      <group position={[0, 1.39, 0]}>
        <mesh castShadow>
          <cylinderGeometry args={[0.25, 0.28, 0.18, 8]} />
          <meshStandardMaterial color={colors.metal} metalness={0.76} roughness={0.3} />
        </mesh>
        {[-0.16, 0.16].map((x) => (
          <mesh key={x} position={[x, 0.16, 0]} castShadow>
            <boxGeometry args={[0.1, 0.22, 0.18]} />
            <meshStandardMaterial color={colors.armor} metalness={0.48} roughness={0.38} />
          </mesh>
        ))}
      </group>
    );
  }

  if (type === "elephant") {
    return (
      <group position={[0, 1.35, 0.01]}>
        {[-1, 1].map((side) => (
          <mesh
            key={side}
            position={[side * 0.22, 0.02, 0.05]}
            rotation={[Math.PI / 2, 0, side * 0.38]}
            castShadow
          >
            <coneGeometry args={[0.055, 0.28, 8]} />
            <meshStandardMaterial color={colors.metal} metalness={0.8} roughness={0.2} />
          </mesh>
        ))}
      </group>
    );
  }

  return (
    <mesh position={[0, 1.44, 0]} castShadow>
      <coneGeometry args={[0.11, type === "advisor" ? 0.27 : 0.2, 6]} />
      <meshStandardMaterial color={colors.metal} metalness={0.7} roughness={0.26} />
    </mesh>
  );
}

function ArmorBody({ piece }: { piece: Piece }) {
  const colors = theme[piece.camp];
  const black = piece.camp === "black";
  const broad = piece.type === "elephant" || piece.type === "chariot";
  const short = piece.type === "soldier";

  return (
    <group scale={short ? 0.88 : 1} position={[0, short ? 0.03 : 0, 0]}>
      <mesh position={[0, 0.82, 0]} castShadow>
        <cylinderGeometry args={[broad ? 0.31 : 0.25, 0.34, 0.58, black ? 6 : 10]} />
        <meshStandardMaterial color={colors.cloth} roughness={0.64} metalness={0.12} />
      </mesh>
      <mesh position={[0, 0.91, 0.18]} rotation={[-0.08, 0, 0]} castShadow>
        <boxGeometry args={[broad ? 0.52 : 0.43, 0.37, 0.1]} />
        <meshStandardMaterial color={colors.armor} roughness={0.34} metalness={0.48} />
      </mesh>
      {[-1, 1].map((side) => (
        <mesh
          key={side}
          position={[side * (broad ? 0.37 : 0.31), 1.03, 0]}
          rotation={[0, 0, side * (black ? 0.2 : 0.08)]}
          castShadow
        >
          {black ? (
            <octahedronGeometry args={[broad ? 0.2 : 0.16, 0]} />
          ) : (
            <sphereGeometry args={[broad ? 0.2 : 0.17, 12, 8]} />
          )}
          <meshStandardMaterial color={colors.armorLight} roughness={0.35} metalness={0.52} />
        </mesh>
      ))}
      <mesh position={[0, 1.22, 0]} castShadow>
        <sphereGeometry args={[0.19, 16, 10]} />
        <meshStandardMaterial color={colors.dark} roughness={0.42} metalness={0.38} />
      </mesh>
      <mesh position={[0, 1.34, 0]} castShadow>
        <cylinderGeometry args={[0.22, 0.19, 0.18, black ? 6 : 12]} />
        <meshStandardMaterial color={colors.armorLight} roughness={0.3} metalness={0.56} />
      </mesh>
      <HelmetCrest type={piece.type} camp={piece.camp} />
      <Weapon type={piece.type} camp={piece.camp} />
    </group>
  );
}

export function ArmoredPiece({
  piece,
  selected,
  move,
  effects,
  onClick,
  onMoveComplete,
}: ArmoredPieceProps) {
  const group = useRef<Group>(null);
  const completionSent = useRef<number | null>(null);
  const animationStart = useRef(0);
  const [hovered, setHovered] = useState(false);
  const labelTexture = useMemo(() => getLabelTexture(piece), [piece]);
  const colors = theme[piece.camp];
  const activeMove = move?.piece.id === piece.id ? move : null;

  useEffect(() => {
    if (activeMove) {
      animationStart.current = performance.now();
      completionSent.current = null;
    }
  }, [activeMove]);

  useFrame(({ clock }) => {
    if (!group.current) return;
    const target = boardToWorld(piece.position);
    let x = target[0];
    let y = 0.24;
    let z = target[2];

    if (activeMove) {
      const from = boardToWorld(activeMove.from);
      const duration = effects === "off" ? 90 : activeMove.captured ? 720 : 480;
      const rawProgress = Math.min(1, (performance.now() - animationStart.current) / duration);
      const progress = 1 - Math.pow(1 - rawProgress, 3);
      x = from[0] + (target[0] - from[0]) * progress;
      z = from[2] + (target[2] - from[2]) * progress;
      const arcScale = piece.type === "horse" ? 1.05 : activeMove.captured ? 0.64 : 0.36;
      y += effects === "off" ? 0 : Math.sin(Math.PI * rawProgress) * arcScale;
      group.current.rotation.y = Math.sin(rawProgress * Math.PI) * 0.14;

      if (rawProgress >= 1 && completionSent.current !== activeMove.id) {
        completionSent.current = activeMove.id;
        onMoveComplete();
      }
    } else {
      group.current.rotation.y = 0;
      if (selected && effects !== "off") y += 0.055 + Math.sin(clock.elapsedTime * 4.4) * 0.025;
    }

    const targetScale = selected ? 1.06 : hovered ? 1.025 : 1;
    const scale = group.current.scale.x + (targetScale - group.current.scale.x) * 0.18;
    group.current.scale.setScalar(scale);
    group.current.position.set(x, y, z);
  });

  return (
    <group
      ref={group}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
      onPointerEnter={(event) => {
        event.stopPropagation();
        setHovered(true);
      }}
      onPointerLeave={() => setHovered(false)}
    >
      {(selected || hovered) && (
        <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.4, 0.49, 40]} />
          <meshBasicMaterial color={selected ? colors.ring : "#c8bfa9"} transparent opacity={0.82} />
        </mesh>
      )}
      <mesh position={[0, 0.17, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.42, 0.46, 0.3, piece.camp === "black" ? 10 : 20]} />
        <meshStandardMaterial
          color={colors.dark}
          metalness={0.46}
          roughness={0.42}
          emissive={selected ? new Color(colors.armor) : new Color("#050706")}
          emissiveIntensity={selected ? 0.24 : 0}
        />
      </mesh>
      <mesh position={[0, 0.34, 0]} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <torusGeometry args={[0.35, 0.036, 8, piece.camp === "black" ? 10 : 20]} />
        <meshStandardMaterial color={colors.metal} metalness={0.76} roughness={0.24} />
      </mesh>
      <ArmorBody piece={piece} />
      <mesh position={[0, 0.342, 0.12]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.205, 36]} />
        <meshBasicMaterial
          map={labelTexture}
          transparent
          side={DoubleSide}
          toneMapped={false}
        />
      </mesh>
      <mesh position={[0, 0.72, 0]} visible={false}>
        <cylinderGeometry args={[0.53, 0.53, 1.65, 12]} />
        <meshBasicMaterial transparent opacity={0} />
      </mesh>
    </group>
  );
}
