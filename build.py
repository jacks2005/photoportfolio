import os

photos_folder = "./photos/main"
template_page = "./template.html"
home_page = "./index.html"

images = sorted(
    [f for f in os.listdir(photos_folder) if f.lower().endswith(('.webp', '.jpg', '.jpeg', '.png', '.avif'))],
    key=lambda f: int(os.path.splitext(f)[0].split('-')[-1]) if os.path.splitext(f)[0].split('-')[-1].isdigit() else f,
    reverse=True
)

image_elements = []
for i, image in enumerate(images):
    num = os.path.splitext(image)[0].split('-')[-1]
    alt_text = f"Photo {num}"
    image_elements.append(f'''    <div class="photoGrid">
        <a href="/photos/main/{image}" data-index="{i}" class="gallery-item" aria-label="Open {alt_text} in viewer">
            <img src="/photos/main/{image}"
                 alt="{alt_text}"
                 loading="lazy"
                 sizes="(max-width: 500px) 100vw, (max-width: 650px) calc(50vw - 1.5em), (max-width: 900px) calc(33vw - 1.5em), calc(25vw - 1.5em)">
        </a>
    </div>''')

grid = "\n".join(image_elements)

with open(template_page, "r") as f:
    template = f.read()

output = template.replace('<!-- PHOTOS_INJECT -->', grid)

with open(home_page, "w") as f:
    f.write(output)

print("Built page successfully")
