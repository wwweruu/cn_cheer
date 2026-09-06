import { useEffect, useLayoutEffect, useMemo, useRef, type ReactNode } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { BufferGeometry, Color, DodecahedronGeometry, DoubleSide, Float32BufferAttribute, InstancedMesh, Object3D, PlaneGeometry, ShaderMaterial } from "three";
import { Surface } from "./Surface";
import { SceneModel } from "./SceneModel";
import { BOARD_SPACING } from "../game/coordinates";

const smooth=(a:number,b:number,x:number)=>{const t=Math.max(0,Math.min(1,(x-a)/(b-a)));return t*t*(3-2*t);};
const random=(n:number)=>{const v=Math.sin(n*127.1+311.7)*43758.5453;return v-Math.floor(v);};
const riverCenter=(x:number)=>Math.sin(x*.8)*.045+Math.sin(x*2.1)*.018+smooth(4.6,7,Math.abs(x))*(Math.sin(x*.53)*.38+Math.sin(x*1.7)*.08);
const riverWidth=(x:number)=>.36+smooth(4.6,7,Math.abs(x))*(.15+.05*Math.sin(x));
function terrainHeight(x:number,z:number) {
  const outside=smooth(5,9,Math.abs(x))+smooth(7.5,11,Math.abs(z));
  const hills=(Math.sin(x*.82+z*.23)*Math.cos(z*.61)*.23+Math.sin(x*2.1-z)*.08)*Math.min(1,outside);
  const half=riverWidth(x),water=1-smooth(half-.13,half+.09,Math.abs(z-riverCenter(x)));
  return .245+hills-water*.37;
}

type Instance={p:[number,number,number];s:[number,number,number];r?:[number,number,number];color?:string};
function Instances({items,children,shadow=false,name}:{items:Instance[];children:ReactNode;shadow?:boolean;name:string}) {
  const mesh=useRef<InstancedMesh>(null);
  useLayoutEffect(()=>{
    if(!mesh.current)return;const dummy=new Object3D();
    items.forEach((item,i)=>{dummy.position.set(...item.p);dummy.scale.set(...item.s);dummy.rotation.set(...(item.r??[0,0,0]));dummy.updateMatrix();mesh.current!.setMatrixAt(i,dummy.matrix);if(item.color)mesh.current!.setColorAt(i,new Color(item.color));});
    mesh.current.instanceMatrix.needsUpdate=true;if(mesh.current.instanceColor)mesh.current.instanceColor.needsUpdate=true;mesh.current.computeBoundingSphere();
  },[items]);
  return <instancedMesh ref={mesh} args={[undefined,undefined,items.length]} castShadow={shadow} receiveShadow name={name}>{children}</instancedMesh>;
}

function Earth() {
  const mobile=useThree(state=>state.size.width<700);
  const geometry=useMemo(()=>{
    const segments=mobile?128:256;const result=new PlaneGeometry(70,70,segments,segments);result.rotateX(-Math.PI/2);
    const p=result.getAttribute('position'),uv=result.getAttribute('uv'),colors=[];const color=new Color();
    for(let i=0;i<p.count;i++){
      const x=p.getX(i),oldZ=p.getZ(i),z=Math.sign(oldZ)*Math.pow(Math.abs(oldZ)/35,1.65)*35;p.setZ(i,z);p.setY(i,terrainHeight(x,z));uv.setXY(i,x/70+.5,z/70+.5);
      const mottled=(Math.sin(x*3.1+z*.74)*Math.cos(z*2.7-x*.4)+1)/2;
      color.set('#b9afa0').lerp(new Color('#838e75'),mottled*.5);
      if(Math.abs(z-riverCenter(x))<.5)color.multiplyScalar(.7);
      colors.push(color.r,color.g,color.b);
    }
    result.setAttribute('color',new Float32BufferAttribute(colors,3));result.computeVertexNormals();return result;
  },[mobile]);
  useEffect(()=>()=>geometry.dispose(),[geometry]);
  return <mesh geometry={geometry} receiveShadow renderOrder={-3} name="battlefield-earth"><Surface asset="battlefield_earth" repeat={14} vertexColors fadeToHorizon/></mesh>;
}

