const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function main() {
  const screenshotsDir = path.resolve(__dirname, '../../screenshots');
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir, { recursive: true });
  }

  console.log('Launching browser for assistant screenshots...');
  const browser = await chromium.launch({
    channel: 'msedge',
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  console.log('Navigating to http://localhost:5173/assistant...');
  await page.goto('http://localhost:5173/assistant', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  // 1. Initial State Light Mode
  await page.evaluate(() => document.documentElement.classList.remove('dark'));
  await page.waitForTimeout(500);
  const p1 = path.join(screenshotsDir, 'assistant_full_light_1440.png');
  await page.screenshot({ path: p1 });
  console.log('Saved assistant_full_light_1440.png');

  // 2. Initial State Dark Mode
  await page.evaluate(() => document.documentElement.classList.add('dark'));
  await page.waitForTimeout(500);
  const p2 = path.join(screenshotsDir, 'assistant_full_dark_1440.png');
  await page.screenshot({ path: p2 });
  console.log('Saved assistant_full_dark_1440.png');

  // Back to light mode and ask "What changed since yesterday?"
  await page.evaluate(() => document.documentElement.classList.remove('dark'));
  await page.waitForTimeout(300);

  // Click chip: "What changed since yesterday?"
  const chip1 = page.locator('button:has-text("What changed since yesterday?")').first();
  if (await chip1.isVisible()) {
    console.log('Clicking chip: What changed since yesterday?');
    await chip1.click();
    await page.waitForTimeout(3000);
  }

  // Ask chip: "Which region lost the most Commit?"
  const chip2 = page.locator('button:has-text("Which region lost the most Commit?")').first();
  if (await chip2.isVisible()) {
    console.log('Clicking chip: Which region lost the most Commit?');
    await chip2.click();
    await page.waitForTimeout(3000);
  }

  // Ask chip: "Top 10 opportunities in Middle East"
  const chip3 = page.locator('button:has-text("Top 10 opportunities in Middle East")').first();
  if (await chip3.isVisible()) {
    console.log('Clicking chip: Top 10 opportunities in Middle East');
    await chip3.click();
    await page.waitForTimeout(3500);
  }

  // Ask chip: "How many deals are Pending Approval?"
  const inputEl = page.locator('#assistant-chat-input');
  await inputEl.fill('How many deals are Pending Approval?');
  await page.locator('#assistant-chat-send').click();
  await page.waitForTimeout(3000);

  // Ask history chip: "Show history of 006Qp00000as0WCIAY"
  await inputEl.fill('Show history of 006Qp00000as0WCIAY');
  await page.locator('#assistant-chat-send').click();
  await page.waitForTimeout(3000);

  // Take screenshot with full conversations in light mode
  const p3 = path.join(screenshotsDir, 'assistant_conversation_light_1440.png');
  await page.screenshot({ path: p3 });
  console.log('Saved assistant_conversation_light_1440.png');

  // Take screenshot with full conversations in dark mode
  await page.evaluate(() => document.documentElement.classList.add('dark'));
  await page.waitForTimeout(500);
  const p4 = path.join(screenshotsDir, 'assistant_conversation_dark_1440.png');
  await page.screenshot({ path: p4 });
  console.log('Saved assistant_conversation_dark_1440.png');

  // Now test Docked Panel on an existing page e.g. / (Dashboard)
  console.log('Navigating to http://localhost:5173/ to capture docked panel...');
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(1500);

  // Open docked assistant via topbar button or shortcut
  const toggleBtn = page.locator('#topbar-assistant-toggle');
  if (await toggleBtn.isVisible()) {
    await toggleBtn.click();
    await page.waitForTimeout(1000);
  }

  // Dark mode docked screenshot
  const p5 = path.join(screenshotsDir, 'assistant_docked_dark_1440.png');
  await page.screenshot({ path: p5 });
  console.log('Saved assistant_docked_dark_1440.png');

  // Light mode docked screenshot
  await page.evaluate(() => document.documentElement.classList.remove('dark'));
  await page.waitForTimeout(500);
  const p6 = path.join(screenshotsDir, 'assistant_docked_light_1440.png');
  await page.screenshot({ path: p6 });
  console.log('Saved assistant_docked_light_1440.png');

  await browser.close();
  console.log('All assistant screenshots captured successfully!');
}

main().catch((err) => {
  console.error('Error in capture_assistant_screenshots:', err);
  process.exit(1);
});
