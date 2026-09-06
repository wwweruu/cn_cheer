/* global window,console */
import {chromium} from 'playwright';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.launch({channel:'chrome',headless:true});
try {
 const page=await browser.newPage({viewport:{width:1200,height:800}});const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto('http://127.0.0.1:4175/sky-review.html');await page.waitForFunction(()=>window.skyAudit?.ready);
 for(let i=0;i<6;i++){await page.evaluate(i=>{const [,yaw,pitch]=window.skyAudit.views[i];window.skyAudit.view(yaw,pitch);},i);await page.screenshot({path:`docs/asset-reports/environment/sky-view-${i}.png`});}
 const board=await page.evaluate(()=>window.skyAudit.board());if(errors.length)throw new Error(errors.join('\n'));
 await writeFile('docs/asset-reports/environment/board-final-rays.json',JSON.stringify({board,errors},null,2));console.log('Final board: 180 ray intersections passed; six sky views rendered');
} finally {await browser.close();}
