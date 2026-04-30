import os

photos_folder = "./photos/main"
template_page = "./template.html"
home_page = "./index.html"

images = sorted([f for f in os.listdir(photos_folder) if f.lower().endswith(('.webp', '.jpg', '.jpeg', '.png'))])

image_elements = []
for image in images:
    image_elements.append(f'''    <div class="photoGrid">
        <a href="/photos/main/{image}">
            <img src="/photos/main/{image}" alt="">
        </a>
    </div>''')

grid = "\n".join(image_elements)

with open(template_page, "r") as f:
    template = f.read()

output = template.replace('<!-- PHOTOS_INJECT -->', grid)

with open(home_page, "w") as f:
    f.write(output)

print("Built page successfully")
