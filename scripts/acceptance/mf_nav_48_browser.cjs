#!/usr/bin/env node
// Synthetic browser acceptance for cache-first provisional MF NAV (#48 / #54).
// Drives the real React UI (Vite) against the SQLite acceptance backend started by
// mf_nav_48_server.py. Writes <run-dir>/acceptance-results.json and screenshots.
//
// Usage (repo root):
//   PLAYWRIGHT_MODULE=/path/to/node_modules/playwright \
//   node scripts/acceptance/mf_nav_48_browser.cjs --run-dir /tmp/kp-mfnav-48/run1 \
//     --frontend http://127.0.0.1:15173
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const arg = (name, fallback) => {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : fallback;
};
const RUN_DIR = path.resolve(arg('--run-dir', '/tmp/kp-mfnav-48/run1'));
const FRONTEND = arg('--frontend', 'http://127.0.0.1:15173');
const REPO_ROOT = path.resolve(__dirname, '..', '..');
const SHOTS = path.join(RUN_DIR, 'screenshots');
fs.mkdirSync(SHOTS, { recursive: true });

const server = JSON.parse(fs.readFileSync(path.join(RUN_DIR, 'server.json'), 'utf8'));
const { users, password, portfolios, schemes } = server.fixtures;
const ALPHA = '990101';
const BETA = '990202';
const GAMMA = '990303';

