(() => {
    'use strict';

    const themeToggle = document.querySelector('[data-theme-toggle]');
    const root = document.documentElement;
    if (themeToggle && root) {
        const systemTheme = typeof matchMedia === 'function' ? matchMedia('(prefers-color-scheme: dark)') : null;
        let savedTheme = null;
        try {
            const saved = localStorage.getItem('theme');
            savedTheme = saved === 'light' || saved === 'dark' ? saved : null;
        } catch {}

        const currentTheme = () => root.dataset.theme || (systemTheme?.matches ? 'dark' : 'light');
        const updateToggle = () => {
            const dark = currentTheme() === 'dark';
            const label = `Switch to ${dark ? 'light' : 'dark'} mode`;
            themeToggle.setAttribute('aria-label', label);
            themeToggle.setAttribute('title', label);
            themeToggle.setAttribute('aria-pressed', String(dark));
        };

        themeToggle.addEventListener('click', () => {
            savedTheme = currentTheme() === 'dark' ? 'light' : 'dark';
            root.dataset.theme = savedTheme;
            try { localStorage.setItem('theme', savedTheme); } catch {}
            updateToggle();
        });
        systemTheme?.addEventListener('change', event => {
            if (savedTheme) return;
            root.dataset.theme = event.matches ? 'dark' : 'light';
            updateToggle();
        });
        updateToggle();
    }

    // The index is progressively enhanced: every project remains a normal link.
    const projects = [...document.querySelectorAll('[data-project]')];
    const previewImage = document.querySelector('.preview-photo');
    const previewLink = document.getElementById('preview-link');
    if (projects.length && previewImage && previewLink) {
        const desktop = window.matchMedia('(min-width: 900px)');
        let selected = projects[0];
        const selectProject = row => {
            if (!desktop.matches) return;
            selected = row;
            projects.forEach(project => project.classList.toggle('is-active', project === row));
            const source = row.querySelector('img');
            previewImage.srcset = source.srcset;
            previewImage.src = source.src;
            previewImage.width = source.width;
            previewImage.height = source.height;
            previewImage.alt = source.alt;
            previewLink.href = row.href;
            previewLink.setAttribute('aria-label', `Open ${row.dataset.title}`);
            document.getElementById('preview-title').textContent = row.dataset.title;
            document.getElementById('preview-number').textContent = `PROJECT_${row.dataset.number}`;
            document.getElementById('preview-filename').textContent = row.dataset.filename;
            document.getElementById('preview-date').textContent = row.dataset.date;
            document.getElementById('preview-count').textContent = `${row.dataset.count} photographs`;
        };
        projects.forEach(row => {
            row.addEventListener('pointerenter', () => selectProject(row));
            row.addEventListener('focus', () => selectProject(row));
        });
        desktop.addEventListener('change', () => {
            if (desktop.matches) selectProject(selected);
            else projects.forEach(row => row.classList.remove('is-active'));
        });
        selectProject(selected);
    }

    const dialog = document.getElementById('lightbox');
    if (!dialog || typeof dialog.showModal !== 'function') return;

    const photoLinks = [...document.querySelectorAll('[data-photo]')];
    const photo = document.getElementById('lb-img');
    const status = document.getElementById('lb-status');
    const previous = document.getElementById('lb-prev');
    const next = document.getElementById('lb-next');
    const close = document.getElementById('lb-close');
    let group = [];
    let current = 0;
    let opener = null;
    let previousOverflow = '';
    let requestId = 0;

    const showPhoto = index => {
        current = (index + group.length) % group.length;
        const link = group[current];
        const id = ++requestId;
        photo.hidden = true;
        photo.alt = link.dataset.title;
        document.getElementById('lb-title').textContent = link.dataset.title;
        document.getElementById('lb-filename').textContent = link.dataset.filename;
        document.getElementById('lb-metadata').textContent = link.dataset.metadata;
        document.getElementById('lb-counter').textContent = `${String(current + 1).padStart(3, '0')} / ${String(group.length).padStart(3, '0')}`;
        previous.disabled = next.disabled = group.length < 2;
        status.textContent = 'Loading photograph…';
        const loader = new Image();
        loader.onload = async () => {
            if (id !== requestId || !dialog.open) return;
            photo.src = link.href;
            try {
                // The preloader finishing does not mean the displayed element
                // has decoded its pixels. Keep the loading state until it has.
                await photo.decode();
            } catch {
                loader.onerror();
                return;
            }
            if (id !== requestId || !dialog.open) return;
            photo.hidden = false;
            status.textContent = '';
        };
        loader.onerror = () => {
            if (id !== requestId || !dialog.open) return;
            status.textContent = 'This photograph could not be loaded. Try another image or ';
            const original = document.createElement('a');
            original.href = link.href;
            original.textContent = 'open the image directly ↗';
            status.append(original);
        };
        loader.src = link.href;
    };

    photoLinks.forEach(link => link.addEventListener('click', event => {
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        const collection = link.closest('.archive-collection') || document.getElementById('gallery');
        group = collection ? [...collection.querySelectorAll('[data-photo]')] : photoLinks;
        opener = link;
        previousOverflow = document.body.style.overflow;
        dialog.showModal();
        document.body.style.overflow = 'hidden';
        showPhoto(group.indexOf(link));
        close.focus();
    }));

    close.addEventListener('click', () => dialog.close());
    previous.addEventListener('click', () => showPhoto(current - 1));
    next.addEventListener('click', () => showPhoto(current + 1));
    dialog.addEventListener('close', () => {
        requestId++;
        document.body.style.overflow = previousOverflow;
        photo.removeAttribute('src');
        status.textContent = '';
        opener?.focus({ preventScroll: true });
    });
    dialog.addEventListener('keydown', event => {
        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
            event.preventDefault();
            showPhoto(current + (event.key === 'ArrowLeft' ? -1 : 1));
        }
        if (event.key === 'Tab') {
            const controls = [...dialog.querySelectorAll('button:not(:disabled), a[href]')];
            const first = controls[0];
            const last = controls[controls.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        }
    });
    dialog.addEventListener('click', event => {
        if (event.target === dialog || event.target.classList.contains('lightbox-stage')) dialog.close();
    });
})();
