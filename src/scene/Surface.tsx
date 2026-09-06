import { useEffect, useMemo } from "react";
import { DoubleSide, Mesh, MeshStandardMaterial, RepeatWrapping } from "three";
import { useRuntimeAsset } from "../assets/runtimeAssets";

export function Surface({ asset, repeat=1, tint="#ffffff", fadeToHorizon=false, vertexColors=false, wornPath=false, stone=false }: { asset:string; repeat?:number; tint?:string; fadeToHorizon?:boolean; vertexColors?:boolean; wornPath?:boolean; stone?:boolean }) {
  const snapshot=useRuntimeAsset("surface",asset,"mobile");
  const material=useMemo(()=>{
    let original: MeshStandardMaterial|undefined;
    snapshot.value?.traverse(o=>{if(o instanceof Mesh && o.material instanceof MeshStandardMaterial) original=o.material;});
    const result=original?.clone() ?? new MeshStandardMaterial({color: "#343a33",roughness:.85});
    result.color.set(tint);result.side=DoubleSide;result.vertexColors=vertexColors;
    for(const key of ["map","normalMap","roughnessMap","metalnessMap"] as const) {
      if(result[key]) { result[key]=result[key]!.clone(); result[key]!.repeat.set(repeat,repeat); result[key]!.wrapS=RepeatWrapping;result[key]!.wrapT=RepeatWrapping;result[key]!.needsUpdate=true; }
    }
    result.normalScale.set(.55,.55);
    if(stone){result.metalness=0;result.roughness=1;result.normalScale.set(1.2,1.2);}
    if(fadeToHorizon) {
      result.transparent=true;result.depthWrite=false;result.forceSinglePass=true;
      result.onBeforeCompile=shader=>{
        shader.vertexShader='varying vec3 vGroundWorld;\n'+shader.vertexShader;
        shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\n vGroundWorld = (modelMatrix * vec4(position, 1.0)).xyz;');
        shader.fragmentShader='varying vec3 vGroundWorld;\n float dirtHash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);} float dirtNoise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(dirtHash(i),dirtHash(i+vec2(1.,0.)),f.x),mix(dirtHash(i+vec2(0.,1.)),dirtHash(i+1.),f.x),f.y);}\n'+shader.fragmentShader;
        shader.fragmentShader=shader.fragmentShader.replace('#include <color_fragment>','#include <color_fragment>\n float soilPatch=dirtNoise(vGroundWorld.xz*.65)*.6+dirtNoise(vGroundWorld.xz*2.3)*.25+dirtNoise(vGroundWorld.xz*9.)*.15; diffuseColor.rgb*=mix(vec3(.56,.60,.47),vec3(1.18,1.09,.91),smoothstep(.16,.82,soilPatch)); diffuseColor.a *= 1.0 - smoothstep(22.0, 42.0, length(vGroundWorld.xz));');
      };
      result.customProgramCacheKey=()=> 'ground-horizon-patches-v2';
    }
    if(wornPath) {
      result.transparent=true;result.depthWrite=false;result.opacity=.85;result.forceSinglePass=true;
      result.onBeforeCompile=shader=>{
        shader.vertexShader='varying vec2 vPathUv;\n'+shader.vertexShader;
        shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\n vPathUv=uv;');
        shader.fragmentShader='varying vec2 vPathUv;\n float pathHash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);} float pathNoise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(pathHash(i),pathHash(i+vec2(1.,0.)),f.x),mix(pathHash(i+vec2(0.,1.)),pathHash(i+1.),f.x),f.y);}\n'+shader.fragmentShader;
        shader.fragmentShader=shader.fragmentShader.replace('#include <color_fragment>','#include <color_fragment>\n float edge=min(vPathUv.x,1.-vPathUv.x);float wear=pathNoise(vPathUv*vec2(5.,8.))*.18-.10;diffuseColor.a*=smoothstep(.0,.24,edge+wear)*(.55+.45*pathNoise(vPathUv*vec2(2.,1.5)));');
      };
      result.customProgramCacheKey=()=> 'worn-earth-path-v2';
    }
    return result;
  },[snapshot.value,repeat,tint,fadeToHorizon,vertexColors,wornPath,stone]);
  useEffect(()=>()=>{
    for(const key of ["map","normalMap","roughnessMap","metalnessMap"] as const) material[key]?.dispose();
    material.dispose();
  },[material]);
  return <primitive object={material} attach="material" dispose={null}/>;
}

