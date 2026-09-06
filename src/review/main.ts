import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { KTX2Loader } from "three/addons/loaders/KTX2Loader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import "./style.css";
import { motionAssetRevision } from '../assets/manifest';

type Variant = "desktop" | "mobile" | "lod1" | "lod2";
type ReviewManifest = { variants: Record<Variant, { file: string; bytes: number; triangles: number }>; note?:string; generated_clips?:string[]; review_clips?:string[]; source_version?:number };
const productionPieces = ["general_red","general_black","advisor_red","advisor_black","elephant_red","elephant_black","horse_red","horse_black","chariot_red","chariot_black","cannon_red","cannon_black","soldier_red","soldier_black"];
const query = new URLSearchParams(window.location.search);
const queryAsset = query.get("asset") ?? "general_red";
const motionGallery=document.body.dataset.motionGallery==='true';
const nativeGallery=document.body.dataset.nativeGallery==='true';
const production = document.body.dataset.productionGallery === "true" || motionGallery;
const nativePieces = ["soldier_red","soldier_black","general_black","advisor_red","horse_red","horse_black","cannon_red","cannon_black","elephant_red","elephant_black"];
const availablePieces=nativeGallery?nativePieces:productionPieces;
const asset = availablePieces.includes(queryAsset) ? queryAsset : nativeGallery?"soldier_red":"general_red";
const root = production ? `/assets/review/${nativeGallery?'native-motion':motionGallery?'motion':'production'}/${asset}/` : document.body.dataset.reviewRoot ?? "/assets/review/general_red/";
if (production) {
  const selection = document.getElementById("asset") as HTMLSelectElement;
  selection.value=asset;
  document.getElementById("piece-title")!.textContent=selection.selectedOptions[0].textContent;
  selection.addEventListener("change",()=>{
    query.set('asset', selection.value);
    if(motionGallery)query.set('clip',(document.getElementById('clip') as HTMLSelectElement).value);
    window.location.search=query.toString();
  });
}
function element<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Missing review element: ${id}`);
  return node as T;
}
const viewport = element<HTMLDivElement>("viewport");
const status = element("status");
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.1;
viewport.appendChild(renderer.domElement);
const ktxLoader = new KTX2Loader().setTranscoderPath("/assets/decoders/basis/").setWorkerLimit(2).detectSupport(renderer);
const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
const room = new RoomEnvironment();
const environment = pmrem.fromScene(room, 0.04);
scene.environment = environment.texture;
scene.environmentIntensity = 0.65;
room.dispose();
pmrem.dispose();
scene.add(new THREE.HemisphereLight(0xe3e9e5, 0x383126, 1.4));
const key = new THREE.DirectionalLight(0xffe7c4, 3.2);
key.position.set(-2, 4, 4);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
Object.assign(key.shadow.camera, { left: -2, right: 2, top: 3, bottom: -2, near: 0.1, far: 12 });
key.shadow.normalBias = 0.012;
scene.add(key);
const rim = new THREE.DirectionalLight(0xc3d8ef, 2);
rim.position.set(2, 3, -2);
scene.add(rim);
const floor = new THREE.Mesh(new THREE.PlaneGeometry(200, 200), new THREE.ShadowMaterial({ opacity: 0.28 }));
floor.rotation.x = -Math.PI / 2;
floor.position.y = -0.002;
floor.receiveShadow = true;
scene.add(floor);
const grid = new THREE.GridHelper(4.2, 4, 0x8e8766, 0x585f4e);
grid.position.y = -0.001;
grid.visible = false;
scene.add(grid);
const camera = new THREE.PerspectiveCamera(32, 1, 0.02, 100);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.minDistance = 0.6;
controls.maxDistance = 7;
controls.maxPolarAngle = Math.PI * 0.52;
controls.autoRotateSpeed = 0.6;
const views: Record<string, { position: number[]; target: number[] }> = {
  front: { position: [0, 0.90, 3.45], target: [0, 0.77, 0] },
  quarter: { position: [2.1, 1.3, 3.1], target: [0, 0.77, 0] },
  back: { position: [0, 0.90, -3.45], target: [0, 0.77, 0] },
  side: { position: [4, 1.2, 0], target: [0, .77, 0] },
  detail: { position: [0.32, 1.36, 1.17], target: [0, 1.17, 0] },
  base: { position: [0.32, 0.36, 1.22], target: [0, 0.2, 0] },
};
if (document.body.dataset.normalize === "true") {
  views.front.position = [0, 0.90, 4];
  views.quarter.position = [2.4, 1.4, 3.7];
  views.back.position = [0, 0.90, -4];
  views.base.position = [0.25, 0.44, 1.95];
}
function setView(name: string) {
  const view = views[name];
  camera.position.fromArray(view.position);
  controls.target.fromArray(view.target);
  if (name === "base" && document.body.dataset.normalize === "true" && camera.aspect < 0.8) {
    camera.position.sub(controls.target).multiplyScalar(0.8 / camera.aspect).add(controls.target);
  }
  controls.update();
  document.querySelectorAll<HTMLButtonElement>("[data-view]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.view === name)));
}
setView(query.get('view') && views[query.get('view')!] ? query.get('view')! : 'quarter');
document.querySelectorAll<HTMLButtonElement>("[data-view]").forEach(button => button.addEventListener("click", () => setView(button.dataset.view!)));
element<HTMLInputElement>("rotate").addEventListener("change", event => controls.autoRotate = (event.target as HTMLInputElement).checked);
element<HTMLInputElement>("grid").addEventListener("change", event => grid.visible = (event.target as HTMLInputElement).checked);
let model: THREE.Group | null = null;
let mixer:THREE.AnimationMixer|null=null;
let clips:THREE.AnimationClip[]=[];
let action:THREE.AnimationAction|null=null;
let playing=true;
let lastFrame=performance.now();
let fixedSamples:Array<{mesh:THREE.SkinnedMesh;index:number;rest:THREE.Vector3}>=[];
function chooseClip(){
  if(!mixer||!motionGallery)return;
  const name=element<HTMLSelectElement>('clip').value;
  const clip=clips.find(clip=>clip.name===name);if(!clip)return;
  mixer.stopAllAction();action=mixer.clipAction(clip);action.reset().play();
  action.setLoop(THREE.LoopRepeat,Infinity);playing=true;mixer.update(0);
  element('play-motion').textContent='暂停';viewport.dataset.clip=name;
}
if(motionGallery){
  const requestedClip=query.get('clip');
  if(requestedClip&&['idle','attack','hit','death','walk','run'].includes(requestedClip))element<HTMLSelectElement>('clip').value=requestedClip;
  element('clip').addEventListener('change',chooseClip);
  element('play-motion').addEventListener('click',()=>{playing=!playing;element('play-motion').textContent=playing?'暂停':'播放';});
  element<HTMLInputElement>('playhead').addEventListener('input',event=>{
    if(!action||!mixer)return;playing=false;element('play-motion').textContent='播放';
    action.time=Number((event.target as HTMLInputElement).value)/1000*(action.getClip().duration-.00001);mixer.update(0);
  });
}
function visitMaterials(group: THREE.Group, callback: (material: THREE.MeshStandardMaterial) => void) {
  group.traverse(object => {
    if (object instanceof THREE.Mesh) {
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.forEach(callback);
    }
  });
}
function wireframe() {
  if (model) visitMaterials(model, material => material.wireframe = element<HTMLInputElement>("wireframe").checked);
}
element<HTMLInputElement>("wireframe").addEventListener("change", wireframe);
function release(group: THREE.Group) {
  const textures = new Set<THREE.Texture>();
  group.traverse(object => { if (object instanceof THREE.Mesh) object.geometry.dispose();if(object instanceof THREE.SkinnedMesh)object.skeleton.dispose(); });
  visitMaterials(group, material => {
    Object.values(material).forEach(value => { if (value instanceof THREE.Texture) textures.add(value); });
    material.dispose();
  });
  textures.forEach(texture => texture.dispose());
}
let loadVersion = 0;
async function load(variant: Variant, manifest: ReviewManifest) {
  const version = ++loadVersion;
  status.textContent = "正在载入模型…";
  viewport.dataset.loaded = "false";
  try {
    const entry = manifest.variants[variant];
    const revision=motionGallery&&!nativeGallery?motionAssetRevision(asset):0;
    const url = (entry.file.startsWith("/") ? entry.file : root+entry.file)+(revision?`?v=${revision}`:'');
    const gltf = await new GLTFLoader().setKTX2Loader(ktxLoader).loadAsync(url);
    if (version !== loadVersion) { release(gltf.scene); return; }
    if (model) {mixer?.stopAllAction();mixer?.uncacheRoot(model);scene.remove(model); release(model); }
    model = gltf.scene;
    if (document.body.dataset.normalize === "true") {
      let box = new THREE.Box3().setFromObject(model);
      model.scale.multiplyScalar(1.511 / (box.max.y - box.min.y));
      model.updateMatrixWorld(true);
      box = new THREE.Box3().setFromObject(model);
      model.position.x -= (box.max.x + box.min.x) / 2;
      model.position.y -= box.min.y;
      model.position.z -= (box.max.z + box.min.z) / 2;
    }
    model.traverse(object => { if (object instanceof THREE.Mesh) { object.castShadow = true; object.receiveShadow = true; } });
    visitMaterials(model, material => {
      if (material.map) material.map.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
    });
    scene.add(model);
    if(motionGallery){
      clips=gltf.animations;mixer=new THREE.AnimationMixer(model);fixedSamples=[];model.updateMatrixWorld(true);
      model.traverse(object=>{if(object instanceof THREE.SkinnedMesh){
        object.frustumCulled=false;
        const fixed=object.skeleton.bones.findIndex(b=>b.name==='FixedPedestal');
        const indices=object.geometry.getAttribute('skinIndex'),weights=object.geometry.getAttribute('skinWeight');
        for(let i=0;i<indices.count;i+=13){
          if(indices.getX(i)===fixed&&weights.getX(i)>.9999999&&weights.getY(i)<1e-7&&weights.getZ(i)<1e-7&&weights.getW(i)<1e-7)fixedSamples.push({mesh:object,index:i,rest:object.getVertexPosition(i,new THREE.Vector3()).applyMatrix4(object.matrixWorld)});
        }
      }});
      viewport.dataset.clips=clips.map(clip=>clip.name).join(',');viewport.dataset.fixedSamples=String(fixedSamples.length);chooseClip();
    }
    wireframe();
    element("triangles").textContent = entry.triangles.toLocaleString("zh-CN");
    element("size").textContent = `${(entry.bytes / 1048576).toFixed(2)} MB`;
    element<HTMLAnchorElement>("download").href = url;
    status.textContent = "模型已载入 · 可旋转检查";
    viewport.dataset.loaded = variant;
    let compressedTextures = 0;
    const textureSet = new Set<THREE.Texture>();
    visitMaterials(model, material => Object.values(material).forEach(value => {
      if (value instanceof THREE.Texture) textureSet.add(value);
    }));
    textureSet.forEach(texture => { if (texture instanceof THREE.CompressedTexture) compressedTextures++; });
    viewport.dataset.compressedTextures = String(compressedTextures);
  } catch (error) {
    status.textContent = "载入失败，请确认已准备样板文件后刷新";
    console.error(error);
  }
}
const observer = new ResizeObserver(() => {
  const width = viewport.clientWidth, height = viewport.clientHeight;
  renderer.setSize(width, height);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
});
observer.observe(viewport);
renderer.setAnimationLoop(() => {
  const now=performance.now(),delta=Math.min(.05,(now-lastFrame)/1000);lastFrame=now;
  if(motionGallery&&mixer&&action){
    if(playing)mixer.update(delta*Number(element<HTMLSelectElement>('speed').value));
    element<HTMLInputElement>('playhead').value=String(Math.round(action.time/action.getClip().duration*1000));
    viewport.dataset.motionProgress=String(action.time/action.getClip().duration);
    model!.updateMatrixWorld(true);let drift=0;const point=new THREE.Vector3();
    for(const sample of fixedSamples){sample.mesh.getVertexPosition(sample.index,point).applyMatrix4(sample.mesh.matrixWorld);drift=Math.max(drift,point.distanceTo(sample.rest));}
    viewport.dataset.baseDrift=String(drift);
  }
  controls.update();renderer.render(scene, camera);
});
fetch(root + (nativeGallery&&query.get('sample')==='before'?'before.json':"manifest.json")).then(response => {
  if (!response.ok) throw new Error("Sample manifest is unavailable");
  return response.json() as Promise<ReviewManifest>;
}).then(manifest => {
  if(nativeGallery){
    const allowedClips=manifest.review_clips??manifest.generated_clips??[];
    const sampleSelection=element<HTMLSelectElement>('sample-version');
    sampleSelection.value=query.get('sample')==='before'?'before':'current';
    sampleSelection.addEventListener('change',()=>{query.set('sample',sampleSelection.value);window.location.search=query.toString();});
    viewport.dataset.sourceVersion=String(manifest.source_version??'');
    element('native-note').textContent=manifest.note??'Meshy 原生动作样板';
    element<HTMLAnchorElement>('compare-current').href=`/motion-gallery.html?asset=${asset}&clip=${manifest.generated_clips?.[0]??'idle'}`;
    const selection=element<HTMLSelectElement>('clip');
    const requested=selection.value;
    for(const option of Array.from(selection.options))if(!allowedClips.includes(option.value))option.remove();
    selection.value=allowedClips.includes(requested)?requested:allowedClips[0]??'idle';
  }
  element<HTMLSelectElement>("quality").addEventListener("change", event => void load((event.target as HTMLSelectElement).value as Variant, manifest));
  void load(element<HTMLSelectElement>('quality').value as Variant, manifest);
}).catch(error => { status.textContent = "尚未准备样板文件，请查看样板说明"; console.error(error); });
