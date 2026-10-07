import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const outDir = 'C:/Users/ASUS/web-video-clipper/anti-slop/evidence-studio-refresh';
mkdirSync(outDir, { recursive: true });

async function main() {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: true,
  });

  const viewports = [
    { name: 'studio-1440.png', width: 1440, height: 900 },
    { name: 'studio-768.png', width: 768, height: 1024 },
    { name: 'studio-390.png', width: 390, height: 844 },
    { name: 'studio-320.png', width: 320, height: 640 },
  ];

  for (const vp of viewports) {
    const page = await browser.newPage({
      viewport: { width: vp.width, height: vp.height },
    });
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });
    // Wait a brief moment for fonts and layouts to settle
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${outDir}/${vp.name}`, fullPage: false });
    console.log(`Captured ${vp.name} (${vp.width}x${vp.height})`);
    await page.close();
  }

  // Also capture the Preset Gallery Modal open state on 1440px
  const modalPage = await browser.newPage({
    viewport: { width: 1440, height: 900 },
  });
  await modalPage.goto('http://localhost:5173', { waitUntil: 'networkidle' });
  await modalPage.waitForTimeout(500);
  // Click "Buka Galeri Lengkap" button
  const galleryBtn = modalPage.locator('button:has-text("Buka Galeri Lengkap")').first();
  if (await galleryBtn.isVisible()) {
    await galleryBtn.click();
    await modalPage.waitForTimeout(600);
    await modalPage.screenshot({ path: `${outDir}/studio-1440-gallery-modal.png` });
    console.log('Captured studio-1440-gallery-modal.png');
  }
  await modalPage.close();

  await browser.close();
  console.log('All QA screenshots captured successfully!');
}

main().catch((err) => {
  console.error('Capture error:', err);
  process.exit(1);
});
