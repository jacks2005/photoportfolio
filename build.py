import os

thumbs_folder = "./photos/thumbs"
full_folder = "./photos/full"
template_page = "./template.html"
home_page = "./index.html"

images = sorted(
    [f for f in os.listdir(thumbs_folder) if f.lower().endswith(('.webp', '.jpg', '.jpeg', '.png', '.avif'))],
    key=lambda f: int(os.path.splitext(f)[0].split('-')[-1]) if os.path.splitext(f)[0].split('-')[-1].isdigit() else f,
    reverse=True
)

image_elements = []
for image in images:
    image_elements.append(f'''    <div class="photoGrid">
        <a href="/photos/full/{image}">
            <picture>
                <source srcset="/photos/full/{image}" media="(max-width: 500px)">
                <img src="/photos/thumbs/{image}" alt="" loading="lazy">
            </picture>
        </a>
    </div>''')

grid = "\n".join(image_elements)

with open(template_page, "r") as f:
    template = f.read()

output = template.replace('<!-- PHOTOS_INJECT -->', grid)

with open(home_page, "w") as f:
    f.write(output)

print("Built page successfully")
