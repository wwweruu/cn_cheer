import { expect, test } from "@playwright/test";
import { PNG } from "pngjs";

test("preserves an imported origin through a move, reload and undo", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-chromium");
  await page.goto("/");
  const imported = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/PCP1P1P1P/1C7/9/RNBAKABNR w - - 0 1";
  await page.getByRole("button", { name: "打开设置" }).click();
  await page.getByRole("button", { name: "导入 FEN" }).click();
  await page.getByLabel("FEN 局面串").fill(imported);
  await page.getByRole("button", { name: "载入局面" }).click();
  await page.getByRole("button", { name: "关闭设置" }).click();
  await page.waitForTimeout(1600);

  const box = (await page.locator("canvas").boundingBox())!;
  const x = box.x + box.width / 2;
  await page.mouse.click(x, box.y + box.height * 0.588);
  await page.waitForTimeout(120);
  await page.mouse.click(x, box.y + box.height * 0.531);
  await expect(page.getByText("兵五进1")).toBeVisible();
  await expect(page.getByLabel("悔棋")).toBeEnabled();
  const savedFen = await page.evaluate(() => JSON.parse(localStorage.getItem("xuanjia-xiangqi-game")!).fen);

  await page.reload();
  await expect(page.getByText("兵五进1")).toBeVisible();
  await expect(page.getByLabel("悔棋")).toBeEnabled();
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("xuanjia-xiangqi-game")!).fen)).toBe(savedFen);
  await page.getByLabel("悔棋").click();
  await expect(page.getByLabel("悔棋")).toBeDisabled();
  await page.reload();
  await page.getByRole("button", { name: "打开设置" }).click();
  await page.getByRole("button", { name: "导入 FEN" }).click();
  await expect(page.getByLabel("FEN 局面串")).toHaveValue(imported);
});

async function canvasHasRenderedPixels(page: import("@playwright/test").Page) {
  const screenshot = await page.locator("canvas").screenshot({ animations: "disabled" });
  const { data, width, height } = PNG.sync.read(screenshot);
  const sampleStep = Math.max(1, Math.floor(Math.min(width, height) / 180));
  const baseR = data[0];
  const baseG = data[1];
  const baseB = data[2];
  let varied = 0;
  let sampled = 0;

  for (let y = 0; y < height; y += sampleStep) {
    for (let x = 0; x < width; x += sampleStep) {
      const index = (y * width + x) * 4;
      sampled += 1;
      if (
        Math.abs(data[index] - baseR) > 8 ||
        Math.abs(data[index + 1] - baseG) > 8 ||
        Math.abs(data[index + 2] - baseB) > 8
      ) {
        varied += 1;
      }
    }
  }

  return sampled > 0 && varied / sampled > 0.03;
}

test("renders a nonblank 3D battlefield and core controls", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle("玄甲棋局");
  await expect(page.getByRole("heading", { name: "阵中对弈" })).toBeVisible();
  await expect(page.getByLabel("悔棋")).toBeDisabled();
  await expect(page.locator("canvas")).toBeVisible();
  await page.waitForTimeout(1200);
  expect(await canvasHasRenderedPixels(page)).toBe(true);

  await page.getByLabel("切换顶视").click();
  await expect(page.getByLabel("切换斜视")).toBeVisible();
});

test("keeps the game surface and controls inside a mobile viewport", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);
  const stage = page.getByTestId("scene-stage");
  await expect(stage).toBeVisible();
  await expect(page.locator("canvas")).toBeVisible();
  await expect(page.getByLabel("重新开局")).toBeVisible();
  await expect(page.getByLabel(/特效：/)).toBeVisible();
  expect(await canvasHasRenderedPixels(page)).toBe(true);

  const bodyBox = await page.locator("body").boundingBox();
  expect(bodyBox?.width).toBeLessThanOrEqual(page.viewportSize()!.width);
  expect(bodyBox?.height).toBeLessThanOrEqual(page.viewportSize()!.height);
});

test("plays, undoes and restarts a move through the mobile 3D board", async (
  { page },
  testInfo,
) => {
  test.skip(testInfo.project.name !== "mobile-chromium");
  await page.goto("/");
  await page.waitForTimeout(1600);
  await expect(page.getByRole("switch", { name: "关闭镜头震动" })).toBeVisible();

  const canvasBox = await page.locator("canvas").boundingBox();
  expect(canvasBox).not.toBeNull();
  const x = canvasBox!.x + canvasBox!.width / 2;
  const selectY = canvasBox!.y + canvasBox!.height * 0.588;
  const targetY = canvasBox!.y + canvasBox!.height * 0.531;

  const playFirstMove = async () => {
    await page.mouse.click(x, selectY);
    await page.waitForTimeout(120);
    await page.mouse.click(x, targetY);
    await expect(page.getByText("兵五进1")).toBeVisible();
    await expect(page.getByLabel("悔棋")).toBeEnabled();
  };

  await playFirstMove();
  await page.getByLabel("悔棋").click();
  await expect(page.getByLabel("悔棋")).toBeDisabled();
  await expect(page.getByText("兵五进1")).toHaveCount(0);

  await playFirstMove();
  await page.getByLabel("重新开局").click();
  const dialog = page.getByRole("alertdialog", { name: "重新布阵？" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "重新开局" }).click();
  await expect(page.getByLabel("悔棋")).toBeDisabled();
  await expect(page.getByText("兵五进1")).toHaveCount(0);
});

test("resumes the current game after a page reload", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-chromium");
  await page.goto("/");
  await page.waitForTimeout(1600);
  await expect(page.getByRole("switch", { name: "关闭镜头震动" })).toBeVisible();

  const canvasBox = await page.locator("canvas").boundingBox();
  expect(canvasBox).not.toBeNull();
  const x = canvasBox!.x + canvasBox!.width / 2;
  const selectY = canvasBox!.y + canvasBox!.height * 0.588;
  const targetY = canvasBox!.y + canvasBox!.height * 0.531;

  await page.mouse.click(x, selectY);
  await page.waitForTimeout(120);
  await page.mouse.click(x, targetY);
  await expect(page.getByText("兵五进1")).toBeVisible();
  await expect(page.getByLabel("悔棋")).toBeEnabled();

  await page.reload();
  await page.waitForTimeout(1600);
  await expect(page.getByRole("heading", { name: "阵中对弈" })).toBeVisible();
  await expect(page.getByText("兵五进1")).toBeVisible();
  await expect(page.getByLabel("悔棋")).toBeEnabled();

  await page.getByLabel("悔棋").click();
  await expect(page.getByLabel("悔棋")).toBeDisabled();
  await expect(page.getByText("兵五进1")).toHaveCount(0);
});
