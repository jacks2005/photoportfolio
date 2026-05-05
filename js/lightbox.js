(function () {
    'use strict';

    var gallery   = document.getElementById('gallery');
    var lightbox  = document.getElementById('lightbox');
    var lbClose   = document.getElementById('lightbox-close');
    var lbPrev    = document.getElementById('lightbox-prev');
    var lbNext    = document.getElementById('lightbox-next');
    var lbCounter = document.getElementById('lightbox-counter');

    // Slot divs slide; img elements carry src/alt/load events
    var slotDivs = [
        document.getElementById('lb-slot-a'),
        document.getElementById('lb-slot-b')
    ];
    var slotImgs = [
        document.getElementById('lightbox-img-a'),
        document.getElementById('lightbox-img-b')
    ];

    if (!gallery || !lightbox) return;

    var items = Array.prototype.slice.call(
        document.querySelectorAll('.gallery-item')
    ).map(function (a) {
        var img = a.querySelector('img');
        return {
            src: a.getAttribute('href'),
            alt: img ? img.getAttribute('alt') : ''
        };
    });

    var currentIndex = 0;
    var activeSlot = 0;
    var animating = false;
    var previouslyFocused = null;

    var DURATION = 320;

    function openLightbox(index) {
        currentIndex = index;
        previouslyFocused = document.activeElement;
        lightbox.setAttribute('aria-hidden', 'false');
        lightbox.classList.add('lb-open');
        document.body.style.overflow = 'hidden';
        showImage(index, 0);
        lbClose.focus();
    }

    function closeLightbox() {
        lightbox.classList.remove('lb-open');
        lightbox.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
        slotImgs[0].src = '';
        slotImgs[0].alt = '';
        slotImgs[1].src = '';
        slotImgs[1].alt = '';
        slotDivs[0].style.transition = 'none';
        slotDivs[0].style.transform  = 'translateX(0)';
        slotDivs[0].style.opacity    = '1';
        slotDivs[1].style.transition = 'none';
        slotDivs[1].style.transform  = 'translateX(100%)';
        slotDivs[1].style.opacity    = '1';
        activeSlot = 0;
        animating  = false;
        if (previouslyFocused) previouslyFocused.focus();
    }

    function updateUI(index) {
        lbCounter.textContent = (index + 1) + ' / ' + items.length;
        lbPrev.disabled = (index === 0);
        lbNext.disabled = (index === items.length - 1);
    }

    // direction: 0 = open (fade, no slide), +1 = next (slide left), -1 = prev (slide right)
    function showImage(index, direction) {
        if (index < 0 || index >= items.length) return;

        var item   = items[index];
        var outIdx = activeSlot;
        var inIdx  = 1 - activeSlot;

        updateUI(index);

        if (direction === 0) {
            // Initial open: fade the active slot in, park the other off-screen
            slotDivs[outIdx].style.transition = 'none';
            slotDivs[outIdx].style.transform  = 'translateX(0)';
            slotDivs[outIdx].style.opacity    = '0';
            slotDivs[inIdx].style.transition  = 'none';
            slotDivs[inIdx].style.transform   = 'translateX(100%)';
            slotImgs[outIdx].src = item.src;
            slotImgs[outIdx].alt = item.alt;
            slotImgs[outIdx].removeAttribute('aria-hidden');
            slotImgs[inIdx].setAttribute('aria-hidden', 'true');

            function onOpen() {
                slotImgs[outIdx].removeEventListener('load',  onOpen);
                slotImgs[outIdx].removeEventListener('error', onOpen);
                slotDivs[outIdx].style.transition = '';
                slotDivs[outIdx].style.opacity    = '1';
            }
            slotImgs[outIdx].addEventListener('load',  onOpen);
            slotImgs[outIdx].addEventListener('error', onOpen);
            return;
        }

        animating = true;

        var enterFrom = direction > 0 ? '100%'  : '-100%';
        var exitTo    = direction > 0 ? '-100%' : '100%';

        // Park incoming slot off-screen instantly, then load
        slotDivs[inIdx].style.transition = 'none';
        slotDivs[inIdx].style.transform  = 'translateX(' + enterFrom + ')';
        slotImgs[inIdx].src = item.src;
        slotImgs[inIdx].alt = item.alt;
        slotImgs[inIdx].removeAttribute('aria-hidden');

        function startSlide() {
            slotImgs[inIdx].removeEventListener('load',  startSlide);
            slotImgs[inIdx].removeEventListener('error', startSlide);

            // Force reflow so the browser commits the off-screen position
            // before transitions are re-enabled
            slotDivs[inIdx].getBoundingClientRect();

            slotDivs[inIdx].style.transition = '';
            slotDivs[outIdx].style.transition = '';

            slotDivs[inIdx].style.transform  = 'translateX(0)';
            slotDivs[outIdx].style.transform = 'translateX(' + exitTo + ')';

            setTimeout(function () {
                slotImgs[outIdx].setAttribute('aria-hidden', 'true');
                slotDivs[outIdx].style.transition = 'none';
                slotDivs[outIdx].style.transform  = 'translateX(' + enterFrom + ')';
                activeSlot = inIdx;
                animating  = false;
            }, DURATION);
        }

        if (slotImgs[inIdx].complete) {
            startSlide();
        } else {
            slotImgs[inIdx].addEventListener('load',  startSlide, { once: true });
            slotImgs[inIdx].addEventListener('error', startSlide, { once: true });
        }
    }

    function navigate(delta) {
        if (animating) return;
        var next = currentIndex + delta;
        if (next < 0 || next >= items.length) return;
        currentIndex = next;
        showImage(currentIndex, delta);
    }

    gallery.addEventListener('click', function (e) {
        var link = e.target.closest('.gallery-item');
        if (!link) return;
        e.preventDefault();
        var index = parseInt(link.getAttribute('data-index'), 10);
        if (!isNaN(index)) openLightbox(index);
    });

    lbClose.addEventListener('click', closeLightbox);
    document.getElementById('lightbox-backdrop').addEventListener('click', closeLightbox);
    lbPrev.addEventListener('click', function () { navigate(-1); });
    lbNext.addEventListener('click', function () { navigate(+1); });

    var touchStartX = 0;
    var touchStartY = 0;

    lightbox.addEventListener('touchstart', function (e) {
        touchStartX = e.changedTouches[0].clientX;
        touchStartY = e.changedTouches[0].clientY;
    }, { passive: true });

    lightbox.addEventListener('touchend', function (e) {
        var dx = e.changedTouches[0].clientX - touchStartX;
        var dy = e.changedTouches[0].clientY - touchStartY;
        if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) {
            navigate(dx < 0 ? +1 : -1);
        }
    }, { passive: true });

    document.addEventListener('keydown', function (e) {
        if (!lightbox.classList.contains('lb-open')) return;
        switch (e.key) {
            case 'Escape':     closeLightbox(); break;
            case 'ArrowLeft':  navigate(-1); e.preventDefault(); break;
            case 'ArrowRight': navigate(+1); e.preventDefault(); break;
        }
    });

    lightbox.addEventListener('keydown', function (e) {
        if (e.key !== 'Tab') return;
        var focusable = Array.prototype.slice.call(
            lightbox.querySelectorAll('button:not([disabled])')
        );
        if (focusable.length === 0) return;
        var first = focusable[0];
        var last  = focusable[focusable.length - 1];
        if (e.shiftKey) {
            if (document.activeElement === first) { last.focus(); e.preventDefault(); }
        } else {
            if (document.activeElement === last) { first.focus(); e.preventDefault(); }
        }
    });

})();
