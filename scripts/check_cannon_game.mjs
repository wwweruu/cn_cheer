/* global window,console */
import {chromium} from 'playwright';import {writeFile} from 'node:fs/promises';
const b=await chromium.launch({channel:'chrome',headless:true});const p=await b.newPage({viewport:{width:1440,height:1000}});const report=[];const errors=[];p.on('pageerror',e=>errors.push(e.message));p.on('console',m=>{if(m.type()==='error'&&!m.text().includes('404'))errors.push(m.text());});
try{
 await p.goto('http://127.0.0.1:4175/?audit=1');await p.waitForFunction(()=>window.__CHESS_DIAGNOSTICS__?.pieces.length===32&&window.__CHESS_DIAGNOSTICS__.pieces.every(p=>p.status==='ready'),{}, {timeout:90000});await p.getByLabel('切换顶视').click();await p.waitForTimeout(1500);
 const click=async(f,r)=>{const pt=await p.evaluate(([f,r])=>window.__CHESS_DIAGNOSTICS__.points.find(p=>p.file===f&&p.rank===r),[f,r]);const box=await p.locator('canvas').boundingBox();await p.mouse.click(box.x+pt.x,box.y+pt.y);};
 for(const [f,rank,to,camp,count] of [[1,7,0,'red',31],[7,2,9,'black',30]]){
  await click(f,rank);await p.waitForTimeout(200);await click(f,to);
  await p.waitForFunction(()=>window.__CHESS_DIAGNOSTICS__.projectile?.visible,{}, {timeout:5000});
  const flight=await p.evaluate(()=>({projectile:window.__CHESS_DIAGNOSTICS__.projectile,pieces:window.__CHESS_DIAGNOSTICS__.pieces.filter(p=>p.motion.clip==='attack')}));await p.screenshot({path:`docs/asset-reports/motion/cannon-${camp}-flight.png`});
  if(!flight.pieces.some(p=>p.asset===`cannon_${camp}`&&Math.abs(p.position[2]-(rank-4.5)*1.05)<.001))throw new Error('Cannon moved before impact');
  await p.getByLabel('打开设置').click();await p.getByRole('button',{name:'流畅',exact:true}).click();await p.getByLabel('关闭设置').click();
  await p.waitForFunction(n=>window.__CHESS_DIAGNOSTICS__.pieces.length===n,count, {timeout:5000});report.push({camp,flight,qualityChangeDuringCapture:true});
 }
 if(errors.length)throw new Error(errors.join('\n'));console.log('Both cannon capture flows passed');
}finally{await writeFile('docs/asset-reports/motion/cannon-flow.json',JSON.stringify({report,errors},null,2));await b.close();}
