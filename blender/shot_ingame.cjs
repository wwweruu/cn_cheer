/* 截图验证：打开棋盘页，等待3D场景与GLB加载后截图 */
const { chromium } = require("@playwright/test");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  await page.goto("http://127.0.0.1:4173/", { waitUntil: "networkidle" });
  await page.waitForSelector("canvas", { timeout: 20000 });
  await page.waitForTimeout(6000); // 等 GLB 加载与首帧稳定
  await page.screenshot({ path: "blender/renders/ingame_chariot_red.png" });
  // 拉近镜头特写红方车（点击画布中央拖动放大）
  await page.mouse.move(720, 450);
  await page.mouse.wheel(0, -600);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: "blender/renders/ingame_chariot_red_closeup.png" });
  console.log("ERRORS:", JSON.stringify(errors.slice(0, 5)));
  await browser.close();
  console.log("SHOT-OK");
})().catch((e) => {
  console.error("SHOT-FAIL", e);
  process.exit(1);
});
