/* Event tests use real markup and page scripts with a minimal DOM fixture.
 * They do not cover browser layout or native form validation.
 * Run with Node.js and Python 3; no packages are required.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { execFileSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');
let assertions = 0;

function equal(actual, expected) {
  assert.deepEqual(actual, expected);
  assertions += 1;
}

class Element {
  constructor(data, parent = null) {
    this.tagName = data.tag.toUpperCase();
    this.attrs = { ...data.attrs };
    this.parent = parent;
    this.events = {};
    this.children = data.children.map(child => (
      typeof child === 'string' ? child : new Element(child, this)
    ));
    this.hidden = 'hidden' in this.attrs;
    this.disabled = false;
    this._value = this.attrs.value || '';
    this._validity = '';
    this._text = undefined;
    this.dataset = Object.fromEntries(
      Object.entries(this.attrs)
        .filter(([name]) => name.startsWith('data-'))
        .map(([name, value]) => [
          name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase()),
          value,
        ])
    );
    this.classList = {
      add: name => this.setClasses(this.classes().add(name)),
      remove: name => {
        const classes = this.classes();
        classes.delete(name);
        this.setClasses(classes);
      },
      contains: name => this.classes().has(name),
      toggle: (name, state) => {
        const classes = this.classes();
        const enabled = state === undefined ? !classes.has(name) : state;
        if (enabled) classes.add(name);
        else classes.delete(name);
        this.setClasses(classes);
        return enabled;
      },
    };
  }

  classes() {
    return new Set((this.attrs.class || '').split(/\s+/).filter(Boolean));
  }

  setClasses(classes) {
    this.attrs.class = [...classes].join(' ');
  }

  get id() {
    return this.attrs.id || '';
  }

  get textContent() {
    if (this._text !== undefined) return this._text;
    return this.children.map(child => (
      typeof child === 'string' ? child : child.textContent
    )).join('');
  }

  set textContent(value) {
    this._text = String(value);
  }

  get options() {
    return this.querySelectorAll('option');
  }

  get value() {
    if (this.tagName === 'SELECT') {
      return this._value || this.options[0]?.value || '';
    }
    if (this.tagName === 'OPTION') {
      return this.attrs.value !== undefined ? this.attrs.value : this.textContent;
    }
    return this._value;
  }

  set value(value) {
    this._value = String(value);
  }

  getAttribute(name) {
    return this.attrs[name] ?? null;
  }

  setAttribute(name, value) {
    this.attrs[name] = String(value);
  }

  removeAttribute(name) {
    delete this.attrs[name];
  }

  matches(selector) {
    if (selector[0] === '#') return this.id === selector.slice(1);
    if (selector[0] === '.') return this.classes().has(selector.slice(1));
    if (selector[0] === '[') return selector.slice(1, -1) in this.attrs;
    return this.tagName.toLowerCase() === selector;
  }

  querySelectorAll(selector) {
    return this.children
      .filter(child => typeof child !== 'string')
      .flatMap(child => [
        ...(child.matches(selector) ? [child] : []),
        ...child.querySelectorAll(selector),
      ]);
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }

  closest(selector) {
    return this.matches(selector) ? this : this.parent?.closest(selector) || null;
  }

  addEventListener(type, handler) {
    (this.events[type] ??= []).push(handler);
  }

  async dispatch(type, properties = {}) {
    const event = {
      target: this,
      preventDefault() { this.defaultPrevented = true; },
      ...properties,
    };
    for (const handler of this.events[type] || []) {
      await handler.call(this, event);
    }
    return event;
  }

  owner() {
    return this.parent ? this.parent.owner() : this;
  }

  focus() {
    this.owner().activeElement = this;
  }

  scrollIntoView() {
    this.scrolled = true;
  }

  select() {
    this.selected = true;
  }

  setCustomValidity(message) {
    this._validity = message;
  }

  reportValidity() {
    return Object.values(this.elements || {}).every(field => (
      !field._validity && (!('required' in field.attrs) || field.value.trim())
    ));
  }

  reset() {
    for (const field of Object.values(this.elements)) field.value = '';
  }
}

function setup(page, options = {}) {
  const pagePath = path.join(root, 'docs', page);
  const fixture = JSON.parse(execFileSync(
    process.env.PYTHON || 'python3',
    [path.join(__dirname, 'dom_fixture.py'), pagePath],
    { encoding: 'utf8', maxBuffer: 4 * 1024 * 1024 }
  ));
  const document = new Element(fixture);
  document.documentElement = document.querySelector('html');
  document.body = document.querySelector('body');
  const form = document.querySelector('#contact-form');
  if (form) {
    form.elements = Object.fromEntries(
      ['input', 'select', 'textarea']
        .flatMap(selector => form.querySelectorAll(selector))
        .filter(field => field.attrs.name)
        .map(field => [field.attrs.name, field])
    );
  }
  const events = {};
  const media = {
    matches: !!options.mobile,
    addEventListener(type, handler) { this.listener = handler; },
  };
  const context = {
    document,
    URL, URLSearchParams, Date, Map, Set, AbortController,
    setTimeout, clearTimeout, console,
    location: new URL(options.url || `https://example.test/${page}`),
    navigator: {},
    window: {
      AB_CONFIG: options.config || {},
      isSecureContext: false,
      matchMedia: () => media,
      addEventListener: (type, handler) => (events[type] ??= []).push(handler),
    },
    fetch: options.fetch || (() => { throw Error('Unexpected network request'); }),
  };
  context.history = {
    replaceState(state, title, url) { context.location = new URL(url); },
  };
  vm.createContext(context);
  for (const tag of document.querySelectorAll('script')) {
    const source = tag.getAttribute('src');
    if (!source || source === 'site-config.js') continue;
    const filename = path.join(root, 'docs', source);
    vm.runInContext(fs.readFileSync(filename, 'utf8'), context, { filename });
  }
  return {
    document, form, context, media, events,
    get: selector => document.querySelector(selector),
    all: selector => document.querySelectorAll(selector),
  };
}

function fillEnquiry(page) {
  page.form.elements.name.value = 'Test User';
  page.form.elements.email.value = 'qa@example.com';
  page.form.elements.message.value = 'I would like material compatibility information.';
}

function visibleProducts(page) {
  return page.all('[data-product]').filter(product => !product.hidden);
}

async function testNavigation() {
  for (const filename of ['index.html', 'products.html', 'solutions.html', 'contact.html']) {
    const page = setup(filename);
    equal(page.document.documentElement.classList.contains('js-enabled'), true);
  }
  const page = setup('index.html', { mobile: true });
  await page.get('.menu-toggle').dispatch('click');
  equal(page.get('.main-nav').classList.contains('is-open'), true);
  equal(page.get('.menu-toggle').getAttribute('aria-expanded'), 'true');
  await page.document.dispatch('keydown', { key: 'Escape' });
  equal(page.get('.menu-toggle').getAttribute('aria-expanded'), 'false');
  equal(page.document.activeElement, page.get('.menu-toggle'));
  await page.get('.menu-toggle').dispatch('click');
  page.media.matches = false;
  page.media.listener();
  equal(page.document.body.classList.contains('menu-open'), false);
}

async function testProductFilters() {
  let page = setup('products.html');
  equal(visibleProducts(page).length, 12);
  for (const [category, count] of [['materials', 2], ['cleaning', 5], ['applications', 5]]) {
    await page.all('[data-filter]')
      .find(button => button.dataset.filter === category).dispatch('click');
    equal(visibleProducts(page).length, count);
  }
  await page.all('[data-filter]')
    .find(button => button.dataset.filter === 'all').dispatch('click');
  page.get('#product-search').value = 'water purification';
  await page.get('#product-search').dispatch('input');
  equal(page.get('#water-equipment').hidden, false);
  equal(page.get('#result-count').textContent, 'Showing 1 product');
  page.get('#product-search').value = 'zzznothingfound';
  await page.get('#product-search').dispatch('input');
  equal(page.get('#empty-state').hidden, false);
  await page.get('#reset-filters').dispatch('click');
  equal(page.get('#empty-state').hidden, true);
  equal(visibleProducts(page).length, 12);
  page.get('#product-search').value = 'silver';
  await page.get('#product-search').dispatch('input');
  await page.get('#clear-search').dispatch('click');
  equal(page.get('#product-search').value, '');
  equal(page.get('#clear-search').hidden, true);
  page = setup('products.html', {
    url: 'https://example.test/products.html?category=cleaning#masterbatch',
  });
  equal(page.get('#masterbatch').hidden, false);
  equal(page.get('#masterbatch').scrolled, true);
  page = setup('products.html', {
    url: 'https://example.test/products.html?category=INVALID&q=zzznothingfound',
  });
  equal(page.get('#empty-state').hidden, false);
}

async function testEmailDraft() {
  const page = setup('contact.html', {
    url: 'https://example.test/contact.html?product=Antibacterial+Masterbatch&interest=Custom+formulation',
  });
  equal(page.form.elements.product.value, 'Antibacterial Masterbatch');
  equal(page.form.elements.interest.value, 'Custom formulation');
  fillEnquiry(page);
  page.form.elements.name.value = 'QA & 测试';
  await page.form.dispatch('submit');
  equal(page.get('#email-fallback').hidden, false);
  equal(page.get('#form-status').textContent.includes('Nothing has been sent yet.'), true);
  equal(decodeURIComponent(page.get('#email-draft-link').href).includes('QA & 测试'), true);
  equal(page.form.elements.message.value.length > 0, true);
  page.form.elements.message.value = 'Updated message preserved in draft';
  await page.form.dispatch('input');
  equal(page.get('#enquiry-copy').value.includes('Updated message'), true);
  await page.get('#copy-enquiry').dispatch('click');
  equal(page.get('#enquiry-copy').hidden, false);
  equal(page.get('#enquiry-copy').selected, true);
}

async function testContactApi() {
  let page = setup('contact.html', {
    config: { contactEndpoint: '/api/contact' },
    fetch: async () => ({ ok: true, status: 200, json: async () => ({ success: true }) }),
  });
  fillEnquiry(page);
  await page.form.dispatch('submit');
  equal(page.get('#form-status').dataset.state, 'success');
  equal(page.form.elements.message.value, '');
  equal(page.get('#submit-enquiry').disabled, false);
  const failures = [
    { ok: false, status: 502, json: async () => ({ success: false }) },
    { ok: true, status: 200, json: async () => ({ success: false }) },
    { ok: false, status: 429, json: async () => ({}) },
    { ok: false, status: 500, json: async () => { throw Error('Invalid JSON'); } },
  ];
  for (const response of failures) {
    page = setup('contact.html', {
      config: { contactEndpoint: '/api/contact' },
      fetch: async () => response,
    });
    fillEnquiry(page);
    await page.form.dispatch('submit');
    equal(page.get('#form-status').dataset.state, 'error');
    equal(page.form.elements.message.value.length > 0, true);
    equal(page.get('#submit-enquiry').disabled, false);
    equal(page.get('#email-fallback').hidden, false);
  }
}

async function testDuplicateSubmit() {
  let resolveRequest;
  let calls = 0;
  const page = setup('contact.html', {
    config: { contactEndpoint: '/api/contact' },
    fetch: () => {
      calls += 1;
      return new Promise(resolve => { resolveRequest = resolve; });
    },
  });
  fillEnquiry(page);
  const pending = page.form.dispatch('submit');
  await page.form.dispatch('submit');
  equal(calls, 1);
  resolveRequest({ ok: true, status: 200, json: async () => ({ success: true }) });
  await pending;
}

async function testTimeoutAndValidation() {
  let page = setup('contact.html', {
    config: { contactEndpoint: '/api/contact', requestTimeoutMs: 5 },
    fetch: (url, options) => new Promise((resolve, reject) => {
      options.signal.addEventListener('abort', () => {
        const error = Error('Timeout');
        error.name = 'AbortError';
        reject(error);
      });
    }),
  });
  fillEnquiry(page);
  await page.form.dispatch('submit');
  equal(page.get('#form-status').textContent.includes('timed out'), true);
  equal(page.get('#submit-enquiry').disabled, false);
  equal(page.form.elements.message.value.length > 0, true);
  page = setup('contact.html');
  fillEnquiry(page);
  page.form.elements.message.value = '          ';
  await page.form.dispatch('submit');
  equal(page.get('#email-fallback').hidden, true);
  equal(page.form.elements.message._validity.length > 0, true);
}

async function main() {
  await testNavigation();
  await testProductFilters();
  await testEmailDraft();
  await testContactApi();
  await testDuplicateSubmit();
  await testTimeoutAndValidation();
  console.log(JSON.stringify({
    status: 'PASS',
    assertions,
    scope: 'JavaScript event/state regression; no browser rendering',
  }, null, 2));
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
