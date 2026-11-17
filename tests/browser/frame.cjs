/* Run: NODE_PATH=<temporary playwright install>/node_modules PIFRAME_TEST_PYTHON=venv/bin/python node tests/browser/frame.cjs */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {execFileSync} = require('node:child_process');
const {chromium} = require('playwright');
const templates = JSON.parse(execFileSync(process.env.PIFRAME_TEST_PYTHON || 'venv/bin/python', ['-c', `
import json
from jinja2 import Environment, FileSystemLoader, select_autoescape
env=Environment(loader=FileSystemLoader('templates'),autoescape=select_autoescape())
print(json.dumps({name:env.get_template(name+'.html').render(refresh_interval=600,weather_available=False,forecast=[]) for name in ('picture','fullscreen')}))
`], {encoding:'utf8'}));
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1sAAAAASUVORK5CYII=', 'base64');
const token = n => String(n).repeat(32);
const photoPath = n => '/random-picture/snapshots/' + token(n);
const metadata = n => ({picture_url:photoPath(n),creation_date:'photo '+n,creation_time:'12:00',image_id:String(n)});
async function main() {
    const browser = await chromium.launch({headless:true, ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? {executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}: {})});
    try {
        async function setup(handler) {
            const page = await browser.newPage();
            let pictureLoads = 0, weatherLoads = 0;
            const errors = [];
            page.on('pageerror', e => errors.push(e.message));
            await page.route('http://frame.test/**', async route => {
                const path = new URL(route.request().url()).pathname;
                if (path === '/picture') {
                    pictureLoads++;
                    return route.fulfill({contentType:'text/html',body:templates.picture.replace('data-refresh-ms="600000"','data-refresh-ms="600000" data-timeout-ms="150" data-retry-ms="20" data-weather-ms="50"')});
                }
                if (path === '/fullscreen') {
                    // The previous parent timer would recreate the iframe every100ms.
                    return route.fulfill({contentType:'text/html',body:templates.fullscreen.replace(/600000/g,'100')});
                }
                if (path === '/static/js/frame.js') { return route.fulfill({contentType:'text/javascript',body:fs.readFileSync('static/js/frame.js','utf8')}); }
                if (path === '/weather/cached-overlay') {
                    weatherLoads++;
                    return route.fulfill({contentType:'text/html',body:'<span>weather '+weatherLoads+'</span>'});
                }
                return handler(route,path);
            });
            return {page,errors,counts:()=>({pictureLoads,weatherLoads})};
        }
        // Failed image, then a hung retry: A remains visible until C succeeds.
        let calls = 0, hungRetry;
        const hung = new Promise(resolve => { hungRetry = resolve; });
        const first = await setup(async (route,path) => {
            if (path === '/random-picture/metadata') {
                calls++;
                if (calls === 3) { hungRetry(); return; }
                return route.fulfill({json:metadata(calls >= 4 ? 3 : calls)});
            }
            if (path === photoPath(2)) { return route.fulfill({status:503,body:'unavailable'}); }
            return route.fulfill({contentType:'image/png',body:png});
        });
        await first.page.goto('http://frame.test/picture');
        await first.page.waitForFunction(() => document.getElementById('creation-date').textContent === 'photo 1');
        await first.page.evaluate(() => {
            window.swaps = [];
            new MutationObserver(() => window.swaps.push(document.getElementById('frame-photo').getAttribute('src'))).observe(document.body,{childList:true});
            window.photoFrame.refresh();
        });
        await hung;
        assert.match(await first.page.locator('#frame-photo').getAttribute('src'), new RegExp(token(1)));
        assert(await first.page.locator('#frame-photo').isVisible());
        await first.page.waitForFunction(() => document.getElementById('creation-date').textContent === 'photo 3');
        assert.deepEqual(await first.page.evaluate(() => window.swaps),[photoPath(3)]);
        assert(first.counts().weatherLoads >= 2);
        assert.deepEqual(first.errors,[]);
        await first.page.close();
        // A late image completion from a canceled attempt must not replace C.
        let imageB, releaseB, call = 0;
        const requestedB = new Promise(resolve => { imageB = resolve; });
        const release = new Promise(resolve => { releaseB = resolve; });
        const second = await setup(async (route,path) => {
            if (path === '/random-picture/metadata') { return route.fulfill({json:metadata(++call)}); }
            if (path === photoPath(2)) { imageB(); await release; }
            try { await route.fulfill({contentType:'image/png',body:png}); } catch (_) { /* browser aborted stale candidate */ }
        });
        await second.page.goto('http://frame.test/fullscreen');
        const child = second.page.frameLocator('#picFrame');
        await child.locator('#creation-date').filter({hasText:'photo 1'}).waitFor();
        await child.locator('body').evaluate(() => window.photoFrame.refresh());
        await requestedB;
        await child.locator('#creation-date').filter({hasText:'photo 3'}).waitFor();
        releaseB();
        await second.page.waitForTimeout(250); // Cross multiple former parent refresh intervals.
        assert.equal(await child.locator('#creation-date').textContent(),'photo 3');
        assert.equal(second.counts().pictureLoads,1);
        assert(second.counts().weatherLoads >= 2);
        await child.locator('body').evaluate(() => {
            window.dispatchEvent(new PageTransitionEvent('pagehide'));
            window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted:true}));
        });
        await child.locator('#creation-date').filter({hasText:'photo 4'}).waitFor();
        assert.deepEqual(second.errors,[]);
        await second.page.close();
        console.log('PASS: failed/hung retries retain A; recovery swaps C; stale callbacks ignored; iframe persists; weather refreshes');
    } finally { await browser.close(); }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
