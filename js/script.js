window.addEventListener('scroll', () => {
    const topbar = document.querySelector('#topbar');
    topbar.classList.toggle('scrolled', window.scrollY > 120);
});

const gallery = document.getElementById('gallery');
const photoGrids = Array.from(gallery.querySelectorAll('.photoGrid'));
let currentIndex = 0;

const images = photoGrids.map(grid => {
    const a = grid.querySelector('a');
    return a ? a.getAttribute('href') : grid.querySelector('img').getAttribute('src').replace('/thumbs/', '/full/');
});

const lightbox = document.getElementById('lightbox');
const lbImg = document.getElementById('lb-img');
const lbCounter = document.getElementById('lb-counter');

function openLightbox(index) {
    currentIndex = index;
    lbImg.src = images[index];
    lbCounter.textContent = `${index + 1} / ${images.length}`;
    lightbox.classList.add('open');
    document.body.style.overflow = 'hidden';
}

function closeLightbox() {
    lightbox.classList.remove('open');
    document.body.style.overflow = '';
    lbImg.src = '';
}

function navigate(dir) {
    currentIndex = (currentIndex + dir + images.length) % images.length;
    lbImg.src = images[currentIndex];
    lbCounter.textContent = `${currentIndex + 1} / ${images.length}`;
}

gallery.addEventListener('click', e => {
    const grid = e.target.closest('.photoGrid');
    if (!grid) return;
    e.preventDefault();
    const index = photoGrids.indexOf(grid);
    if (index !== -1) openLightbox(index);
});

document.getElementById('lb-close').addEventListener('click', closeLightbox);
document.getElementById('lb-prev').addEventListener('click', () => navigate(-1));
document.getElementById('lb-next').addEventListener('click', () => navigate(1));

lightbox.addEventListener('click', e => {
    if (e.target === lightbox) closeLightbox();
});

document.addEventListener('keydown', e => {
    if (!lightbox.classList.contains('open')) return;
    if (e.key === 'Escape') closeLightbox();
    if (e.key === 'ArrowLeft') navigate(-1);
    if (e.key === 'ArrowRight') navigate(1);
});

let touchStartX = 0;
lightbox.addEventListener('touchstart', e => { touchStartX = e.touches[0].clientX; }, { passive: true });
lightbox.addEventListener('touchend', e => {
    const dx = e.changedTouches[0].clientX - touchStartX;
    if (Math.abs(dx) > 50) navigate(dx < 0 ? 1 : -1);
});
