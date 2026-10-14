const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function main() {
  const screenshotsDir = path.resolve(__dirname, '../../screenshots');
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir, { recursive: true });
  }

  console.log('Launching browser...');
  const browser = await chromium.launch({
    channel: 'msedge', // use system Edge
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  const pages = [
    { url: 'http://localhost:5173/regions', lightName: 'regions_light_1440.png', darkName: 'regions_dark_1440.png' },
    { url: 'http://localhost:5173/opportunities', lightName: 'explore_light_1440.png', darkName: 'explore_dark_1440.png' },
    { url: 'http://localhost:5173/history', lightName: 'history_light_1440.png', darkName: 'history_dark_1440.png' },
  ];

  for (const p of pages) {
    console.log(`Navigating to ${p.url}...`);
    await page.goto(p.url, { waitUntil: 'networkidle', timeout: 30000 });
    // wait an extra second for state animations
    await page.waitForTimeout(1500);

    // Ensure light mode
    await page.evaluate(() => document.documentElement.classList.remove('dark'));
    await page.waitForTimeout(500);

    const lightPath = path.join(screenshotsDir, p.lightName);
    await page.screenshot({ path: lightPath, fullPage: false });
    const lightSize = fs.statSync(lightPath).size;
    console.log(`Saved ${p.lightName} (${lightSize.toLocaleString()} bytes)`);

    // Toggle dark mode
    await page.evaluate(() => document.documentElement.classList.add('dark'));
    await page.waitForTimeout(500);

    const darkPath = path.join(screenshotsDir, p.darkName);
    await page.screenshot({ path: darkPath, fullPage: false });
    const darkSize = fs.statSync(darkPath).size;
    console.log(`Saved ${p.darkName} (${darkSize.toLocaleString()} bytes)`);
  }

  await browser.close();
  console.log('All screenshots captured successfully!');
}

main().catch((err) => {
  console.error('Error in capture_screenshots:', err);
  process.exit(1);
});
