import urllib.parse

from app import create_app
from app.models import Stylist, db

# Stylist initial data
stylists_data = [
    {
        "name": "Supercuts",
        "phone": "(207) 873-5908",
        "website": "https://www.supercuts.com/locations/nearme/haircut",
        "instagram": "https://www.instagram.com/supercuts/",
        "email": "",
        "specialties": "Haircut, Color",
    },
    {
        "name": "Salon Renu & Co",
        "phone": "(207) 861-2742",
        "website": "https://www.salonrenu.com/",
        "instagram": "https://www.instagram.com/salonrenu/",
        "email": "",
        "specialties": "Haircut, Styling",
    },
    {
        "name": "Salon LaFleur",
        "phone": "(207) 616-3193",
        "website": "https://www.salonlafleur.com/",
        "instagram": "https://www.instagram.com/salon.lafleur.waterville/",
        "email": "",
        "specialties": "Haircut",
    },
    {
        "name": "Couture Styles",
        "phone": "(207) 680-8996",
        "website": "https://couturestylesmaine.com/",
        "instagram": "",
        "email": "",
        "specialties": "Haircut, Braids",
    },
    {
        "name": "People's Salon & Spa",
        "phone": "(207) 873-5939",
        "website": "https://peoplessalon.com/",
        "instagram": "https://www.instagram.com/peoplessalonspa/",
        "email": "",
        "specialties": "Haircut, Spa",
    },
    {
        "name": "Evolution",
        "phone": "(207) 861-4451",
        "website": "https://evolutionsalondayspa.com/",
        "instagram": "",
        "email": "",
        "specialties": "Balayage, Locs",
    },
    {
        "name": "SmartStyle",
        "phone": "(207) 872-6042",
        "website": "https://www.smartstyle.com/locations/nearme/haircut/me/waterville/80-waterville-commons-dr/19103",
        "instagram": "https://www.instagram.com/smartstylesalon/",
        "email": "",
        "specialties": "Haircut",
    },
    {
        "name": "Hair Studio One",
        "phone": "(207) 616-3305",
        "website": "https://www.vagaro.com/hairstudioone1",
        "instagram": "",
        "email": "",
        "specialties": "Haircut, Styling",
    },
    {
        "name": "Apollo Salon & Spa",
        "phone": "(207) 872-2242",
        "website": "https://apollosalonspa.com/",
        "instagram": "https://www.instagram.com/apollosalonspa/",
        "email": "",
        "specialties": "Haircut, Spa",
    },
    {
        "name": "Heavenly Spa and Cosmetic Ink",
        "phone": "(207) 238-0114",
        "website": "https://heavenlyspame.com/",
        "instagram": "https://www.instagram.com/heavenlyspame/",
        "email": "",
        "specialties": "Spa, Cosmetics",
    },
    {
        "name": "The Hair Gallery",
        "phone": "(207) 629-9100",
        "website": "https://reindeer-nectarine-j9cp.squarespace.com/",
        "instagram": "https://www.instagram.com/thehairgallerymaine/",
        "email": "",
        "specialties": "Haircut, Styling",
    },
]


def seed_database():
    """Seed the database with a directory of initial stylists."""
    app = create_app()
    with app.app_context():
        db.create_all()

        # Clear existing data
        Stylist.query.delete()

        print("Seeding stylists...")
        for data in stylists_data:
            # Generate placeholder image URL
            name_encoded = urllib.parse.quote_plus(data["name"])
            image_url = (
                f"https://placehold.co/400x300/1E1F23/A1A1AA?text={name_encoded}"
            )

            stylist = Stylist(
                name=data["name"],
                phone=data["phone"],
                website=data["website"],
                instagram=data["instagram"],
                email=data["email"],
                specialties=data["specialties"],
                image_url=image_url,
            )
            db.session.add(stylist)

        db.session.commit()
        print(f"Successfully added {len(stylists_data)} stylists!")


if __name__ == "__main__":
    seed_database()
