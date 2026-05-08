from app import create_app
from app.models import Stylist, db

# Stylist initial data. `image_filename` is a file under
# `app/static/images/stylists/`; the seeder writes the corresponding
# `/static/images/stylists/<file>` path into `image_url` so the template's
# `<img src>` works without extra Jinja plumbing.
STATIC_IMAGE_DIR = "/static/images/stylists"

stylists_data = [
    {
        "name": "Supercuts",
        "phone": "(207) 873-5908",
        "website": "https://www.supercuts.com/locations/nearme/haircut",
        "instagram": "https://www.instagram.com/supercuts/",
        "email": "",
        "specialties": "Haircut, Color",
        "image_filename": "supercuts.png",
        "google_maps_url": "https://maps.app.goo.gl/M38NdkvxgUVmfxDQA",
    },
    {
        "name": "Salon Renu & Co",
        "phone": "(207) 861-2742",
        "website": "https://www.salonrenu.com/",
        "instagram": "https://www.instagram.com/salonrenu/",
        "email": "",
        "specialties": "Haircut, Styling",
        "image_filename": "salon-renu.png",
        "google_maps_url": "https://maps.app.goo.gl/6FjWrbiGHwQf9qwj6",
    },
    {
        "name": "Salon LaFleur",
        "phone": "(207) 616-3193",
        "website": "https://www.salonlafleur.com/",
        "instagram": "https://www.instagram.com/salon.lafleur.waterville/",
        "email": "",
        "specialties": "Haircut",
        "image_filename": "salon-lafleur.png",
        "google_maps_url": "https://maps.app.goo.gl/qXDzKWivm7AeeobJ6",
    },
    {
        "name": "Couture Styles",
        "phone": "(207) 680-8996",
        "website": "https://couturestylesmaine.com/",
        "instagram": "",
        "email": "",
        "specialties": "Haircut, Braids",
        "image_filename": "couture-styles.png",
        "google_maps_url": "https://maps.app.goo.gl/JXptr6Wczb2ouhVU8",
    },
    {
        "name": "People's Salon & Spa",
        "phone": "(207) 873-5939",
        "website": "https://peoplessalon.com/",
        "instagram": "https://www.instagram.com/peoplessalonspa/",
        "email": "",
        "specialties": "Haircut, Spa",
        "image_filename": "peoples-salon.png",
        "google_maps_url": "https://maps.app.goo.gl/g9sHsYKhHFXVyihx9",
    },
    {
        "name": "Evolution",
        "phone": "(207) 861-4451",
        "website": "https://evolutionsalondayspa.com/",
        "instagram": "",
        "email": "",
        "specialties": "Balayage, Locs",
        "image_filename": "evolution.jpg",
        "google_maps_url": "https://maps.app.goo.gl/sAkd5A46Bi3H3EF6A",
    },
    {
        "name": "SmartStyle",
        "phone": "(207) 872-6042",
        "website": "https://www.smartstyle.com/locations/nearme/haircut/me/waterville/80-waterville-commons-dr/19103",
        "instagram": "https://www.instagram.com/smartstylesalon/",
        "email": "",
        "specialties": "Haircut",
        "image_filename": "smartstyle.png",
        "google_maps_url": "https://maps.app.goo.gl/qPCArnfgbeDhLqgj9",
    },
    {
        "name": "Hair Studio One",
        "phone": "(207) 616-3305",
        "website": "https://www.vagaro.com/hairstudioone1",
        "instagram": "",
        "email": "",
        "specialties": "Haircut, Styling",
        "image_filename": "hair-studio-one.png",
        "google_maps_url": "https://maps.app.goo.gl/uHEQtApCyHYNe1uX9",
    },
    {
        "name": "Apollo Salon & Spa",
        "phone": "(207) 872-2242",
        "website": "https://apollosalonspa.com/",
        "instagram": "https://www.instagram.com/apollosalonspa/",
        "email": "",
        "specialties": "Haircut, Spa",
        "image_filename": "apollo.png",
        "google_maps_url": "https://maps.app.goo.gl/GgQ24pw9qeeNTcAf8",
    },
    {
        "name": "Heavenly Spa and Cosmetic Ink",
        "phone": "(207) 238-0114",
        "website": "https://heavenlyspame.com/",
        "instagram": "https://www.instagram.com/heavenlyspame/",
        "email": "",
        "specialties": "Spa, Cosmetics",
        "image_filename": "heavenly-spa.png",
        "google_maps_url": "https://maps.app.goo.gl/RJ9PL7VsYV8YAr6o8",
    },
    {
        "name": "The Hair Gallery",
        "phone": "(207) 629-9100",
        "website": "https://reindeer-nectarine-j9cp.squarespace.com/",
        "instagram": "https://www.instagram.com/thehairgallerymaine/",
        "email": "",
        "specialties": "Haircut, Styling",
        "image_filename": "hair-gallery.jpg",
        "google_maps_url": "https://maps.app.goo.gl/3A2zzLnQAXEsA8H36",
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
            stylist = Stylist(
                name=data["name"],
                phone=data["phone"],
                website=data["website"],
                instagram=data["instagram"],
                email=data["email"],
                specialties=data["specialties"],
                image_url=f"{STATIC_IMAGE_DIR}/{data['image_filename']}",
                google_maps_url=data["google_maps_url"],
            )
            db.session.add(stylist)

        db.session.commit()
        print(f"Successfully added {len(stylists_data)} stylists!")


if __name__ == "__main__":
    seed_database()
