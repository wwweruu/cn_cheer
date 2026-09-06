import { useMemo, type ReactNode } from "react";
import { useThree } from "@react-three/fiber";
import { Mesh } from "three";
import { useRuntimeAsset } from "../assets/runtimeAssets";

export function SceneModel({ asset, fallback = null, position = [0,0,0], rotation = 0, scale=1, castShadow=true }: {
  asset: string; fallback?: ReactNode; position?: [number,number,number]; rotation?: number; scale?:number; castShadow?:boolean;
}) {
  const width = useThree(state=>state.size.width);
  const tier = width < 700 || matchMedia("(pointer: coarse)").matches ? "mobile" : "desktop";
  const snapshot = useRuntimeAsset("board",asset,tier);
  const model = useMemo(()=>{const copy=snapshot.value?.clone(true);copy?.traverse(o=>{if(o instanceof Mesh)o.castShadow=castShadow;});return copy;},[snapshot.value,castShadow]);
  return <group position={position} rotation={[0,rotation,0]} scale={scale} name={asset} userData={{ asset, tier, status:snapshot.status }}>
    {model ? <primitive object={model} dispose={null}/> : fallback}
  </group>;
}
