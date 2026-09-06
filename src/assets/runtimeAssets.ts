import { useCallback, useSyncExternalStore } from "react";
import { Group, Material, Mesh, MeshStandardMaterial, SkinnedMesh, Texture, WebGLRenderer } from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { KTX2Loader } from "three/addons/loaders/KTX2Loader.js";
import { AssetCache } from "./assetCache";
import type { ModelTier } from "./quality";
import { getAssetUrl, motionAssetRevision, type AssetCategory } from "./manifest";

let loader: GLTFLoader | undefined;
let basis: KTX2Loader | undefined;
let decoderFailed = false;
let decoderReady: Promise<boolean> = Promise.resolve(false);
const plainLoader = new GLTFLoader();

export function initializeAssetLoader(renderer: WebGLRenderer) {
  if (loader) return;
  basis = new KTX2Loader().setTranscoderPath("/assets/decoders/basis/").setWorkerLimit(2).detectSupport(renderer);
  loader = new GLTFLoader().setKTX2Loader(basis);
  decoderReady = basis.init().then(()=>true,()=>{decoderFailed=true;return false;});
}

function disposeModel(scene: Group) {
  const materials = new Set<Material>();
  const textures = new Set<Texture>();
  scene.traverse(object => {
    if (!(object instanceof Mesh)) return;
    object.geometry.dispose();
    (Array.isArray(object.material) ? object.material : [object.material]).forEach(material => materials.add(material));
  });
  materials.forEach(material => {
    Object.values(material).forEach(value => { if (value instanceof Texture) textures.add(value); });
    material.dispose();
  });
  textures.forEach(texture => {
    texture.dispose();
    if (texture.source.data instanceof ImageBitmap) texture.source.data.close();
  });
}

export function assetPath(key: string, fallback = false) {
  const [category, asset, tier] = key.split(":");
  return getAssetUrl(category as AssetCategory, asset, tier as ModelTier, fallback);
}

export const runtimeAssets = new AssetCache<Group>(async key => {
  let scene: Group | undefined;
  let fallback = false;
  const checkedLoad=async (activeLoader:GLTFLoader,url:string)=>{
    const gltf=await activeLoader.loadAsync(url);
    const result=gltf.scene;result.animations=gltf.animations;
    let valid=true,meshes=0,skinned=false;
    result.traverse(object=>{
      if(!(object instanceof Mesh))return;meshes++;if(object instanceof SkinnedMesh)skinned=true;
      (Array.isArray(object.material)?object.material:[object.material]).forEach(material=>{
        if(!(material instanceof MeshStandardMaterial) || !material.map || !material.normalMap || !material.roughnessMap || !material.metalnessMap)valid=false;
      });
    });
    // GLTFLoader may resolve a scene after silently dropping failed textures.
    // Treat incomplete PBR as a failed decode so the WebP fallback is real.
    if(key.startsWith('motion:')&&(!skinned||!['idle','attack','hit','death'].every(name=>result.animations.some(clip=>clip.name===name))))valid=false;
    if(!valid || !meshes){disposeModel(result);throw new Error('Incomplete PBR or skeletal animation decoding');}
    return result;
  };
  if (loader && !decoderFailed && await decoderReady) {
    try { scene = await checkedLoad(loader,assetPath(key)); }
    catch (error) {
      if (/basis|transcod|wasm|worker/i.test(String(error))) decoderFailed = true;
    }
  }
  if (!scene) {
    fallback = true;
    scene = await checkedLoad(plainLoader,assetPath(key,true));
  }
  scene.traverse(object => {
    if (!(object instanceof Mesh)) return;
    object.castShadow = true;
    object.receiveShadow = true;
    object.geometry.computeBoundingSphere();
  });
  return { value: scene, fallback };
}, disposeModel);

export function useRuntimeAsset(category: AssetCategory, asset: string, tier: ModelTier) {
  const revision=category==='motion'?motionAssetRevision(asset):0;
  const key = `${category}:${asset}:${tier}${revision?`:v${revision}`:''}`;
  const subscribe = useCallback((listener: () => void) => runtimeAssets.subscribe(key, listener), [key]);
  const getSnapshot = useCallback(() => runtimeAssets.snapshot(key), [key]);
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
