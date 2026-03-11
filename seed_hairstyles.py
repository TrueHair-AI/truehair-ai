"""
Seed script for Hairstyle table.
Run from project root: uv run python seed_hairstyles.py
(Or: python seed_hairstyles.py if your venv is activated.)

Preview images are expected in app/static/images/ (e.g. classic_fade_preview_*.png).
"""

from app import create_app
from app.models import Hairstyle, db

# Hairstyle data; image_url is filename under static/images/
HAIRSTYLES_DATA = [
    {
        "name": "Classic Fade",
        "description": "A timeless clean cut with short sides and a blended top.",
        "category": "CLASSIC",
        "image_url": "classic_fade_preview_1773038849601.png",
    },
    {
        "name": "Textured Quiff",
        "description": "A versatile, voluminous style with texture and height.",
        "category": "MODERN",
        "image_url": "textured_quiff_preview_1773038861321.png",
    },
    {
        "name": "Pixie Cut",
        "description": "A short, edgy hairstyle that is both bold and chic.",
        "category": "MODERN",
        "image_url": "pixie_cut_preview_1773038873725.png",
    },
    {
        "name": "Buzz Cut",
        "description": "A low-maintenance, ultra-short style that highlights facial features.",
        "category": "CLASSIC",
        "image_url": "buzz_cut_preview_1773038885522.png",
    },
    {
        "name": "Box Braids",
        "description": "A protective and stylish braided look with long-lasting appeal.",
        "category": "MODERN",
        "image_url": "box_braids_preview_1773038901321.png",
    },
    {
        "name": "Long Wavy",
        "description": "Soft, natural waves for a relaxed yet elegant appearance.",
        "category": "CLASSIC",
        "image_url": "long_wavy_preview_1773038913072.png",
    },
]


def seed_hairstyles():
    app = create_app()
    with app.app_context():
        db.create_all()

        print("Seeding hairstyles...")
        for data in HAIRSTYLES_DATA:
            hairstyle = Hairstyle.query.filter_by(name=data["name"]).first()
            if hairstyle:
                hairstyle.description = data["description"]
                hairstyle.category = data["category"]
                hairstyle.image_url = data["image_url"]
            else:
                hairstyle = Hairstyle(
                    name=data["name"],
                    description=data["description"],
                    category=data["category"],
                    image_url=data["image_url"],
                )
                db.session.add(hairstyle)

        db.session.commit()
        print(f"Successfully added/updated {len(HAIRSTYLES_DATA)} hairstyles!")


if __name__ == "__main__":
    seed_hairstyles()
