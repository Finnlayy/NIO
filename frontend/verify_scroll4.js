const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    recordVideo: { dir: '/home/jules/verification/videos' }
  });
  const page = await context.newPage();
  await page.goto('http://localhost:4001');

  // Wait for the grid to load
  await page.waitForTimeout(2000);

  // Scroll down to see Pattern Scanner and Cvd Heatmap
  await page.evaluate(() => window.scrollTo(0, 800));

  await page.waitForTimeout(2000);

  if (!fs.existsSync('/home/jules/verification/screenshots')) {
    fs.mkdirSync('/home/jules/verification/screenshots', { recursive: true });
  }

  await page.screenshot({ path: '/home/jules/verification/screenshots/verification4.png' });

  const videoPath = await page.video().path();
  await context.close();
  await browser.close();

  console.log(`Screenshot saved to /home/jules/verification/screenshots/verification4.png`);
  console.log(`Video saved to ${videoPath}`);
})();
