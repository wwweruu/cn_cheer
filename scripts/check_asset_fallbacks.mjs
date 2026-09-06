/* global console,window */
import {chromium} from 'playwright';import {writeFile} from 'node:fs/promises';
const browser=await chromium.launch({channel:'chrome',headless:true});const reports=[];
try{for(const failure of ['model','decoder']){const context=await browser.newContext({viewport:{width:1200,height:900}});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));const pattern=failure==='model'?'**/models/motion/general_red/**':'**/decoders/basis/**';await page.route(pattern,route=>route.fulfill({status:404,body:'intentional QA 404'}));await page.goto('http://127.0.0.1:4175/?audit=1');await page.waitForFunction(mode=>{const d=window.__CHESS_DIAGNOSTICS__;return d?.assetStats?.loading===0&&(mode==='model'?d.assetStats.failed===1:d.pieces.every(p=>p.status==='ready')&&d.assetStats.fallback>0);},failure,{timeout:60000});const before=await page.evaluate(()=>window.__CHESS_DIAGNOSTICS__.assetStats);await page.screenshot({path:'docs/asset-reports/game/fallback-'+failure+'.png'});
if(failure==='model'){await page.unroute(pattern);await page.getByRole('button',{name:'重试外观'}).click();await page.waitForFunction(()=>window.__CHESS_DIAGNOSTICS__.pieces.every(p=>p.status==='ready'),{}, {timeout:30000});}
reports.push({failure,before,after:await page.evaluate(()=>window.__CHESS_DIAGNOSTICS__.assetStats),errors});console.log('FALLBACK',failure,JSON.stringify(reports.at(-1)));await context.close();}}
finally{await browser.close();await writeFile('docs/asset-reports/game/fallback.json',JSON.stringify(reports,null,2));}

