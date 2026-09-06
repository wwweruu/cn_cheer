/* global console,process */
import {chromium} from 'playwright';import {mkdir,writeFile} from 'node:fs/promises';
const pieces=['general_red','general_black','advisor_red','advisor_black','elephant_red','elephant_black','horse_red','horse_black','chariot_red','chariot_black','cannon_red','cannon_black','soldier_red','soldier_black'];
const selected=process.argv[2]?.split(',')??pieces;const b=await chromium.launch({channel:'chrome',headless:true});const report=[];await mkdir('docs/asset-reports/motion/browser',{recursive:true});
try{for(const asset of selected){const p=await b.newPage({viewport:{width:1300,height:900}});const errors=[];p.on('pageerror',e=>errors.push(e.message));p.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await p.goto('http://127.0.0.1:4175/motion-gallery.html?asset='+asset);await p.locator('#viewport[data-loaded="desktop"]').waitFor({timeout:60000});
 for(const tier of ['desktop','mobile','lod2']){
  if(tier!=='desktop'){await p.selectOption('#quality',tier);await p.locator(`#viewport[data-loaded="${tier}"]`).waitFor({timeout:60000});}
  const row={asset,tier,clips:[],maxBaseDrift:0,compressedTextures:0};
  for(const clip of ['idle','attack','hit','death','walk','run']){
   await p.selectOption('#clip',clip);let peak=0;
   for(const frame of [0,250,500,750,999]){await p.locator('#playhead').fill(String(frame));await p.waitForTimeout(45);const data=await p.locator('#viewport').evaluate(el=>({...el.dataset}));peak=Math.max(peak,Number(data.baseDrift));row.compressedTextures=Number(data.compressedTextures);if(Number(data.fixedSamples)===0)throw new Error(asset+' has no fixed base samples');}
   row.clips.push({clip,maxBaseDrift:peak});row.maxBaseDrift=Math.max(row.maxBaseDrift,peak);
  }
  if(row.maxBaseDrift>1e-5||row.compressedTextures!==3)throw new Error(JSON.stringify(row));
  await p.selectOption('#clip','attack');await p.locator('#playhead').fill('550');await p.waitForTimeout(100);await p.screenshot({path:`docs/asset-reports/motion/browser/${asset}-${tier}.png`});row.errors=[...errors];if(errors.length)throw new Error(errors.join('\n'));report.push(row);
 }
 await p.close();console.log('MOTION_QA',asset,'3 tiers, 6 clips, fixed base passed');}
}finally{await b.close();await writeFile('docs/asset-reports/motion/browser.json',JSON.stringify(report,null,2));}
