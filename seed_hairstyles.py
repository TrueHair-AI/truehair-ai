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
        "description": "A clean cut with short, faded sides and a slightly longer top. Best suited for oval and square face shapes, providing a sharp and professional appearance. Works well with straight to wavy hair textures (1A-2B). Low to medium maintenance, requiring regular trims to keep the fade sharp. Style with a light pomade or styling cream.",
        "category": "CLASSIC",
        "image_url": "classic_fade_preview_1773038849601.png",
    },
    {
        "name": "Textured Quiff",
        "description": "A voluminous style where the hair is swept upwards and backwards, adding height and texture. Excellent for round and square faces as it elongates the profile. Works best with wavy to thick straight hair (1B-2C). Medium maintenance; blow-drying is often needed to achieve volume, along with a matte clay or wax for holding the texture.",
        "category": "MODERN",
        "image_url": "textured_quiff_preview_1773038861321.png",
    },
    {
        "name": "Pixie Cut",
        "description": "A short, edgy, and feminine style that highlights the facial features. Perfect for oval, heart, and round face shapes. Suitable for fine straight hair up to wavy textures (1A-2A). Very low daily maintenance, but requires frequent salon trims every 4-6 weeks to maintain the shape. A texturizing spray adds a piecey, modern finish.",
        "category": "SHORT",
        "image_url": "pixie_cut_preview_1773038873725.png",
    },
    {
        "name": "Buzz Cut",
        "description": "An ultra-short, uniform length cut that is bold and masculine. Complements strong jawlines, square, and oval face shapes. Ideal for any hair texture, from straight to coily (1A-4C). Extremely low maintenance with zero daily styling needed. Just wash and go, though it requires frequent clipping to stay extremely short.",
        "category": "SHORT",
        "image_url": "buzz_cut_preview_1773038885522.png",
    },
    {
        "name": "Box Braids",
        "description": "A timeless protective style featuring individual plaited sections. Flattering on almost all face shapes, particularly oval and heart shapes. Specifically designed for highly textured, curly, and coily hair (3B-4C). Low daily maintenance but requires a time-consuming installation process. Keep the scalp moisturized and use edge control for a fresh look.",
        "category": "PROTECTIVE",
        "image_url": "box_braids_preview_1773038901321.png",
    },
    {
        "name": "Long Wavy",
        "description": "Soft, natural flowing waves that frame the face beautifully. Suits oval, heart, and square face shapes by softening angular features. Designed for naturally wavy hair (2A-2C). Medium to high maintenance; requires a good hydration routine to prevent frizz. Use a leave-in conditioner or sea salt spray to enhance the natural wave pattern.",
        "category": "LONG",
        "image_url": "long_wavy_preview_1773038913072.png",
    },
    {
        "name": "Afro",
        "description": "A natural, voluminous halo of hair celebrating its natural texture. Looks fantastic on diamond, oval, and square face shapes. Best suited for tightly coiled and kinky hair textures (4A-4C). Medium maintenance; requires dedicated moisture via deep conditioning and gentle detangling. Style with a wide-tooth comb or pick and nourishing oils.",
        "category": "TEXTURED",
        "image_url": "afro_preview.png",
    },
    {
        "name": "Cornrows",
        "description": "A traditional protective style where hair is braided close to the scalp in straight or intricate patterns. Versatile for all face shapes. Perfect for curly and coily hair types (3A-4C). Low daily maintenance; protects ends and promotes growth. Requires a silk durag or bonnet at night and regular scalp oiling to maintain neatness.",
        "category": "PROTECTIVE",
        "image_url": "cornrows_preview.png",
    },
    {
        "name": "French Crop",
        "description": "A textured cut featuring a short, blunt fringe with faded or undercut sides. Softens angular faces, making it great for square and diamond face shapes. Suitable for straight to wavy hair (1A-2B), especially fine hair, as the fringe adds thickness. Low maintenance, simply wash and style with a matte paste to emphasize the choppy texture.",
        "category": "MODERN",
        "image_url": "french_crop_preview.png",
    },
    {
        "name": "Curtain Bangs",
        "description": "A face-framing fringe parted down the middle, sweeping outward like curtains. Highly adaptable and flatters round, square, and oval face shapes by adding cheekbone definition. Great on straight to softly curly hair (1A-3A). Medium maintenance; requires round-brush blow-drying for that signature swoop and frequent micro-trims.",
        "category": "CLASSIC",
        "image_url": "curtain_bangs_preview.png",
    },
    {
        "name": "Shag Cut",
        "description": "A highly textured, layered cut that is deliberately messy and full of movement. Complements diamond, oval, and heart face shapes. Works wonderfully with wavy to curly hair (2A-3B) as the layers enhance natural volume. Medium maintenance; relies heavily on styling products like sea salt spray or texturizing mousse for a lived-in aesthetic.",
        "category": "MODERN",
        "image_url": "shag_cut_preview.png",
    },
    {
        "name": "Undercut",
        "description": "A high-contrast style with closely shaved sides and back, leaving a disconnected, longer top. Suits oval and square face shapes best. Adapts well to straight, wavy, and curly textures (1A-3B). High maintenance; requires frequent visits to the barber to keep the sides crisp. The top can be slicked back or left messy using pomade or clay.",
        "category": "BOLD",
        "image_url": "undercut_preview.png",
    },
    {
        "name": "Pompadour",
        "description": "A vintage classic featuring hair swept upwards and backwards with significant volume at the front. Elongates the face, making it excellent for round or oval shapes. Best for thick, straight to wavy hair (1B-2B). High maintenance; demands a blow-dryer, a round brush, and a strong-hold pomade to build and sustain the dramatic height.",
        "category": "CLASSIC",
        "image_url": "pompadour_preview.png",
    },
    {
        "name": "Twist Out",
        "description": "A highly defined, curly style achieved by two-strand twisting wet hair and unraveling it once dry. Perfect for round and heart face shapes. Essential for curly to coily hair (3B-4C) seeking curl definition. Medium maintenance; the style lasts several days with nighttime protection (bonnet). Use twisting creams and light oils for shine and hold.",
        "category": "TEXTURED",
        "image_url": "twist_out_preview.png",
    },
    {
        "name": "Flat Top",
        "description": "A sharp, structured cut where the hair on top is cut to form a flat, level surface, paired with faded sides. Enhances square and oval face shapes. Primarily suited for thick, coarse, and coily hair textures (4A-4C) that can stand upright. High maintenance; requires frequent trims and a hair sponge or pick to maintain the perfectly level geometry.",
        "category": "BOLD",
        "image_url": "flat_top_preview.png",
    },
    {
        "name": "Locs",
        "description": "A natural, roped hairstyle formed by allowing hair to mat or continuously twisting it over time. Highly versatile for any face shape depending on the length and styling. Ideal for highly textured and kinky hair (3C-4C). Low daily maintenance but requires dedicated retwisting sessions every few weeks. Keep the scalp clean and moisturized.",
        "category": "PROTECTIVE",
        "image_url": "locs_preview.png",
    },
    {
        "name": "Tapered Cut",
        "description": "A clean style featuring natural curls or coils on top with a gradual fade on the sides and back. Balances round and oval face shapes wonderfully. A staple for curly and coily hair types (3A-4C). Low to medium maintenance; requires regular barber visits for the fade, while the top simply needs daily moisturizing and curl-defining cream.",
        "category": "SHORT",
        "image_url": "tapered_cut_preview.png",
    },
    {
        "name": "Wolf Cut",
        "description": "A hybrid of a shag and a mullet, featuring choppy layers, volume at the crown, and length in the back. Flattering on oval and round faces as the face-framing layers add dimension. Perfect for wavy and softly curly hair (2A-3A). Medium maintenance; thrives on a messy, undone look, usually achieved with texturizing spray and air-drying.",
        "category": "BOLD",
        "image_url": "wolf_cut_preview.png",
    },
    {
        "name": "Blowout",
        "description": "A voluminous style where the hair is blow-dried upwards and outwards, often paired with a taper fade. Adds length, making it ideal for round and oval faces. Suits straight, wavy, and loose curly hair (1A-3A). High maintenance; requires daily blow-drying with heat protectant and styling cream to achieve that signature windswept volume.",
        "category": "MODERN",
        "image_url": "blowout_preview.png",
    },
    {
        "name": "Side Part",
        "description": "An elegant, traditional haircut characterized by a sharp dividing line on one side of the head. Flatters square and oval face shapes, offering a distinguished, symmetrical look. Ideal for straight to moderately wavy hair (1A-2A). Medium maintenance; styling requires a comb, a clear parting, and a medium-shine pomade or gel for a sleek finish.",
        "category": "CLASSIC",
        "image_url": "side_part_preview.png",
    },
]


def seed_hairstyles():
    """Seed the database with initial hairstyle catalog data."""
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