const results = [];
let current = 'setup';
function check(name, ok, detail = undefined) {
  results.push({ scenario: current, check: name, ok: Boolean(ok), ...(detail === undefined ? {} : { detail }) });
  console.log(`${ok ? 'PASS' : 'FAIL'} [${current}] ${name}${detail === undefined ? '' : ` — ${JSON.stringify(detail)}`}`);
}
function readJsonl(name) {
  const file = path.join(RUN_DIR, name);
  if (!fs.existsSync(file)) return [];
  return fs.readFileSync(file, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
}
const providerCalls = () => readJsonl('provider_calls.jsonl');
const blockedNetwork = () => readJsonl('blocked_network.jsonl');
function updateBook(mutator) {
  const file = path.join(RUN_DIR, 'provider_book.json');
  const book = JSON.parse(fs.readFileSync(file, 'utf8'));
  mutator(book);
  fs.writeFileSync(file, JSON.stringify(book, null, 2));
}

async function api(page, method, url, body = undefined, { csrf = true } = {}) {
  return page.evaluate(async ({ method, url, body, csrf }) => {
    const m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    const headers = { 'Content-Type': 'application/json' };
    if (csrf && m) headers['X-CSRFToken'] = decodeURIComponent(m[1]);
    const r = await fetch(`/api/v1${url}`, {
      method, headers, credentials: 'same-origin',
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    let data = null;
    try { data = await r.json(); } catch { data = null; }
    return { status: r.status, data };
  }, { method, url, body, csrf });
}

async function shot(page, name) {
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });
}

async function login(page, username) {
  await page.goto(`${FRONTEND}/login`);
  await page.fill('#login-identifier', username);
  await page.fill('#login-password', password);
  await page.locator('form button[type=submit]').click();
  await page.waitForURL(/\/(dashboard|app)?/, { timeout: 15000 });
  await page.getByLabel('portfolio-view').waitFor({ timeout: 15000 });
}

async function selectScope(page, scope) {
  const value = scope === 'all' ? 'all' : `portfolio:${scope}`;
  await page.getByLabel('portfolio-view').selectOption(value);
  await page.waitForLoadState('networkidle');
}

async function gotoPath(page, route) {
  await page.getByRole('navigation').first().waitFor();
  await page.evaluate((r) => { window.history.pushState({}, '', r); window.dispatchEvent(new PopStateEvent('popstate')); }, route);
  await page.waitForLoadState('networkidle');
}

async function allTransactions(page) {
  const res = await api(page, 'GET', '/transactions?portfolio_scope=all&page_size=100');
  return res.data.items;
}

const modal = (page) => page.locator('.modal-content');

async function openMfForm(page, { portfolioId, scheme, folio, type, investmentDate, navDate }) {
  await gotoPath(page, '/transactions');
  await page.getByRole('button', { name: 'Add Transaction' }).click();
  const m = modal(page);
  await m.getByLabel('record type').selectOption('MUTUAL_FUND');
  await m.getByLabel('portfolio').selectOption(String(portfolioId));
  await m.locator('input[name=scheme_code]').fill(scheme);
  await m.locator('input[name=scheme_name]').fill(schemes[scheme]);
  await m.locator('input[name=folio_number]').fill(folio);
  await m.locator('select[name=type]').selectOption(type);
  await m.locator('input[name=investment_date]').fill(investmentDate);
  await m.locator('input[name=nav_date]').fill(navDate);
  return m;
}

async function lookupStatus(m, expected) {
  const status = m.locator('p[role=status]').first();
  await status.filter({ hasText: expected }).waitFor({ timeout: 10000 });
  return (await status.textContent()).trim();
}

async function fillAmounts(m, values) {
  for (const [name, value] of Object.entries(values)) {
    await m.locator(`input[name=${name}]`).fill(value);
  }
}

async function saveModal(page, m) {
  await m.getByRole('button', { name: 'Save', exact: true }).click();
  await Promise.race([
    m.waitFor({ state: 'detached', timeout: 15000 }),
    m.locator('.modal-error').waitFor({ timeout: 15000 }).then(async () => {
      throw new Error(`modal error: ${await m.locator('.modal-error').textContent()}`);
    }),
  ]);
  await page.waitForLoadState('networkidle');
}

async function provisionalEntry(m, { nav, expectedMarket, checkboxes = true }) {
  const group = m.getByRole('group', { name: 'Provisional NAV entry' });
  await group.waitFor({ timeout: 10000 });
  await group.locator('#provisional-mf-nav').fill(nav);
  await group.getByRole('button', { name: 'Get market value' }).click();
  const msg = group.getByText(/Market value from server:/);
  await msg.waitFor({ timeout: 10000 });
  const text = (await msg.textContent()).trim();
  check('server market value shown', text.includes(expectedMarket), text);
  check('market value field is read-only server value',
    (await m.locator('input[name=market_value]').inputValue()) === expectedMarket &&
    (await m.locator('input[name=market_value]').getAttribute('readonly')) !== null,
    await m.locator('input[name=market_value]').inputValue());
  if (checkboxes) {
    const boxes = group.locator('input[type=checkbox]');
    const saveBtn = m.getByRole('button', { name: 'Save', exact: true });
    check('save blocked before confirmations', await saveBtn.isDisabled());
    await boxes.nth(0).check();
    await boxes.nth(1).check();
    check('save enabled after both confirmations', await saveBtn.isEnabled());
  }
}

async function editRow(page, txnId) {
  await gotoPath(page, '/transactions');
  const row = page.locator('tr').filter({ has: page.getByLabel(`Select transaction ${txnId}`) });
  await row.locator('button[title=Edit]').click();
  return modal(page);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  const consoleErrors = [];
  const httpErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push({ scenario: current, text: msg.text() });
  });
  page.on('response', (r) => {
    if (r.status() >= 400) {
      httpErrors.push({ scenario: current, status: r.status(), method: r.request().method(),
        url: r.url().replace(FRONTEND, '') });
    }
  });
  const evidence = { started_at: new Date().toISOString(), frontend: FRONTEND, server: {
    pid: server.pid, cwd: server.cwd, checkout: server.checkout, database: server.database,
    required_migrations_applied: server.required_migrations_applied } };
  const ids = {};
  try {
    current = 'served-checkout';
    const listener = (port) => {
      const pid = execFileSync('lsof', ['-nP', '-t', `-iTCP:${port}`, '-sTCP:LISTEN'], { encoding: 'utf8' })
        .trim().split('\n')[0];
      const cwd = execFileSync('lsof', ['-a', '-p', pid, '-d', 'cwd', '-Fn'], { encoding: 'utf8' })
        .split('\n').find((l) => l.startsWith('n')).slice(1);
      const head = execFileSync('git', ['rev-parse', 'HEAD'], { cwd, encoding: 'utf8' }).trim();
      const top = execFileSync('git', ['rev-parse', '--show-toplevel'], { cwd, encoding: 'utf8' }).trim();
      return { port, pid: Number(pid), cwd, git_toplevel: top, git_head: head };
    };
    evidence.listeners = { backend: listener(server.port), frontend: listener(new URL(FRONTEND).port) };
    const localHead = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: REPO_ROOT, encoding: 'utf8' }).trim();
    check('backend and frontend listeners run from this checkout and commit',
      Object.values(evidence.listeners).every((l) => fs.realpathSync(l.git_toplevel) === fs.realpathSync(REPO_ROOT) &&
        l.git_head === localHead) && evidence.listeners.backend.pid === server.pid, evidence.listeners);
    const health = await (await fetch(`${FRONTEND}/api/v1/health`)).json();
    check('health via Vite proxy', health.status === 'ok' && health.database === 'ok', health);
    check('backend database is the disposable SQLite file in the run dir',
      server.database.vendor === 'sqlite' &&
      path.dirname(server.database.name) === fs.realpathSync(RUN_DIR), server.database);
    check('both new migrations applied on acceptance DB',
      Object.values(server.required_migrations_applied).every(Boolean), server.required_migrations_applied);

    await login(page, users.acceptance.username);
    await shot(page, '00-dashboard-empty');

    // --- 1. cache hit / no provider ---------------------------------------------------
    current = '1-cache-hit-no-provider';
    let calls = providerCalls().length;
    let m = await openMfForm(page, { portfolioId: portfolios.inr, scheme: ALPHA, folio: 'AF-1', type: 'BUY',
      investmentDate: '2026-11-17', navDate: '2026-11-17' });
    check('lookup reports cached NAV', (await lookupStatus(m, 'Cached NAV available.')).length > 0);
    check('NAV field filled from cache', Number(await m.locator('#cached-mf-nav').inputValue()) === 20,
      await m.locator('#cached-mf-nav').inputValue());
    check('no Fetch missing NAV button on cache hit',
      (await m.getByRole('button', { name: 'Fetch missing NAV' }).count()) === 0);
    await fillAmounts(m, { units_allotted: '100', paid_value: '2000', market_value: '2000', fees: '0' });
    await shot(page, '01-cache-hit-form');
    await saveModal(page, m);
    let txns = await allTransactions(page);
    const alphaCache = txns.find((t) => t.scheme_code === ALPHA && t.nav_date === '2026-11-17');
    ids.alphaCache = alphaCache?.id;
    check('cache-path BUY saved with PROVIDER_CACHE source',
      alphaCache?.nav_source === 'PROVIDER_CACHE' && Number(alphaCache?.nav) === 20, alphaCache && {
        id: alphaCache.id, nav: alphaCache.nav, nav_source: alphaCache.nav_source });
    let fetchRes = await api(page, 'POST', '/nav/fetch-missing', { scheme_code: ALPHA, nav_date: '2026-11-17' });
    check('explicit fetch on cached date returns cache_hit', fetchRes.status === 200 && fetchRes.data.outcome === 'cache_hit',
      fetchRes.data);
    check('no provider call for cache hit', providerCalls().length === calls, providerCalls().length - calls);

    // --- 2. missing date / fetch success ---------------------------------------------
    current = '2-missing-date-fetch-success';
    calls = providerCalls().length;
    m = await openMfForm(page, { portfolioId: portfolios.inr, scheme: ALPHA, folio: 'AF-1', type: 'BUY',
      investmentDate: '2026-11-19', navDate: '2026-11-19' });
    await lookupStatus(m, 'No cached NAV for this exact date.');
    check('lookup reports missing exact date', true);
    check('save blocked while NAV missing', await m.getByRole('button', { name: 'Save', exact: true }).isDisabled());
    check('manual NAV entry disabled (read-only cached field)',
      (await m.locator('#cached-mf-nav').getAttribute('readonly')) !== null);
    await m.getByRole('button', { name: 'Fetch missing NAV' }).click();
    await m.getByText('Fetched NAV from MFAPI for this exact date.').waitFor();
    await lookupStatus(m, 'Cached NAV available.');
    check('fetched NAV fills cached field', Number(await m.locator('#cached-mf-nav').inputValue()) === 21.5,
      await m.locator('#cached-mf-nav').inputValue());
    const newCalls = providerCalls().slice(calls);
    check('exactly one provider call for exact scheme/date', newCalls.length === 1 &&
      newCalls[0].scheme_code === ALPHA && newCalls[0].start === '2026-11-19' && newCalls[0].end === '2026-11-19', newCalls);
    await fillAmounts(m, { units_allotted: '50', paid_value: '1075', market_value: '1075', fees: '0' });
    await shot(page, '02-fetch-success-form');
    await saveModal(page, m);
    const lookupAlpha = await api(page, 'GET', `/nav/lookup?scheme_code=${ALPHA}&nav_date=2026-11-19`);
    check('fetched NAV now cached (lookup available)', lookupAlpha.data.status === 'available' &&
      Number(lookupAlpha.data.nav) === 21.5, lookupAlpha.data);

    // --- 3. unavailable + cooldown + provisional BUY --------------------------------
    current = '3-unavailable-cooldown-provisional-buy';
    calls = providerCalls().length;
    m = await openMfForm(page, { portfolioId: portfolios.inr, scheme: BETA, folio: 'BF-1', type: 'BUY',
      investmentDate: '2026-11-18', navDate: '2026-11-18' });
    await lookupStatus(m, 'No cached NAV for this exact date.');
    await m.getByRole('button', { name: 'Fetch missing NAV' }).click();
    await m.getByText('MFAPI has no NAV for this exact date.').waitFor();
    const cooldownText = await m.getByText(/Try again in \d+s\./).textContent();
    check('cooldown countdown shown after date_unavailable', /Try again in \d+s\./.test(cooldownText), cooldownText.trim());
    check('Fetch button disabled during cooldown',
      await m.getByRole('button', { name: 'Fetch missing NAV' }).isDisabled());
    check('one provider call for date_unavailable', providerCalls().length - calls === 1);
    await fillAmounts(m, { units_allotted: '40', paid_value: '610', fees: '0' });
    await provisionalEntry(m, { nav: '15.25', expectedMarket: '610.0000' });
    await shot(page, '03-provisional-buy-form');
    await saveModal(page, m);
    txns = await allTransactions(page);
    const betaBuy = txns.find((t) => t.scheme_code === BETA && t.type === 'BUY');
    ids.betaBuy = betaBuy?.id;
    check('provisional BUY saved with provenance', betaBuy?.nav_source === 'PROVISIONAL_USER' &&
      betaBuy?.nav_provisional === true && Number(betaBuy?.market_value) === 610 &&
      betaBuy?.provisional_failure_reason === 'date_unavailable', betaBuy && {
        id: betaBuy.id, nav: betaBuy.nav, market_value: betaBuy.market_value, nav_source: betaBuy.nav_source,
        provisional_failure_reason: betaBuy.provisional_failure_reason });
    const betaLookup = await api(page, 'GET', `/nav/lookup?scheme_code=${BETA}&nav_date=2026-11-18`);
    check('provisional NAV not written to NAV cache', betaLookup.data.status === 'missing', betaLookup.data);
    let ledger = (await api(page, 'GET', `/cash/ledger?portfolio_id=${portfolios.inr}&page_size=100`)).data.items;
    const betaCash = ledger.filter((e) => e.linked_transaction_id === ids.betaBuy);
    ids.betaCash = betaCash.map((e) => e.id);
    check('provisional BUY settled once from cash (paid value)', betaCash.length === 1 &&
      betaCash[0].amount === -610, betaCash.map((e) => ({ id: e.id, type: e.entry_type, amount: e.amount })));
    await page.locator('tr').filter({ has: page.getByLabel(`Select transaction ${ids.betaBuy}`) })
      .getByText('Provisional NAV — awaiting provider').waitFor();
    check('Transactions list shows provisional review state', true);
    await shot(page, '03b-transactions-provisional');

    calls = providerCalls().length;
    m = await openMfForm(page, { portfolioId: portfolios.inr, scheme: BETA, folio: 'BF-1', type: 'BUY',
      investmentDate: '2026-11-18', navDate: '2026-11-18' });
    await lookupStatus(m, 'No cached NAV for this exact date.');
    await m.getByRole('button', { name: 'Fetch missing NAV' }).click();
    await m.getByText('A recent fetch for this NAV failed.').waitFor();
    check('repeat fetch in a new form returns cooldown', true,
      (await m.getByText('A recent fetch for this NAV failed.').textContent()).trim());
    check('cooldown made no provider call', providerCalls().length === calls);
    check('own cooldown still offers provisional entry',
      (await m.getByRole('group', { name: 'Provisional NAV entry' }).count()) === 1);
    await shot(page, '03c-cooldown-form');
    await m.getByRole('button', { name: 'Cancel' }).click();

    // --- 4. timeout + provisional SELL ----------------------------------------------
    current = '4-timeout-provisional-sell';
    let res = await api(page, 'POST', '/transactions', { asset_type: 'MUTUAL_FUND', scheme_code: GAMMA,
      scheme_name: schemes[GAMMA], folio_number: 'GF-1', type: 'BUY', investment_date: '2026-11-10',
      nav_date: '2026-11-10', units_allotted: '100', paid_value: '3000', market_value: '3000', fees: '0',
      currency: 'INR', portfolio_id: portfolios.inr });
    check('cache-path Gamma BUY seeded through API', res.status === 201 && res.data.nav_source === 'PROVIDER_CACHE',
      { status: res.status, id: res.data?.id });
    res = await api(page, 'POST', '/transactions', { asset_type: 'MUTUAL_FUND', scheme_code: ALPHA,
      scheme_name: schemes[ALPHA], folio_number: 'AF-USD', type: 'BUY', investment_date: '2026-11-17',
      nav_date: '2026-11-17', units_allotted: '10', paid_value: '200', market_value: '200', fees: '0',
      currency: 'INR', portfolio_id: portfolios.usd });
    check('cache-path Alpha BUY in USD-base portfolio', res.status === 201, { status: res.status });
    calls = providerCalls().length;
    m = await openMfForm(page, { portfolioId: portfolios.inr, scheme: GAMMA, folio: 'GF-1', type: 'SELL',
      investmentDate: '2026-11-19', navDate: '2026-11-19' });
    await lookupStatus(m, 'No cached NAV for this exact date.');
    await m.getByRole('button', { name: 'Fetch missing NAV' }).click();
    await m.getByText('MFAPI timed out.').waitFor();
    check('timeout outcome shown with countdown',
      (await m.getByText(/Try again in \d+s\./).count()) === 1);
    check('one provider call for timeout', providerCalls().length - calls === 1);
    await fillAmounts(m, { units_allotted: '20', paid_value: '0', fees: '0' });
    await provisionalEntry(m, { nav: '31', expectedMarket: '620.0000' });
    const proceeds = (await m.locator('.modal-sell-settlement__preview').textContent()).trim();
    check('SELL proceeds calculated by server', proceeds.includes('620.00'), proceeds);
    await shot(page, '04-provisional-sell-form');
    await saveModal(page, m);
    txns = await allTransactions(page);
    const gammaSell = txns.find((t) => t.scheme_code === GAMMA && t.type === 'SELL');
    ids.gammaSell = gammaSell?.id;
    check('provisional SELL saved', gammaSell?.nav_source === 'PROVISIONAL_USER' &&
      gammaSell?.provisional_failure_reason === 'timeout', gammaSell && {
        id: gammaSell.id, nav: gammaSell.nav, nav_source: gammaSell.nav_source,
        provisional_failure_reason: gammaSell.provisional_failure_reason });
    ledger = (await api(page, 'GET', `/cash/ledger?portfolio_id=${portfolios.inr}&page_size=100`)).data.items;
    const sellCash = ledger.filter((e) => e.linked_transaction_id === ids.gammaSell);
    check('SELL proceeds credited once (units × NAV − fees)', sellCash.length === 1 && sellCash[0].amount === 620,
      sellCash.map((e) => ({ type: e.entry_type, amount: e.amount })));
    calls = providerCalls().length;
    fetchRes = await api(page, 'POST', '/nav/fetch-missing', { scheme_code: GAMMA, nav_date: '2026-11-19' });
    check('timeout starts cooldown (API)', fetchRes.data.outcome === 'cooldown' && fetchRes.data.retry_after_seconds > 0,
      fetchRes.data);
    check('cooldown made no provider call', providerCalls().length === calls);

    // --- 5. provisional edit ------------------------------------------------------
    current = '5-provisional-edit';
    m = await editRow(page, ids.betaBuy);
    await m.getByText('Provisional NAV (unverified)').first().waitFor();
    await lookupStatus(m, 'No cached NAV for this exact date.');
    check('edit form keeps provisional NAV', await m.locator('#provisional-mf-nav').inputValue() === '15.25',
      await m.locator('#provisional-mf-nav').inputValue());
    await fillAmounts(m, { units_allotted: '44', paid_value: '671' });
    await provisionalEntry(m, { nav: '15.25', expectedMarket: '671.0000' });
    await shot(page, '05-provisional-edit-form');
    await saveModal(page, m);
    txns = await allTransactions(page);
    const betaEdited = txns.find((t) => t.id === ids.betaBuy);
    check('edit keeps id and provenance, updates units/market value', betaEdited &&
      Number(betaEdited.units_allotted) === 44 && Number(betaEdited.market_value) === 671 &&
      betaEdited.nav_source === 'PROVISIONAL_USER', betaEdited && {
        id: betaEdited.id, units: betaEdited.units_allotted, market_value: betaEdited.market_value });
    ledger = (await api(page, 'GET', `/cash/ledger?portfolio_id=${portfolios.inr}&page_size=100`)).data.items;
    const betaCashAfter = ledger.filter((e) => e.linked_transaction_id === ids.betaBuy);
    check('linked cash updated in place (no orphan rows)', betaCashAfter.length === 1 &&
      betaCashAfter[0].id === ids.betaCash[0] && betaCashAfter[0].amount === -671,
      betaCashAfter.map((e) => ({ id: e.id, amount: e.amount })));

    // --- 6. scope / FX quality / provider-only fund analytics (read-only) -------------
    current = '6-scope-fx-analytics-read-only';
    calls = providerCalls().length;
    const blocked = blockedNetwork().length;
    const banner = 'Current value uses unverified provisional mutual fund NAVs';
    for (const [label, scope, expectBanner] of [['inr', portfolios.inr, true], ['usd', portfolios.usd, false],
      ['all', 'all', true]]) {
      await gotoPath(page, '/dashboard');
      await selectScope(page, scope);
      await page.getByText('Data status', { exact: false }).first().waitFor({ timeout: 15000 }).catch(() => {});
      await page.waitForTimeout(500);
      const shown = (await page.getByText(banner).count()) > 0;
      check(`Dashboard provisional banner ${expectBanner ? 'shown' : 'absent'} (${label} scope)`, shown === expectBanner);
      await shot(page, `06-dashboard-${label}`);
    }
    await gotoPath(page, '/assets');
    await page.getByText('Some mutual fund holdings are valued with unverified provisional NAVs').waitFor();
    check('Assets provisional banner (all scope)', true);
    check('Assets per-row Provisional NAV badges', (await page.getByText('Provisional NAV', { exact: true }).count()) >= 2,
      await page.getByText('Provisional NAV', { exact: true }).count());
    await shot(page, '06-assets-all');

    const scopes = { inr: { portfolio_id: portfolios.inr }, usd: { portfolio_id: portfolios.usd },
      all: { portfolio_scope: 'all' } };
    const scopeEvidence = {};
    const readStatuses = [];
    for (const [label, params] of Object.entries(scopes)) {
      for (const ccy of ['INR', 'USD', 'EUR']) {
        const qs = new URLSearchParams({ ...params, display_currency: ccy }).toString();
        const reads = await Promise.all([
          `/portfolio/summary?${qs}`, `/portfolio/holdings?${qs}`,
          `/portfolio/performance?${qs}&metric=value&range=30D`,
          `/analytics/performance-metrics?${qs}&range=ALL`,
        ].map((url) => api(page, 'GET', url)));
        readStatuses.push(...reads.map((r) => r.status));
        const [s, h, p] = reads.map((r) => r.data);
        scopeEvidence[`${label}/${ccy}`] = { current_value: s.current_value, fx_status: s.fx_status,
          nav_provisional: Boolean(s.nav_provisional), holdings_nav_provisional: Boolean(h.nav_provisional),
          performance_warning: (p.warnings || []).some((w) => w.includes('provisional')) };
      }
    }
    evidence.scope_evidence = scopeEvidence;
    check('all scope/currency reads return 200', readStatuses.every((st) => st === 200), readStatuses);
    check('INR & all scopes flag provisional; USD scope does not',
      scopeEvidence['inr/INR'].nav_provisional && scopeEvidence['all/INR'].nav_provisional &&
      !scopeEvidence['usd/INR'].nav_provisional && scopeEvidence['all/INR'].holdings_nav_provisional &&
      scopeEvidence['all/INR'].performance_warning && !scopeEvidence['usd/INR'].performance_warning,
      { inr: scopeEvidence['inr/INR'], usd: scopeEvidence['usd/INR'], all: scopeEvidence['all/INR'] });
    check('cached INR↔USD FX: USD display ok in every scope',
      ['inr', 'usd', 'all'].every((l) => scopeEvidence[`${l}/USD`].fx_status === 'ok' &&
        scopeEvidence[`${l}/USD`].current_value != null),
      ['inr', 'usd', 'all'].map((l) => scopeEvidence[`${l}/USD`]));
    check('missing EUR FX flagged fx_unavailable', ['inr', 'all'].every((l) =>
      scopeEvidence[`${l}/EUR`].fx_status === 'fx_unavailable'),
      ['inr', 'all'].map((l) => scopeEvidence[`${l}/EUR`]));
    await gotoPath(page, '/dashboard');
    await selectScope(page, 'all');
    await page.getByLabel('display-currency').selectOption('EUR');
    await page.getByRole('alert').filter({ hasText: 'FX unavailable for one or more dates.' })
      .waitFor({ timeout: 15000 });
    check('Dashboard FX-unavailable banner with EUR display (no EUR FX cached)', true);
    await shot(page, '06-dashboard-all-eur-fx');
    await page.getByLabel('display-currency').selectOption('INR');
    await page.waitForLoadState('networkidle');

    const assetQs = (folio) => new URLSearchParams({ portfolio_scope: 'all', display_currency: 'INR',
      range: 'ALL', folio_number: folio }).toString();
    const betaMetrics = (await api(page, 'GET', `/analytics/assets/${BETA}/performance-metrics?${assetQs('BF-1')}`)).data;
    const alphaMetrics = (await api(page, 'GET', `/analytics/assets/${ALPHA}/performance-metrics?${assetQs('AF-1')}`)).data;
    check('fund analytics provider-only for provisional fund', betaMetrics.fund_nav_source === 'PROVIDER_CACHE' &&
      betaMetrics.personal_metrics?.nav_provisional === true, {
        fund_nav_source: betaMetrics.fund_nav_source, personal_nav_provisional: betaMetrics.personal_metrics?.nav_provisional,
        cumulative_return: betaMetrics.metrics?.return?.cumulative_return ?? null });
    check('provider-only fund has no fund series from provisional NAV',
      betaMetrics.metrics?.return?.cumulative_return == null, betaMetrics.coverage ?? null);
    check('cached fund analytics unaffected and not flagged', alphaMetrics.fund_nav_source === 'PROVIDER_CACHE' &&
      alphaMetrics.personal_metrics?.nav_provisional === false &&
      alphaMetrics.metrics?.return?.cumulative_return != null,
      { cumulative_return: alphaMetrics.metrics?.return?.cumulative_return });
    await gotoPath(page, `/assets/${BETA}?folio_number=BF-1`);
    await page.getByText('Includes provisional NAV').first().waitFor({ timeout: 15000 });
    check('Asset Detail badges Your Position "Includes provisional NAV"', true);
    check('Asset Detail states fund performance is provider-only',
      (await page.getByText('Fund performance uses cached provider NAV history only').count()) > 0);
    await shot(page, '06-asset-detail-beta');
    const compare = await api(page, 'GET', `/analytics/compare?${new URLSearchParams({
      subjects: `asset:${ALPHA},asset:${BETA}`, portfolio_scope: 'all', display_currency: 'INR', range: 'ALL' })}`);
    const [cmpAlpha, cmpBeta] = compare.data?.subjects || [];
    check('Compare: provider-only fund series, provisional flagged only on Your Position',
      compare.status === 200 && cmpAlpha?.fund_nav_source === 'PROVIDER_CACHE' &&
      cmpBeta?.fund_nav_source === 'PROVIDER_CACHE' && cmpAlpha?.personal_metrics?.nav_provisional === false &&
      cmpBeta?.personal_metrics?.nav_provisional === true, { status: compare.status,
        subjects: (compare.data?.subjects || []).map((x) => [x.fund_nav_source, x.personal_metrics?.nav_provisional]) });
    check('read paths made no provider call', providerCalls().length === calls, providerCalls().length - calls);
    check('read paths attempted no external network', blockedNetwork().length === blocked,
      blockedNetwork().slice(blocked));
    check('NAV cache unchanged by reads', (await api(page, 'GET',
      `/nav/lookup?scheme_code=${BETA}&nav_date=2026-11-18`)).data.status === 'missing');

    // --- 7. later cached valuation + review ------------------------------------------
    current = '7-later-cache-valuation-review';
    updateBook((book) => {
      book[BETA] = { mode: 'rows', rows: { '2026-11-18': '15.3000', '2026-11-23': '16.0000' } };
      book[GAMMA] = { mode: 'rows', rows: { '2026-11-23': '32.0000' } };
    });
    calls = providerCalls().length;
    res = await api(page, 'POST', '/nav/refresh', { scheme_codes: [BETA, GAMMA] });
    check('explicit NAV refresh accepted', res.status === 202, res.data);
    check('refresh is the only provider caller in this phase', providerCalls().length - calls >= 2,
      providerCalls().slice(calls).map((c) => [c.method, c.scheme_code, c.start, c.end]));
    const h = (await api(page, 'GET', '/portfolio/holdings?portfolio_scope=all&display_currency=INR')).data;
    const betaH = h.holdings.find((x) => x.scheme_code === BETA);
    const gammaH = h.holdings.find((x) => x.scheme_code === GAMMA);
    check('later cached NAV values Beta (provider resumes)', betaH && Number(betaH.latest_nav) === 16 &&
      !betaH.nav_provisional && Number(betaH.current_value) === 704, betaH && {
        latest_nav: betaH.latest_nav, quantity: betaH.quantity, current_value: betaH.current_value });
    check('later cached NAV values Gamma remaining units', gammaH && Number(gammaH.latest_nav) === 32 &&
      Number(gammaH.quantity) === 80, gammaH && { latest_nav: gammaH.latest_nav, quantity: gammaH.quantity });
    const s = (await api(page, 'GET', '/portfolio/summary?portfolio_scope=all&display_currency=INR')).data;
    check('summary headline no longer provisional', !s.nav_provisional, { current_value: s.current_value });
    const p = (await api(page, 'GET', '/portfolio/performance?portfolio_scope=all&display_currency=INR&metric=value&range=30D')).data;
    const flaggedDays = s.timeseries.filter((pt) => pt.nav_provisional).map((pt) => pt.date);
    check('history keeps only uncovered provisional days flagged (Gamma 11-19..11-22)',
      JSON.stringify(flaggedDays) === JSON.stringify(['2026-11-19', '2026-11-20', '2026-11-21', '2026-11-22']),
      flaggedDays);
    check('performance range still warns for those days', (p.warnings || []).some((w) => w.includes('provisional')),
      p.warnings || []);
    txns = await allTransactions(page);
    const betaAfter = txns.find((t) => t.id === ids.betaBuy);
    const gammaAfter = txns.find((t) => t.id === ids.gammaSell);
    check('recorded provisional rows untouched by refresh', Number(betaAfter.nav) === 15.25 &&
      Number(betaAfter.units_allotted) === 44 && betaAfter.nav_source === 'PROVISIONAL_USER' &&
      Number(gammaAfter.nav) === 31 && gammaAfter.nav_source === 'PROVISIONAL_USER',
      { beta: [betaAfter.nav, betaAfter.nav_source], gamma: [gammaAfter.nav, gammaAfter.nav_source] });
    check('Beta review state cached_discrepancy with cached NAV', betaAfter.nav_review?.review_class === 'cached_discrepancy' &&
      Number(betaAfter.nav_review?.cached_nav) === 15.3, betaAfter.nav_review);
    check('Gamma review state stays provisional (no exact-date NAV yet)',
      gammaAfter.nav_review?.review_class === 'provisional', gammaAfter.nav_review);
    await gotoPath(page, '/transactions');
    await page.locator('tr').filter({ has: page.getByLabel(`Select transaction ${ids.betaBuy}`) })
      .getByText('Provider NAV now available — review').waitFor();
    check('Transactions list shows "Provider NAV now available — review" (Beta)', true);
    await page.locator('tr').filter({ has: page.getByLabel(`Select transaction ${ids.gammaSell}`) })
      .getByText('Provisional NAV — awaiting provider').waitFor();
    check('Transactions list keeps "Provisional NAV — awaiting provider" (Gamma)', true);
    await shot(page, '07-transactions-review');
    await page.goto(`${FRONTEND}/dashboard`);
    await page.waitForLoadState('networkidle');
    await page.getByLabel('portfolio-view').waitFor();
    check('Dashboard banner cleared after cache arrives (reload, all scope)',
      (await page.getByText(banner).count()) === 0);
    await shot(page, '07a-dashboard-after-cache');

    const preview = execFileSync(path.join(REPO_ROOT, 'backend', '.venv', 'bin', 'python'), [
      path.join(REPO_ROOT, 'scripts', 'acceptance', 'mf_nav_48_server.py'), 'manage', '--run-dir', RUN_DIR,
      '--', 'preview_mf_nav_corrections', '--user-id', String(users.acceptance.id)],
    { encoding: 'utf8', env: { ...process.env, DATABASE_URL: '' } });
    const previewRows = preview.split('\n').filter((l) => l.startsWith('{')).map((l) => JSON.parse(l));
    evidence.preview_summary = preview.split('\n').filter((l) => l && !l.startsWith('{'));
    check('read-only correction preview lists both provisional rows', previewRows.filter((r) =>
      r.nav_source === 'PROVISIONAL_USER').length === 2 && preview.includes('No records changed.'),
      evidence.preview_summary);

    m = await editRow(page, ids.betaBuy);
    await m.getByText('Cached NAV is now available; saving replaces the provisional NAV with the cached NAV.').waitFor();
    check('edit form explains cached NAV replacement', true);
    check('edit form shows cached provider NAV note',
      (await m.getByText(/Cached provider NAV for this date: 15\.3/).count()) === 1);
    const apply = m.getByText(/Apply cached NAV/);
    if (await apply.count()) await apply.locator('input[type=checkbox]').check().catch(async () => {
      await m.locator('label', { hasText: 'Apply cached NAV' }).locator('input').check();
    });
    await shot(page, '07b-review-edit-form');
    await saveModal(page, m);
    txns = await allTransactions(page);
    const betaResaved = txns.find((t) => t.id === ids.betaBuy);
    check('explicit re-save moves row to PROVIDER_CACHE, keeps statement fields', betaResaved &&
      betaResaved.nav_source === 'PROVIDER_CACHE' && Number(betaResaved.nav) === 15.3 &&
      Number(betaResaved.units_allotted) === 44 && Number(betaResaved.paid_value) === 671 &&
      betaResaved.nav_provisional === false, betaResaved && {
        nav: betaResaved.nav, nav_source: betaResaved.nav_source, units: betaResaved.units_allotted,
        paid_value: betaResaved.paid_value, market_value: betaResaved.market_value,
        nav_verification_status: betaResaved.nav_verification_status });
    ledger = (await api(page, 'GET', `/cash/ledger?portfolio_id=${portfolios.inr}&page_size=100`)).data.items;
    const betaCashFinal = ledger.filter((e) => e.linked_transaction_id === ids.betaBuy);
    check('re-save keeps the single linked cash row', betaCashFinal.length === 1 &&
      betaCashFinal[0].id === ids.betaCash[0] && betaCashFinal[0].amount === -671,
      betaCashFinal.map((e) => ({ id: e.id, amount: e.amount })));

    // --- 8. #55 corrective probes (#57–#60 regressions, synthetic only) ---------------
    current = '8-55-corrective-probes';
    const mfPost = (body) => api(page, 'POST', '/transactions', { asset_type: 'MUTUAL_FUND', currency: 'INR', fees: '0', ...body });
    const failedFetch = async (scheme, navDate) => {
      const r = await api(page, 'POST', '/nav/fetch-missing', { scheme_code: scheme, nav_date: navDate });
      return r.data;
    };
    const provisionalBuy = async ({ portfolioId, scheme, folio, navDate, attemptId, nav, units, paid }) =>
      mfPost({
        portfolio_id: portfolioId, scheme_code: scheme, scheme_name: schemes[scheme], folio_number: folio,
        type: 'BUY', investment_date: navDate, nav_date: navDate, units_allotted: String(units),
        paid_value: String(paid), provisional_nav: String(nav), provisional_attempt_id: attemptId,
        confirm_provisional_nav: true, confirm_paid_value: true,
      });

    // P1 (#57): conflicting provisional observations stay unavailable, not zero.
    const conflictDate = '2026-11-26';
    const conflictFetch = await failedFetch(GAMMA, conflictDate);
    check('#57 fetch yields attempt evidence',
      ['timeout', 'date_unavailable'].includes(conflictFetch.outcome) && conflictFetch.attempt_id,
      { outcome: conflictFetch.outcome });
    res = await provisionalBuy({
      portfolioId: portfolios.inr, scheme: GAMMA, folio: 'GF-55-CONFLICT', navDate: conflictDate,
      attemptId: conflictFetch.attempt_id, nav: '31', units: 10, paid: 310,
    });
    check('#57 first provisional BUY saved', res.status === 201, res.data);
    res = await provisionalBuy({
      portfolioId: portfolios.inr, scheme: GAMMA, folio: 'GF-55-CONFLICT', navDate: conflictDate,
      attemptId: conflictFetch.attempt_id, nav: '32', units: 10, paid: 320,
    });
    check('#57 conflicting provisional BUY saved', res.status === 201, res.data);
    const conflictHold = (await api(page, 'GET',
      `/portfolio/holdings?portfolio_id=${portfolios.inr}&display_currency=INR`)).data.holdings
      .find((h) => h.scheme_code === GAMMA && h.folio_number === 'GF-55-CONFLICT');
    const conflictSum = (await api(page, 'GET',
      `/portfolio/summary?portfolio_id=${portfolios.inr}&display_currency=INR`)).data;
    check('#57 conflicted holding current_value is null not zero',
      conflictHold && conflictHold.current_value === null && conflictHold.current_value !== 0,
      conflictHold && { current_value: conflictHold.current_value, nav_status: conflictHold.nav_status });
    check('#57 summary does not treat unknown MF as zero loss',
      conflictSum.total_pl === null || conflictSum.unrealized_pl === null,
      { total_pl: conflictSum.total_pl, incomplete: conflictSum.incomplete });

    // P2 (#58): valuation-date FX, not observation-date FX, on EUR-base portfolio.
    execFileSync(path.join(REPO_ROOT, 'backend', '.venv', 'bin', 'python'), [
      path.join(REPO_ROOT, 'scripts', 'acceptance', 'mf_nav_48_server.py'), 'manage',
      '--run-dir', RUN_DIR, '--', 'shell', '-c',
      `from datetime import date, timedelta
from decimal import Decimal
from fx.services import upsert_fx_rate
from portfolios import dates as portfolio_dates
end = portfolio_dates.current_date()
day = date(2020, 1, 1)
while day <= end:
    rate = Decimal('0.010') if day < date(2026, 11, 15) else Decimal('0.012')
    upsert_fx_rate(from_currency='INR', to_currency='EUR', row_date=day, rate=rate, source='acceptance')
    upsert_fx_rate(from_currency='EUR', to_currency='INR', row_date=day,
                   rate=(Decimal('1') / rate).quantize(Decimal('0.0001')), source='acceptance')
    day += timedelta(days=1)`,
    ], { encoding: 'utf8', env: { ...process.env, DATABASE_URL: '' } });
    check('#58 EUR/INR FX seeded for valuation-date probe', true);
    res = await api(page, 'POST', '/transactions', {
      asset_symbol: 'ACC_STK', date: '2026-11-05', type: 'BUY', quantity: '10', price_per_share: '110',
      currency: 'EUR', fees: '0', portfolio_id: portfolios.eur,
    });
    check('#58 EUR stock leg seeded', res.status === 201, res.status);
    const fxNavDate = '2026-11-05';
    const fxFetch = await failedFetch(BETA, fxNavDate);
    res = await provisionalBuy({
      portfolioId: portfolios.eur, scheme: BETA, folio: 'BF-55-FX', navDate: fxNavDate,
      attemptId: fxFetch.attempt_id, nav: '42.5', units: 100, paid: 4250,
    });
    check('#58 provisional EUR-base MF saved', res.status === 201, res.data);
    const fxSum = (await api(page, 'GET',
      `/portfolio/summary?portfolio_id=${portfolios.eur}&display_currency=EUR`)).data;
    const fxHist = (fxSum.timeseries || []).find((pt) => pt.date === '2026-11-05');
    check('#58 EUR-base summary readable after provisional MF (smoke)',
      fxSum.fx_status === 'ok' && fxSum.current_value != null,
      { current_value: fxSum.current_value, nav_provisional: fxSum.nav_provisional });
    check('#58 same-date history at observation uses observation FX (EUR 1142.50)',
      fxHist && Number(fxHist.portfolio_value) === 1142.5, fxHist);
    const fxOracle = execFileSync(path.join(REPO_ROOT, 'backend', '.venv', 'bin', 'python'), [
      '-m', 'pytest',
      'tests/test_mf_provisional_valuation_scopes_api.py::test_carried_provisional_nav_uses_valuation_date_fx_not_observation_fx',
      '-q', '--tb=no'],
      { cwd: path.join(REPO_ROOT, 'backend'), encoding: 'utf8',
        env: { ...process.env, DATABASE_URL: '', DJANGO_TEST_USE_SQLITE: '1' } });
    check('#58 valuation-date FX oracle (pytest disposable SQLite)', /passed/.test(fxOracle),
      fxOracle.trim().split('\n').slice(-3));

    // P3 (#59): personal Holding XIRR matches across holdings, detail, and metrics (BF-1).
    const holdX = (await api(page, 'GET',
      `/portfolio/holdings?portfolio_id=${portfolios.inr}&display_currency=INR`)).data.holdings
      .find((h) => h.scheme_code === BETA && h.folio_number === 'BF-1');
    const detailX = (await api(page, 'GET',
      `/portfolio/assets/${BETA}?portfolio_id=${portfolios.inr}&folio_number=BF-1&display_currency=INR`)).data;
    const metricsX = (await api(page, 'GET',
      `/analytics/assets/${BETA}/performance-metrics?portfolio_id=${portfolios.inr}&folio_number=BF-1&display_currency=INR&range=ALL`)).data.personal_metrics;
    const xirrValues = [holdX?.xirr, detailX?.xirr, metricsX?.xirr];
    check('#59 personal XIRR parity across holdings/detail/metrics',
      xirrValues.every((v) => v != null) && Math.max(...xirrValues) - Math.min(...xirrValues) < 1e-6,
      { holdings: holdX?.xirr, detail: detailX?.xirr, metrics: metricsX?.xirr, status: metricsX?.status });
    check('#59 personal metrics calculated with native INR basis',
      metricsX?.status === 'calculated' && metricsX?.basis === 'native_inr',
      { metrics_basis: metricsX?.basis, nav_provisional: metricsX?.nav_provisional });

    // P4 (#60): stale successful fetch cannot overwrite replacement cache (pytest oracle).
    const staleOut = execFileSync(path.join(REPO_ROOT, 'backend', '.venv', 'bin', 'python'), [
      '-m', 'pytest', 'tests/test_mf_nav_fetch_stale_finalization.py', '-q', '--tb=no'],
      { cwd: path.join(REPO_ROOT, 'backend'), encoding: 'utf8',
        env: { ...process.env, DATABASE_URL: '', DJANGO_TEST_USE_SQLITE: '1' } });
    const stalePass = /passed/.test(staleOut) && !/failed/.test(staleOut);
    check('#60 stale-fetch fence suite green (disposable SQLite, not acceptance DB)', stalePass,
      staleOut.trim().split('\n').slice(-3));
    evidence.corrective_probes = { conflictDate, fx_expected_headline: 1151, fx_expected_history: 1142.5 };

    // --- 9. auth / CSRF / cross-user isolation ----------------------------------------
    current = '9-auth-csrf-isolation';
    res = await api(page, 'POST', '/nav/fetch-missing', { scheme_code: BETA, nav_date: '2026-11-20' }, { csrf: false });
    check('fetch-missing without CSRF token rejected', res.status === 403, res.status);
    calls = providerCalls().length;
    const own = await api(page, 'POST', '/nav/fetch-missing', { scheme_code: BETA, nav_date: '2026-11-20' });
    check('owner unsuccessful fetch returns attempt id', own.data.outcome === 'date_unavailable' && own.data.attempt_id,
      { outcome: own.data.outcome });
    const anon = await browser.newContext();
    const anonPage = await anon.newPage();
    await anonPage.goto(`${FRONTEND}/login`);
    res = await api(anonPage, 'GET', `/nav/lookup?scheme_code=${ALPHA}&nav_date=2026-11-17`);
    check('anonymous lookup rejected', res.status === 403 || res.status === 401, res.status);
    res = await api(anonPage, 'POST', '/nav/fetch-missing', { scheme_code: ALPHA, nav_date: '2026-11-18' });
    check('anonymous fetch-missing rejected', res.status === 403 || res.status === 401, res.status);
    await anon.close();
    const otherCtx = await browser.newContext();
    const other = await otherCtx.newPage();
    await login(other, users.other.username);
    const otherTxns = (await api(other, 'GET', '/transactions?portfolio_scope=all&page_size=100')).data;
    check('other user sees none of the acceptance transactions', otherTxns.total === 0, otherTxns.total);
    res = await api(other, 'PUT', `/transactions/${ids.betaBuy}`, { asset_type: 'MUTUAL_FUND',
      scheme_code: BETA, scheme_name: schemes[BETA], folio_number: 'BF-1', type: 'BUY',
      investment_date: '2026-11-18', nav_date: '2026-11-18', units_allotted: '1', paid_value: '1',
      market_value: '1', fees: '0', currency: 'INR' });
    check("other user cannot edit acceptance user's transaction", res.status === 404, res.status);
    const otherCooldown = await api(other, 'POST', '/nav/fetch-missing', { scheme_code: BETA, nav_date: '2026-11-20' });
    check('other user sees cooldown without the owner attempt id', otherCooldown.data.outcome === 'cooldown' &&
      !otherCooldown.data.attempt_id, otherCooldown.data);
    res = await api(other, 'POST', '/transactions', { asset_type: 'MUTUAL_FUND', scheme_code: BETA,
      scheme_name: schemes[BETA], folio_number: 'OF-1', type: 'BUY', investment_date: '2026-11-20',
      nav_date: '2026-11-20', units_allotted: '10', paid_value: '160', fees: '0', currency: 'INR',
      portfolio_id: portfolios.other, provisional_nav: '16', provisional_attempt_id: own.data.attempt_id,
      confirm_provisional_nav: true, confirm_paid_value: true });
    check("other user cannot use owner's attempt id", res.status === 400, { status: res.status, body: res.data });
    check('isolation checks made one provider call (owner attempt only)', providerCalls().length - calls === 1);
    await otherCtx.close();

    current = 'console';
    evidence.http_errors = httpErrors;
    const unexpected = httpErrors.filter((e) => e.scenario !== '9-auth-csrf-isolation' &&
      e.scenario !== '8-55-corrective-probes' &&
      !(e.scenario === 'served-checkout' && e.status === 403 && e.url.startsWith('/api/v1/auth/me')));
    check('no HTTP errors outside pre-login probe and deliberate 4xx checks', unexpected.length === 0, unexpected);
    check('every browser console error maps to a logged HTTP error',
      consoleErrors.length === httpErrors.length, { console: consoleErrors.length, http: httpErrors.length });
  } catch (err) {
    check('unexpected error', false, String(err && err.stack || err));
    await shot(page, `zz-failure-${current}`).catch(() => {});
  } finally {
    evidence.finished_at = new Date().toISOString();
    evidence.provider_calls = providerCalls().map((c) => [c.method, c.scheme_code, c.start ?? null, c.end ?? null]);
    evidence.blocked_network = blockedNetwork();
    evidence.results = results;
    evidence.passed = results.filter((r) => r.ok).length;
    evidence.failed = results.filter((r) => !r.ok).length;
    fs.writeFileSync(path.join(RUN_DIR, 'acceptance-results.json'), JSON.stringify(evidence, null, 2));
    console.log(`\n${evidence.passed} passed, ${evidence.failed} failed`);
    await browser.close();
    process.exitCode = evidence.failed ? 1 : 0;
  }
}

main();
