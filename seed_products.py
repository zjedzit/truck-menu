import os
import random
import uuid
import sys
from datetime import datetime, timedelta, timezone

# Allow imports from main
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import SessionLocal, MongoCompatibility, tenant_context

def seed_products():
    # Set context - defaults to 'bar' but can be changed via environment
    tenant = os.environ.get("BRAND", "bar").lower()
    tenant_context.set(tenant)
    
    print(f"--- Seeding Menu Products for tenant: {tenant} ---")
    
    session = SessionLocal()
    db = MongoCompatibility(session)

    # Products based on static/images content
    products = {
        "double_cheese": {
            "name": "Double Cheese Burger",
            "price": 45.00,
            "description": "Podwójna wołowina (400g), poczwórny ser cheddar, pikle, czerwona cebula i sos musztardowy. Dla prawdziwych mięsożerców.",
            "allergens": "Gluten, laktoza, gorczyca, sezam",
            "kcal": "1150",
            "weight": "480",
            "sort_order": 1,
            "to_kitchen": True,
            "no_rating": False,
            "image": "Double Cheese.png"
        },
        "dynamite_burger": {
            "name": "Dynamite Burger",
            "price": 39.00,
            "description": "Ostra przygoda! Wołowina (200g), papryczki jalapeño, pikantny sos Dynamite, ser pepper jack i chrupiące nachosy.",
            "allergens": "Gluten, laktoza, jaja, sezam",
            "kcal": "820",
            "weight": "380",
            "sort_order": 2,
            "to_kitchen": True,
            "no_rating": False,
            "image": "Dynamite Burger.png"
        },
        "nuggets": {
            "name": "Złociste Nugetsy",
            "price": 22.00,
            "description": "Kawałki piersi z kurczaka w złocistej, chrupiącej panierce. Podawane z wybranym sosem.",
            "allergens": "Gluten, jaja",
            "kcal": "450",
            "weight": "250",
            "sort_order": 3,
            "to_kitchen": True,
            "no_rating": False,
            "image": "Nugetsy.png"
        },
        "belgian_fries": {
            "name": "Frytki Belgijskie",
            "price": 16.00,
            "description": "Grubo cięte frytki smażone na dwa razy w tradycyjny belgijski sposób. Chrupiące na zewnątrz, miękkie w środku.",
            "allergens": "Brak",
            "kcal": "520",
            "weight": "250",
            "sort_order": 4,
            "to_kitchen": True,
            "no_rating": True,
            "image": "Frytki Belgijskie.png"
        },
        "onion_rings": {
            "name": "Krążki Cebulowe",
            "price": 14.00,
            "description": "Krążki cebulowe w chrupiącej panierce piwnej. Idealna przekąska do burgera.",
            "allergens": "Gluten",
            "kcal": "380",
            "weight": "150",
            "sort_order": 5,
            "to_kitchen": True,
            "no_rating": True,
            "image": "Onion Rings.png"
        },
        "season_salad": {
            "name": "Sałatka Sezonowa",
            "price": 28.00,
            "description": "Miks świeżych sałat, pomidorki koktajlowe, ogórek, rzodkiewka, prażone ziarna słonecznika i winegret miodowo-musztardowy.",
            "allergens": "Gorczyca",
            "kcal": "180",
            "weight": "200",
            "sort_order": 6,
            "to_kitchen": False,
            "no_rating": False,
            "image": "Sałatka Sezonowa.png"
        },
        "brownie": {
            "name": "Brownie z lodami",
            "price": 18.00,
            "description": "Ciepłe brownie czekoladowe z gałką waniliowych lodów rzemieślniczych i polewą malinową.",
            "allergens": "Gluten, laktoza, jaja, orzechy",
            "kcal": "580",
            "weight": "180",
            "sort_order": 7,
            "to_kitchen": False,
            "no_rating": False,
            "image": "Brownie z lodami.png"
        },
        "cola": {
            "name": "Coca-Cola 0.5L",
            "price": 8.00,
            "description": "Klasyczna, orzeźwiająca Coca-Cola w butelce.",
            "allergens": "Brak",
            "kcal": "210",
            "weight": "500",
            "sort_order": 8,
            "to_kitchen": False,
            "no_rating": True,
            "image": "cola.png"
        },
        "fries": {
            "name": "Frytki Klasyczne",
            "price": 12.00,
            "description": "Złociste, cienkie i klasyczne frytki z solą morską.",
            "allergens": "Brak",
            "kcal": "450",
            "weight": "200",
            "sort_order": 9,
            "to_kitchen": True,
            "no_rating": True,
            "image": "fries.png"
        },
        "ketchup": {
            "name": "Ketchup Heinz",
            "price": 3.00,
            "description": "Gęsty sos pomidorowy najwyższej jakości.",
            "allergens": "Gorczyca, seler",
            "kcal": "35",
            "weight": "25",
            "sort_order": 10,
            "to_kitchen": False,
            "no_rating": True,
            "image": "ketchup.png"
        },
        "sauce": {
            "name": "Sos Czosnkowy",
            "price": 4.00,
            "description": "Domowy sos czosnkowy na bazie jogurtu i majonezu.",
            "allergens": "Jaja, gorczyca, mleko",
            "kcal": "120",
            "weight": "30",
            "sort_order": 11,
            "to_kitchen": False,
            "no_rating": True,
            "image": "sauce.png"
        }
    }

    # Upsert menu products to database
    for key, data in products.items():
        db.update_one({"_id": key}, {"$set": data}, upsert=True)

    print(f"SUCCESS: {len(products)} products seeded for {tenant}.")
    
    # Optional: Generate history if requested (but keeping it simple for now)
    print("TIP: Run this script with BRAND environment variable to seed different tenants.")
    print("Example: BRAND=elvis python seed_products.py")

if __name__ == "__main__":
    seed_products()
