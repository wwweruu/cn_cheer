/* global window,console */
import {chromium,devices} from 'playwright';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.launch({channel:'chrome',headless:true});const report=[];
try {for(const mode of ['desktop','mobile']) {
 const context=await browser.newContext(mode==='mobile'?devices['Pixel 7']:{viewport:{width:1440,height:1000}});
 const page=await context.newPage();const errors=[],requests=new Map();page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('404'))errors.push(m.text());});page.on('request',r=>{if((r.url().includes('/production/')||r.url().includes('/motion/'))&&r.url().endsWith('.glb'))requests.set(r.url(),(requests.get(r.url())??0)+1);});
 await page.goto('http://127.0.0.1:4175/?audit=1');await page.waitForFunction(()=>window.__CHESS_DIAGNOSTICS__?.assetStats?.loading===0&&window.__CHESS_DIAGNOSTICS__?.pieces?.length===32&&window.__CHESS_DIAGNOSTICS__?.pieces?.every(p=>p.status==='ready'),{}, {timeout:90000});
 await page.getByLabel('打开设置').click();await page.getByRole('button',{name:'精细',exact:true}).click();await page.getByLabel('关闭设置').click();
 await page.getByLabel('切换顶视').click();await page.waitForTimeout(1500);
 const point=await page.evaluate(()=>window.__CHESS_DIAGNOSTICS__.points.find(p=>p.file===4&&p.rank===9));const box=await page.locator('canvas').boundingBox();await page.mouse.click(box.x+point.x,box.y+point.y);
 await page.waitForFunction(tier=>window.__CHESS_DIAGNOSTICS__.pieces.some(p=>p.asset==='general_red'&&p.tier===tier&&p.status==='ready'),mode==='mobile'?'mobile':'desktop',{timeout:60000});
 const high=await page.evaluate(()=>window.__CHESS_DIAGNOSTICS__.pieces.find(p=>p.asset==='general_red').tier);
 await page.getByLabel('打开设置').click();await page.getByRole('button',{name:'流畅',exact:true}).click();await page.getByLabel('关闭设置').click();await page.waitForFunction(()=>window.__CHESS_DIAGNOSTICS__.pieces.every(p=>p.tier==='distant'&&p.status==='ready'));
 await page.getByLabel('切换斜视').click();await page.waitForTimeout(1000);
 await page.mouse.move(box.x+box.width*.5,box.y+box.height*.55);await page.mouse.down();await page.mouse.move(box.x+box.width*.85,box.y+box.height*.15,{steps:25});await page.mouse.up();await page.waitForTimeout(800);await page.screenshot({path:`docs/asset-reports/game/${mode}-orbit.png`});
 await page.getByLabel('复位镜头').click();await page.waitForTimeout(1000);await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5);await page.mouse.wheel(0,-320);await page.waitForTimeout(700);await page.screenshot({path:`docs/asset-reports/game/${mode}-zoom.png`});
 const camera=await page.evaluate(()=>window.__CHESS_DIAGNOSTICS__.camera);const duplicateRequests=[...requests].filter(([,count])=>count>1);if(errors.length||duplicateRequests.length)throw new Error(JSON.stringify({errors,duplicateRequests}));
 report.push({mode,highSelectedTier:high,lowAllDistant:true,camera,errors,duplicateRequests});await context.close();
}}finally{await browser.close();await writeFile('docs/asset-reports/game/camera-quality.json',JSON.stringify(report,null,2));}
console.log('Desktop/mobile quality switching, shared requests, orbit and zoom passed');
