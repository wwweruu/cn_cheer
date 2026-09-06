/* global window,console */
import {chromium} from 'playwright';import {writeFile} from 'node:fs/promises';
const browser=await chromium.launch({channel:'chrome',headless:true});const context=await browser.newContext({viewport:{width:1440,height:1000},recordVideo:{dir:'docs/asset-reports/motion/video',size:{width:1152,height:800}}});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('404'))errors.push(m.text());});const report={};
try{
await page.goto('http://127.0.0.1:4175/?audit=1');await page.waitForFunction(()=>window.__CHESS_DIAGNOSTICS__?.pieces.length===32&&window.__CHESS_DIAGNOSTICS__.pieces.every(p=>p.status==='ready'),{}, {timeout:90000});await page.waitForTimeout(500);
const idle1=await page.evaluate(()=>window.__CHESS_DIAGNOSTICS__.pieces);await page.waitForTimeout(700);const idle2=await page.evaluate(()=>window.__CHESS_DIAGNOSTICS__.pieces);report.idleMoving=idle2.filter((p,i)=>Math.abs(p.poseSignature-idle1[i].poseSignature)>.00001).length;if(report.idleMoving!==32)throw new Error('Some pieces have static idle poses: '+report.idleMoving);
await page.getByLabel('切换顶视').click();await page.waitForTimeout(1600);
const click=async(file,rank)=>{const p=await page.evaluate(([f,r])=>window.__CHESS_DIAGNOSTICS__.points.find(p=>p.file===f&&p.rank===r),[file,rank]);const box=await page.locator('canvas').boundingBox();await page.mouse.click(box.x+p.x,box.y+p.y);};
const move=async(f,r,tf,tr)=>{await click(f,r);await page.waitForTimeout(120);await click(tf,tr);await page.waitForTimeout(800);};
await move(4,6,4,5);await move(4,3,4,4);await click(4,5);await page.waitForTimeout(180);await click(4,4);await page.waitForTimeout(500);
report.lockedDuringCapture=await page.getByLabel('悔棋').isDisabled();report.approach=await page.evaluate(()=>window.__CHESS_DIAGNOSTICS__.pieces.filter(p=>p.motion.token!==null&&p.asset.includes('soldier')));await page.screenshot({path:'docs/asset-reports/motion/capture-approach.png'});
await page.waitForFunction(()=>window.__CHESS_DIAGNOSTICS__.pieces.some(p=>p.motion.clip==='hit'),{}, {timeout:2000});report.hit=await page.evaluate(()=>window.__CHESS_DIAGNOSTICS__.pieces.filter(p=>p.motion.clip==='hit'||p.motion.clip==='attack'));await page.screenshot({path:'docs/asset-reports/motion/capture-hit.png'});
await page.waitForTimeout(650);report.death=await page.evaluate(()=>window.__CHESS_DIAGNOSTICS__.pieces.filter(p=>p.motion.clip==='death'));await page.screenshot({path:'docs/asset-reports/motion/capture-death.png'});
await page.waitForFunction(()=>window.__CHESS_DIAGNOSTICS__.pieces.length===31,{}, {timeout:4000});await page.getByLabel('悔棋').click();await page.waitForFunction(()=>window.__CHESS_DIAGNOSTICS__.pieces.length===32,{}, {timeout:4000});
await click(4,5);await page.waitForTimeout(150);await click(4,4);await page.waitForTimeout(450);await page.getByLabel('重新开局',{exact:true}).click();await page.getByRole('alertdialog').getByRole('button',{name:'重新开局',exact:true}).click();await page.waitForTimeout(100);
await move(4,6,4,5);await page.waitForTimeout(3400);report.afterRestart=await page.evaluate(()=>window.__CHESS_DIAGNOSTICS__.pieces);
await page.getByLabel('重新开局',{exact:true}).click();await page.getByRole('alertdialog').getByRole('button',{name:'重新开局',exact:true}).click();await page.waitForTimeout(300);
await move(0,6,0,5);await move(4,3,4,4);await move(4,6,4,5);await click(4,4);await page.waitForTimeout(150);await click(4,5);
await page.waitForFunction(()=>window.__CHESS_DIAGNOSTICS__.pieces.some(p=>p.motion.clip==='hit'),{}, {timeout:2500});
report.blackCapture=await page.evaluate(()=>window.__CHESS_DIAGNOSTICS__.pieces.filter(p=>p.motion.clip==='hit'||p.motion.clip==='attack'));await page.screenshot({path:'docs/asset-reports/motion/black-capture-hit.png'});
if(!report.blackCapture.some(p=>p.asset==='soldier_black'&&p.motion.clip==='attack')||!report.blackCapture.some(p=>p.asset==='soldier_red'&&p.motion.clip==='hit'))throw new Error('Black attacker / red defender playback missing');
await page.waitForFunction(()=>window.__CHESS_DIAGNOSTICS__.pieces.length===31,{}, {timeout:5000});await page.getByLabel('悔棋').click();await page.waitForFunction(()=>window.__CHESS_DIAGNOSTICS__.pieces.length===32,{}, {timeout:4000});
report.errors=errors;if(errors.length)throw new Error(errors.join('\n'));console.log('CAPTURE',JSON.stringify({idleMoving:report.idleMoving,locked:report.lockedDuringCapture,hit:report.hit.map(p=>p.motion),death:report.death.map(p=>p.motion),blackCapture:report.blackCapture.map(p=>({asset:p.asset,motion:p.motion})),errors}));
}finally{await writeFile('docs/asset-reports/motion/game-flow.json',JSON.stringify(report,null,2));await context.close();await browser.close();}

