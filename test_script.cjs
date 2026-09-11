// Exercise image loading races and fallback behavior without network requests.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');
const script = readFileSync('js/script.js', 'utf8');

function viewer() {
    class Element {
        constructor() {
            this.events = {};
            this.style = {};
            this.dataset = {};
            this.classList = { contains: () => false };
            this.children = [];
        }
        addEventListener(name, callback) { this.events[name] = callback; }
        fire(name, overrides = {}) {
            const event = { button: 0, target: this, prevented: false, preventDefault() { this.prevented = true; }, ...overrides };
            this.events[name]?.(event);
            return event;
        }
        append(element) { this.children.push(element); }
        focus() { document.activeElement = this; }
        removeAttribute(name) { delete this[name]; }
        showModal() { this.open = true; }
        close() { this.open = false; this.fire('close'); }
    }
    const ids = Object.fromEntries(['lightbox', 'lb-img', 'lb-status', 'lb-prev', 'lb-next', 'lb-close', 'lb-title', 'lb-filename', 'lb-metadata', 'lb-counter', 'gallery'].map(id => [id, new Element()]));
    const links = [0, 1].map(i => {
        const link = new Element();
        link.href = `/photos/test/full/image-${i}.webp`;
        link.dataset = { title: `Photo ${i}`, filename: `image-${i}.webp`, metadata: `metadata ${i}` };
        link.closest = () => null;
        return link;
    });
    ids.gallery.querySelectorAll = () => links;
    const document = {
        body: new Element(),
        querySelectorAll: selector => selector === '[data-photo]' ? links : [],
        querySelector: () => null,
        getElementById: id => ids[id],
        createElement: () => new Element(),
    };
    const loads = [];
    const decodes = [];
    ids['lb-img'].decode = () => new Promise((resolve, reject) => decodes.push({ resolve, reject }));
    class Image { constructor() { loads.push(this); } }
    vm.runInNewContext(script, { document, Image });
    return { ids, links, loads, decodes, document };
}

test('shared script is safe on a page without any gallery', () => {
    assert.doesNotThrow(() => vm.runInNewContext(script, {
        document: { querySelectorAll: () => [], querySelector: () => null, getElementById: () => null }
    }));
});

test('modified clicks preserve direct image navigation', () => {
    const { ids, links } = viewer();
    const event = links[0].fire('click', { ctrlKey: true });
    assert.equal(event.prevented, false);
    assert.equal(ids.lightbox.open, undefined);
});

test('only the latest requested image may replace the viewer contents', async () => {
    const { ids, links, loads, decodes } = viewer();
    links[0].fire('click');
    assert.match(ids['lb-status'].textContent, /Loading/);
    assert.equal(ids['lb-img'].hidden, true);
    ids['lb-next'].fire('click');
    const ready = loads[1].onload();
    decodes[0].resolve();
    await ready;
    loads[0].onload();
    assert.equal(ids['lb-img'].src, links[1].href);
    assert.equal(ids['lb-counter'].textContent, '002 / 002');
    assert.equal(ids['lb-status'].textContent, '');
});

test('failed images offer a direct link and next-image navigation recovers', async () => {
    const { ids, links, loads, decodes } = viewer();
    links[0].fire('click');
    loads[0].onerror();
    assert.match(ids['lb-status'].textContent, /could not be loaded/);
    assert.equal(ids['lb-status'].children[0].href, links[0].href);
    assert.equal(ids['lb-img'].hidden, true);
    ids['lb-next'].fire('click');
    const ready = loads[1].onload();
    decodes[0].resolve();
    await ready;
    assert.equal(ids['lb-status'].textContent, '');
    assert.equal(ids['lb-img'].hidden, false);
});

test('closing restores focus and scroll state and ignores pending image loads', () => {
    const { ids, links, loads, document } = viewer();
    document.body.style.overflow = 'auto';
    links[0].fire('click');
    ids['lb-close'].fire('click');
    loads[0].onload();
    assert.equal(document.body.style.overflow, 'auto');
    assert.equal(document.activeElement, links[0]);
    assert.equal(ids['lb-img'].src, undefined);
});

test('loading stays visible until the displayed photo finishes decoding', async () => {
    const { ids, links, loads, decodes } = viewer();
    links[0].fire('click');
    const ready = loads[0].onload();
    assert.match(ids['lb-status'].textContent, /Loading/);
    assert.equal(ids['lb-img'].hidden, true);
    decodes[0].resolve();
    await ready;
    assert.equal(ids['lb-status'].textContent, '');
    assert.equal(ids['lb-img'].hidden, false);
});

test('an old decode cannot clear the next photograph loading state', async () => {
    const { ids, links, loads, decodes } = viewer();
    links[0].fire('click');
    const oldReady = loads[0].onload();
    ids['lb-next'].fire('click');
    decodes[0].resolve();
    await oldReady;
    assert.match(ids['lb-status'].textContent, /Loading/);
    assert.equal(ids['lb-img'].hidden, true);
});

test('decode failure shows an error rather than an empty viewer', async () => {
    const { ids, links, loads, decodes } = viewer();
    links[0].fire('click');
    const ready = loads[0].onload();
    decodes[0].reject(new Error('Decode failed'));
    await ready;
    assert.match(ids['lb-status'].textContent, /could not be loaded/);
    assert.equal(ids['lb-img'].hidden, true);
});

test('closing during decode cannot reveal the image after closing', async () => {
    const { ids, links, loads, decodes } = viewer();
    links[0].fire('click');
    const ready = loads[0].onload();
    ids['lb-close'].fire('click');
    decodes[0].resolve();
    await ready;
    assert.equal(ids['lb-status'].textContent, '');
    assert.equal(ids['lb-img'].hidden, true);
    assert.equal(ids['lb-img'].src, undefined);
});
