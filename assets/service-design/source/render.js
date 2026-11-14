const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [svgPath, out, scale] = process.argv.slice(2);
  const svg = fs.readFileSync(svgPath, 'utf8');
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: Number(scale || 2) });
  await p.setContent(`<html><head><style>html,body{margin:0;background:transparent}</style></head><body>${svg}</body></html>`);
  await p.waitForTimeout(300);
  await p.locator('svg').screenshot({ path: out, omitBackground: true });
  await b.close();
})();