function River() {
  const material=useRef<ShaderMaterial>(null);
  const geometry=useMemo(()=>{
    const result=new PlaneGeometry(48,2,256,12);result.rotateX(-Math.PI/2);
    const p=result.getAttribute('position');for(let i=0;i<p.count;i++)p.setZ(i,p.getZ(i)*riverWidth(p.getX(i))+riverCenter(p.getX(i)));
    return result;
  },[]);
  const uniforms=useMemo(()=>({time:{value:0}}),[]);
  useFrame(({clock})=>{if(material.current)material.current.uniforms.time.value=clock.elapsedTime;});
  useEffect(()=>()=>geometry.dispose(),[geometry]);
  return <mesh geometry={geometry} position={[0,.055,0]} renderOrder={-2} name="battlefield-river">
    <shaderMaterial ref={material} uniforms={uniforms} transparent side={DoubleSide} depthWrite={false}
      vertexShader={'varying vec2 vUv; varying vec3 vWorld; void main(){vUv=uv;vWorld=(modelMatrix*vec4(position,1.)).xyz;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }'}
      fragmentShader={'uniform float time;varying vec2 vUv;varying vec3 vWorld;float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1.,0.)),f.x),mix(hash(i+vec2(0.,1.)),hash(i+1.),f.x),f.y);}void main(){vec2 flow=vec2(vWorld.x-time*.045,vWorld.z);float n=noise(flow*vec2(1.8,13.));float ripple=smoothstep(.64,.9,noise(flow*vec2(7.,55.)+n*2.));vec3 col=mix(vec3(.19,.175,.125),vec3(.29,.265,.19),n);col+=vec3(.13,.14,.14)*ripple*.5;float edge=smoothstep(0.,.08,vUv.y)*smoothstep(0.,.08,1.-vUv.y);float fog=smoothstep(13.,30.,length(vWorld.xz));col=mix(col,vec3(.027,.037,.034),fog);gl_FragColor=vec4(col,edge*(1.-smoothstep(17.,24.,abs(vWorld.x))));}'} />
  </mesh>;
}

function StonesAndGrass() {
  const mobile=useThree(state=>state.size.width<700);
  const rockGeometry=useMemo(()=>{
    const g=new DodecahedronGeometry(1,mobile?1:2),p=g.getAttribute('position');
    for(let i=0;i<p.count;i++){const x=p.getX(i),y=p.getY(i),z=p.getZ(i),n=1+.14*Math.sin(x*8+z*3)*Math.cos(y*7-x*4)+.10*Math.sin(z*11+y*5);p.setXYZ(i,x*n,y*n*.75,z*n);}
    g.computeVertexNormals();const normals=g.getAttribute('normal');
    for(let i=0;i<p.count;i++){const x=p.getX(i),y=p.getY(i)/(.75*.75),z=p.getZ(i),length=Math.hypot(x,y,z);const nx=normals.getX(i)*.35+x/length*.65,ny=normals.getY(i)*.35+y/length*.65,nz=normals.getZ(i)*.35+z/length*.65,l=Math.hypot(nx,ny,nz);normals.setXYZ(i,nx/l,ny/l,nz/l);}
    return g;
  },[mobile]);
  const bladeGeometry=useMemo(()=>{
    const vertices:number[]=[];
    for(let i=0;i<7;i++){
      const angle=i*2.4,c=Math.cos(angle),s=Math.sin(angle),x=c*.25,z=s*.25,h=.65+random(i)*.4;
      vertices.push(x-c*.1,0,z-s*.1, x+c*.1,0,z+s*.1, x+c*.45,h,z+s*.45);
    }
    const g=new BufferGeometry();g.setAttribute('position',new Float32BufferAttribute(vertices,3));g.computeVertexNormals();return g;
  },[]);
  useEffect(()=>()=>{bladeGeometry.dispose();rockGeometry.dispose();},[bladeGeometry,rockGeometry]);
  const {rocks,stones,grass}=useMemo(()=>{
    const rocks:Instance[]=[],stones:Instance[]=[],grass:Instance[]=[];
    for(let i=0;i<90;i++)stones.push({p:[(i%9-4)*BOARD_SPACING,.247,(Math.floor(i/9)-4.5)*BOARD_SPACING],s:[.16,.015,.16],r:[0,random(i)*6.28,0],color:i%3?'#a49b7e':'#8c8972'});
    for(let i=0;i<620;i++){
      let x:number,z:number;
      if(i<220){x=(random(i+100)-.5)*27;z=riverCenter(x)+(i%2?1:-1)*(riverWidth(x)-.07+random(i+500)*.12);}
      else {const side=i%4; x=side<2?(side===0?-1:1)*(5+random(i+33)*2.7):(random(i+44)-.5)*15;z=side<2?(random(i+44)-.5)*17:(side===2?-1:1)*(7.5+random(i+22)*2.2);}
      const size=i<220?.018+random(i+77)*.07:.025+random(i+77)*.15;
      if(i<220&&Math.abs(x)<4.75){const nearestX=Math.round(x/BOARD_SPACING)*BOARD_SPACING;if(Math.hypot(x-nearestX,Math.abs(z)-.525)<.45+size)continue;}
      rocks.push({p:[x,terrainHeight(x,z)+size*.15,z],s:[size,size*(.5+random(i)),size*(.7+random(i+1))],r:[random(i)*2,random(i+2)*6,random(i+3)],color:i%3?'#9a998d':'#bbb4a2'});
    }
    for(let i=0;i<1200;i++){
      const x=(random(i+901)-.5)*16,z=(random(i+1601)-.5)*20;
      if(Math.abs(z)<.65|| (Math.abs(x)<4.8&&Math.abs(z)<5.2) || (Math.abs(x)<1.3&&Math.abs(z)>5.2&&Math.abs(z)<7.5))continue;
      grass.push({p:[x,terrainHeight(x,z),z],s:[.12+random(i)*.12,.05+random(i+4)*.18,.17],r:[0,random(i+5)*6.28,(random(i+6)-.5)*.4],color:i%2?'#41482e':'#535039'});
    }
    return {rocks,stones,grass};
  },[]);
  return <>
    <Instances items={stones} name="ninety-stone-intersections"><cylinderGeometry args={[1,1.13,1,10]}/><Surface asset="ground_stone"/></Instances>
    <Instances items={rocks} name="riverbank-and-field-rocks"><primitive object={rockGeometry} attach="geometry"/><Surface asset="ground_stone" stone/></Instances>
    <Instances items={grass} name="battlefield-grass"><primitive object={bladeGeometry} attach="geometry"/><meshStandardMaterial roughness={1} side={DoubleSide}/></Instances>
  </>;
}

