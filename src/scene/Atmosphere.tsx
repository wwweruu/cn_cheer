import { useCallback, useEffect, useRef, useSyncExternalStore } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { AdditiveBlending, CubeTextureLoader, PMREMGenerator, Sprite, SRGBColorSpace, Texture, TextureLoader } from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { AssetCache } from "../assets/assetCache";
import type { EffectLevel } from "../game/types";

const textures=new AssetCache<Texture>(async name=>{
  const value=await new TextureLoader().loadAsync(`/assets/environment/atmosphere/${name}.webp`);value.colorSpace=SRGBColorSpace;return {value};
},texture=>texture.dispose(),2,30000);
function useLayer(name:string) {
  const subscribe=useCallback((listener:()=>void)=>textures.subscribe(name,listener),[name]);
  const snapshot=useCallback(()=>textures.snapshot(name),[name]);
  const asset=useSyncExternalStore(subscribe,snapshot,snapshot);
  return asset.value;
}

function DistantLayer({ name,y,z,width,height,opacity }: {name:string;y:number;z:number;width:number;height:number;opacity:number}) {
  const texture=useLayer(name);
  if(!texture)return null;
  return <mesh position={[0,y,z]}>
    <planeGeometry args={[width,height]}/><meshBasicMaterial map={texture} transparent opacity={opacity} depthWrite={false}/>
  </mesh>;
}
function Haze({ name,x,z,size,opacity }: {name:string;x:number;z:number;size:number;opacity:number}) {
  const texture=useLayer(name);const sprite=useRef<Sprite>(null);
  useFrame(({clock})=>{
    if(!sprite.current)return;
    sprite.current.position.y=.6+Math.sin(clock.elapsedTime*.13+x)*.25;
    sprite.current.material.opacity=opacity*(.75+Math.sin(clock.elapsedTime*.2+z)*.25);
  });
  if(!texture)return null;
  return <sprite ref={sprite} position={[x,.6,z]} scale={[size,size,1]}>
    <spriteMaterial map={texture} transparent opacity={opacity} depthWrite={false} blending={name==='fx_embers'?AdditiveBlending:undefined}/>
  </sprite>;
}

export function Atmosphere({effects}:{effects:EffectLevel}) {
  const get=useThree(state=>state.get);
  useEffect(()=>{
    const {scene,gl}=get();
    const pmrem=new PMREMGenerator(gl);const room=new RoomEnvironment();const environment=pmrem.fromScene(room,.04);
    room.dispose();pmrem.dispose();scene.environment=environment.texture;scene.environmentIntensity=.45;
    const previous=scene.background;let disposed=false;
    const cube=new CubeTextureLoader().setPath('/assets/environment/atmosphere/').load(
      ['sky_px.webp','sky_nx.webp','sky_py.webp','sky_ny.webp','sky_pz.webp','sky_nz.webp'],
      result=>{if(!disposed){result.colorSpace=SRGBColorSpace;scene.background=result;scene.backgroundIntensity=.42;}},undefined,()=>{});
    return()=>{disposed=true;scene.background=previous;scene.environment=null;cube.dispose();environment.dispose();};
  },[get]);
  return <>
    <DistantLayer name="distant_mountains" y={1.75} z={-29} width={72} height={23} opacity={.22}/>
    <DistantLayer name="distant_camp" y={1} z={-20} width={43} height={14} opacity={.18}/>
    {effects==='full'&&<><Haze name="fx_smoke" x={-7.5} z={1} size={4} opacity={.14}/><Haze name="fx_smoke" x={7.5} z={-4} size={3} opacity={.10}/><Haze name="fx_embers" x={-6.2} z={5.4} size={2.2} opacity={.32}/></>}
  </>;
}
