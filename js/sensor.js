(() => {
    'use strict';

    const canvas = document.querySelector('[data-sensor-pattern]');
    if (!canvas) return;
    const context = canvas.getContext('2d');
    if (!context) return;

    const field = canvas.parentElement;
    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
    const systemTheme = matchMedia('(prefers-color-scheme: dark)');
    const width = 624;
    const height = 272;
    // Tiles follow the supplied reference, with R=+, G=x and B=.
    const bayer = ['GB', 'RG'];
    const xtrans = ['GBRGRB', 'RGGBGG', 'BGGRGG', 'GRBGBR', 'BGGRGG', 'RGGBGG'];
    const filters = {
        R: { glyph: '+', alpha: .62, index: 0 },
        G: { glyph: 'x', alpha: .46, index: 1 },
        B: { glyph: '.', alpha: .62, index: 2 },
    };
    const glyphs = document.createElement('canvas');
    const glyphContext = glyphs.getContext('2d');
    if (!glyphContext) return;
    const frameDelay = 1000 / 30;
    const pulsePeriod = 4.8;
    const pulseLength = 1.2;
    const ease = value => value * value * (3 - 2 * value);
    const cells = [];
    const noise = value => {
        let bits = value | 0;
        bits = Math.imul(bits ^ (bits >>> 16), 0x21f0aaad);
        bits = Math.imul(bits ^ (bits >>> 15), 0x735a2d97);
        return ((bits ^ (bits >>> 15)) >>> 0) / 4294967296;
    };
    for (let row = 0; row < 30; row++) {
        for (let column = 0; column < 72; column++) {
            const id = row * 72 + column + 1;
            cells.push({
                id,
                x: 28 + column * 8,
                y: 20 + row * 8,
                filters: [bayer[row % 2][column % 2], xtrans[row % 6][column % 6]],
                patch: Math.floor(row / 3) * 24 + Math.floor(column / 3),
                offset: noise(id) * pulsePeriod,
                switchAt: 0,
                fadeLength: 0,
            });
        }
    }
    let timer = null;
    let visible = true;
    let elapsed = 0;
    let lastTick = null;
    let glyphSize = 12;
    let pattern = 0;
    let transitioning = false;
    let phaseTime = 0;
    let phaseDuration = 5 + Math.random() * 3;

    const cacheGlyphs = () => {
        // Cache three glyphs so the animation does not repeatedly render text.
        glyphSize = Math.max(12, Math.ceil(12 * canvas.width / width));
        glyphs.width = glyphSize * 3;
        glyphs.height = glyphSize;
        glyphContext.setTransform(glyphSize / 12, 0, 0, glyphSize / 12, 0, 0);
        glyphContext.fillStyle = getComputedStyle(canvas).color;
        glyphContext.font = '9px "IBM Plex Mono", "Courier New", monospace';
        glyphContext.textAlign = 'center';
        glyphContext.textBaseline = 'middle';
        for (const filter of Object.values(filters)) {
            glyphContext.fillText(filter.glyph, filter.index * 12 + 6, 6);
        }
    };

    const draw = () => {
        context.clearRect(0, 0, width, height);
        const still = reducedMotion.matches;
        const mark = (filter, x, y, alpha) => {
            context.globalAlpha = alpha;
            context.drawImage(glyphs, filter.index * glyphSize, 0, glyphSize, glyphSize, x - 6, y - 6, 12, 12);
        };
        for (const cell of cells) {
            const switched = !still && transitioning && phaseTime >= cell.switchAt;
            const current = still ? 0 : (switched ? 1 - pattern : pattern);
            const filter = filters[cell.filters[current]];
            let brightness = 1;
            if (!still) {
                // Smooth dimming pulses are staggered across the field.
                const time = elapsed + cell.offset;
                const pulse = time % pulsePeriod;
                const epoch = Math.floor(time / pulsePeriod);
                if (pulse < pulseLength && noise(cell.id ^ Math.imul(epoch + 1, 2654435761)) < .11) {
                    brightness = 1 - .75 * Math.sin(Math.PI * pulse / pulseLength) ** 2;
                }
                // Fade out, change the glyph at zero opacity, then fade back in.
                const distance = Math.abs(phaseTime - cell.switchAt);
                if (transitioning && cell.filters[0] !== cell.filters[1] && distance < cell.fadeLength) {
                    brightness *= ease(distance / cell.fadeLength);
                }
            }
            mark(filter, cell.x, cell.y, filter.alpha * brightness);
        }
        for (const [x, y] of [[4, 6], [width - 4, 6], [4, height - 6], [width - 4, height - 6]]) {
            mark(filters.R, x, y, .3);
        }
        context.globalAlpha = 1;
        field.classList.add('is-ready');
    };

    const resize = () => {
        const bounds = field.getBoundingClientRect();
        const scale = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = Math.max(1, Math.round(bounds.width * scale));
        canvas.height = Math.max(1, Math.round(bounds.height * scale));
        context.setTransform(canvas.width / width, 0, 0, canvas.height / height, 0, 0);
        cacheGlyphs();
        draw();
    };

    const advance = delta => {
        elapsed += delta;
        phaseTime += delta;
        while (phaseTime >= phaseDuration) {
            phaseTime -= phaseDuration;
            if (transitioning) {
                pattern = 1 - pattern;
                transitioning = false;
                phaseDuration = 5 + Math.random() * 4;
            } else {
                transitioning = true;
                phaseDuration = 12 + Math.random() * 6;
                const seed = Math.floor(Math.random() * 2147483647);
                for (const cell of cells) {
                    const patch = noise(Math.imul(cell.patch + 1, 97) ^ seed);
                    const individual = noise(cell.id ^ seed);
                    cell.switchAt = 1.2 + (phaseDuration - 2.4) * (.6 * patch + .4 * individual);
                    cell.fadeLength = .6 + noise(cell.id + seed) * .4;
                }
            }
        }
    };
    const tick = () => {
        const now = performance.now();
        if (lastTick !== null) advance((now - lastTick) / 1000);
        lastTick = now;
        draw();
        timer = setTimeout(tick, frameDelay);
    };
    const updateMotion = () => {
        clearTimeout(timer);
        timer = null;
        lastTick = null;
        draw();
        if (!reducedMotion.matches && visible && !document.hidden) {
            lastTick = performance.now();
            timer = setTimeout(tick, frameDelay);
        }
    };

    const refresh = () => {
        cacheGlyphs();
        draw();
    };
    reducedMotion.addEventListener('change', updateMotion);
    systemTheme.addEventListener('change', refresh);
    document.addEventListener('visibilitychange', updateMotion);
    new MutationObserver(refresh).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    if (typeof ResizeObserver === 'function') new ResizeObserver(resize).observe(field);
    else window.addEventListener('resize', resize);
    if (typeof IntersectionObserver === 'function') {
        new IntersectionObserver(entries => {
            visible = entries[0].isIntersecting;
            updateMotion();
        }).observe(field);
    }
    document.fonts?.ready.then(refresh);
    resize();
    updateMotion();
})();