function Fortifications() {
  const {stakes,rails}=useMemo(()=>{
    const stakes:Instance[]=[],rails:Instance[]=[];
    const fence=(ax:number,az:number,bx:number,bz:number,height:number)=>{
      const length=Math.hypot(bx-ax,bz-az),angle=-Math.atan2(bz-az,bx-ax);const count=Math.ceil(length/.14);
      for(let i=0;i<=count;i++){
        const x=ax+(bx-ax)*i/count,z=az+(bz-az)*i/count,h=height*(.9+random(i+ax+az)*.2);
        stakes.push({p:[x,terrainHeight(x,z)+h/2,z],s:[.065,h,.065],r:[0,random(i)*6,(random(i+21)-.5)*.09]});
      }
      for(const y of [.2,.41])rails.push({p:[(ax+bx)/2,.245+y,(az+bz)/2],s:[length,.055,.055],r:[0,angle,0]});
    };
    for(const s of [-1,1]){
      fence(s*5.2,-7.6,s*5.2,-.8,.55);fence(s*5.2,.8,s*5.2,7.6,.55);
      fence(-5.2,s*7.6,5.2,s*7.6,.55);
      fence(-1.55,s*5.5,-1.55,s*7.6,.44);fence(1.55,s*5.5,1.55,s*7.6,.44);
      fence(-1.55,s*5.5,-.5,s*5.5,.44);fence(.5,s*5.5,1.55,s*5.5,.44);
    }
    return {stakes,rails};
  },[]);
  return <>
    <Instances items={stakes} name="timber-palisades" shadow><cylinderGeometry args={[.65,1,1,5]}/><Surface asset="weathered_wood" tint="#c6b391"/></Instances>
    <Instances items={rails} name="palisade-crossbeams" shadow><boxGeometry/><Surface asset="weathered_wood" tint="#bfa986"/></Instances>
    <SceneModel asset="camp_red" position={[0,.245,6.55]} rotation={Math.PI} scale={.85}/>
    <SceneModel asset="camp_black" position={[0,.245,-6.55]} scale={.85}/>
    {[-5.2,5.2].flatMap(x=>[-7.2,-3.1,3.1,7.2].map(z=><SceneModel key={`${x}:${z}`} asset="watchtower" position={[x,.245,z]} scale={.52} castShadow={false}/>))}
  </>;
}

function CampFlag({red,x,z}:{red:boolean;x:number;z:number}) {
  const geometry=useMemo(()=>new PlaneGeometry(.55,.7,10,12),[]);
  useFrame(({clock})=>{const p=geometry.getAttribute('position');for(let i=0;i<p.count;i++){
    const freedom=(p.getX(i)+.275)/.55;p.setZ(i,Math.sin(p.getX(i)*8+p.getY(i)*3+clock.elapsedTime*2.4+z)*.055*freedom);
  }p.needsUpdate=true;geometry.computeVertexNormals();});
  useEffect(()=>()=>geometry.dispose(),[geometry]);
  return <group position={[x,.245,z]}>
    <mesh position={[0,.92,0]}><cylinderGeometry args={[.018,.027,1.84,6]}/><Surface asset="aged_metal" tint="#a29772"/></mesh>
    <mesh position={[.275,1.39,0]} geometry={geometry}><Surface asset={red?'fabric_red':'fabric_black'} tint="#b6a68b"/></mesh>
  </group>;
}

/** A continuous field at the same ninety rules coordinates as the original board. */
export function BattlefieldTerrain() {
  return <group name="battlefield-C1">
    <Earth/><River/><StonesAndGrass/><Fortifications/>
    {[-1,1].flatMap(side=>[-1.45,1.45].map(x=><CampFlag key={`${side}:${x}`} red={side>0} x={x} z={side*5.8}/>))}
  </group>;
}
