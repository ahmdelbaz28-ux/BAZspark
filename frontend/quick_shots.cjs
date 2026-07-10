const { chromium } = require('playwright');
const fs = require('fs');
const D = '/home/z/my-project/download/screenshots';
const KEY = 'test-admin-key-1234567890abcdef1234567890abcdef';
const BASE = 'http://127.0.0.1:4173';
fs.mkdirSync(D, { recursive: true });
const PAGES = [
	['/login','01_login'], ['/dashboard','02_dashboard'], ['/projects','03_projects'],
	['/engineering','04_engineering'], ['/marine','05_marine'], ['/facp','06_facp'],
	['/environment','07_environment'], ['/monitor','08_monitor'], ['/memory','09_memory'],
	['/graphrag','10_graphrag'], ['/reports','11_reports'], ['/reports/generate','12_report_gen'],
	['/elements','13_elements'], ['/conflicts','14_conflicts'], ['/connections','15_connections'],
	['/revit','16_revit'], ['/autocad','17_autocad'], ['/settings','18_settings'],
	['/digital-twin','19_digital_twin'], ['/fire-alarm','20_fire_alarm'],
];
(async () => {
	const b = await chromium.launch({ headless: true });
	const c = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
	const p = await c.newPage();
	// Login via API
	const r = await c.request.post(`${BASE}/api/v1/auth/login`, {
		data: { api_key: KEY }, headers: { 'Content-Type': 'application/json' }
	});
	console.log(`Login: ${r.status()}`);
	let pass = 0, fail = 0;
	for (const [path, name] of PAGES) {
		process.stdout.write(`  ${name}... `);
		try {
			if (path === '/login') await c.clearCookies();
			await p.goto(`${BASE}${path}`, { waitUntil: 'load' });
			await p.waitForTimeout(2500);
			const url = p.url();
			if (url.includes('/login') && path !== '/login') { console.log('❌ REDIRECT'); fail++; continue; }
			await p.screenshot({ path: `${D}/${name}.png` });
			console.log('✅'); pass++;
		} catch (e) { console.log(`❌ ${e.message.slice(0,50)}`); fail++; }
	}
	console.log(`\nPASS: ${pass} | FAIL: ${fail}`);
	await b.close();
})();
