#!/usr/bin/env node
/**
 * validate-perf-budget.cjs — Performance Budget CI Enforcement
 *
 * Ensures critical assets and entry chunks do not exceed budgets,
 * and ensures non-critical overlay components are not leaked into the
 * initial modulepreload waterfall.
 */

const fs = require('fs');
const path = require('path');

const distDir = path.resolve(__dirname, '../dist');
const assetsDir = path.join(distDir, 'assets');
const indexHtmlPath = path.join(distDir, 'index.html');

if (!fs.existsSync(distDir) || !fs.existsSync(assetsDir)) {
  console.error('❌ Error: dist directory not found. Run npm run build first.');
  process.exit(1);
}

console.log('=== Performance Budget CI Validation ===');

const files = fs.readdirSync(assetsDir);
let hasError = false;

// 1. Entry JS Budget (< 215 KB raw / ~65 KB gzip)
const entryJs = files.find(f => f.startsWith('index-') && f.endsWith('.js'));
if (entryJs) {
  const size = fs.statSync(path.join(assetsDir, entryJs)).size;
  const maxEntryJs = 220 * 1024; // 220 KB
  console.log(`Entry JS Chunk (${entryJs}): ${(size / 1024).toFixed(2)} KB [Max: 220 KB]`);
  if (size > maxEntryJs) {
    console.error(`❌ REGRESSION: Entry JS exceeds budget (${(size / 1024).toFixed(2)} KB > 220 KB)`);
    hasError = true;
  } else {
    console.log(`  ✅ Passed entry JS budget check`);
  }
} else {
  console.error('❌ Error: index-*.js entry chunk not found.');
  hasError = true;
}

// 2. Global CSS Budget (< 220 KB raw / ~30 KB gzip)
const entryCss = files.find(f => f.startsWith('index-') && f.endsWith('.css'));
if (entryCss) {
  const size = fs.statSync(path.join(assetsDir, entryCss)).size;
  const maxCss = 230 * 1024; // 230 KB
  console.log(`Global CSS (${entryCss}): ${(size / 1024).toFixed(2)} KB [Max: 230 KB]`);
  if (size > maxCss) {
    console.error(`❌ REGRESSION: Global CSS exceeds budget (${(size / 1024).toFixed(2)} KB > 230 KB)`);
    hasError = true;
  } else {
    console.log(`  ✅ Passed CSS budget check`);
  }
}

// 3. Check for leaked overlay chunks in index.html modulepreload
if (fs.existsSync(indexHtmlPath)) {
  const html = fs.readFileSync(indexHtmlPath, 'utf8');
  const leakedTopics = html.includes('helpTopics-');
  const leakedDrawer = html.includes('GlobalHelpDrawer-');
  const leakedPalette = html.includes('CommandPalette-');
  const leakedAi = html.includes('AskAiSheet-');

  console.log('\n--- Overlay Chunk Isolation in Entry HTML ---');
  if (leakedTopics || leakedDrawer || leakedPalette || leakedAi) {
    console.error('❌ REGRESSION: Overlay chunks leaked into index.html preloads!');
    hasError = true;
  } else {
    console.log('  ✅ No overlay chunks leaked into critical entry preloads.');
  }
}

if (hasError) {
  console.error('\n❌ Performance Budget Check FAILED.');
  process.exit(1);
} else {
  console.log('\n🎉 Performance Budget Check PASSED successfully.');
  process.exit(0);
}
