import os
import random
import uuid
import sys
from datetime import datetime, timedelta, timezone

# Allow imports from main
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import SessionLocal, MongoCompatibility, tenant_context, POSHistory

def seed_products():
    # Set context - defaults to 'bar' but can be changed via environment
    tenant = os.environ.get("BRAND", "bar").lower()
    tenant_context.set(tenant)
    
    print(f"--- Seeding Menu Products for tenant: {tenant} ---")
    
    session = SessionLocal()
    db = MongoCompatibility(session)

    # Comprehensive products list based on static/images content
    products = {
        "double_cheese": {
            "name": "Double Cheese Burger",
            "price": 45.00,
            "description": "Podwójna wołowina (400g), poczwórny ser cheddar, pikle, czerwona cebula i sos musztardowy. Dla prawdziwych mięsożerców.",
            "category": "Burgery",
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
            "category": "Burgery",
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
            "category": "Przekąski",
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
            "category": "Dodatki",
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
            "category": "Przekąski",
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
            "category": "Sałatki",
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
            "category": "Desery",
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
            "category": "Napoje",
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
            "category": "Dodatki",
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
            "category": "Sosy",
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
            "category": "Sosy",
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
        # Set both image and image_url to be safe
        data["image_url"] = f"/static/images/{data['image']}"
        db["menu"].update_one({"_id": key}, {"$set": data}, upsert=True)

    print(f"SUCCESS: {len(products)} products seeded for {tenant}.")

    # Generate historical data (copied from seed_bar for completeness)
    print("Generating simulated historical monthly sales...")
    now = datetime.now(timezone.utc)
    for day in range(30):
        target_date = now - timedelta(days=30-day)
        daily_receipts = random.randint(5, 15)
        
        for _ in range(daily_receipts):
            table_no = str(random.randint(1, 10))
            order_items = []
            
            # 1-2 main items
            num_main = random.randint(1, 2)
            for _ in range(num_main):
                p_key = random.choice(["double_cheese", "dynamite_burger", "nuggets"])
                p_data = products[p_key]
                order_items.append({
                    "id": str(uuid.uuid4()),
                    "table_number": table_no,
                    "burger_name": p_data["name"],
                    "price": float(p_data["price"]),
                    "note": "",
                    "to_kitchen": p_data["to_kitchen"],
                    "session_id": f"sim_{day}",
                    "status": "ready",
                    "paid": True
                })
                
                # Add side sometimes
                if random.random() < 0.6:
                    s_key = random.choice(["belgian_fries", "fries", "onion_rings"])
                    s_data = products[s_key]
                    order_items.append({
                        "id": str(uuid.uuid4()),
                        "table_number": table_no,
                        "burger_name": s_data["name"],
                        "price": float(s_data["price"]),
                        "note": "",
                        "to_kitchen": True,
                        "session_id": f"sim_{day}",
                        "status": "ready",
                        "paid": True
                    })
                
                # Add drink sometimes
                if random.random() < 0.8:
                    order_items.append({
                        "id": str(uuid.uuid4()),
                        "table_number": table_no,
                        "burger_name": products["cola"]["name"],
                        "price": float(products["cola"]["price"]),
                        "note": "",
                        "to_kitchen": False,
                        "session_id": f"sim_{day}",
                        "status": "ready",
                        "paid": True
                    })
            
            total_sum = sum(i["price"] for i in order_items)
            h = random.randint(11, 21)
            m = random.randint(0, 59)
            ts = target_date.replace(hour=h, minute=m)
            
            history_id = f"pos_{ts.strftime('%Y%m%d_%H%M%S')}_{table_no}"
            db_item = POSHistory(
                id=history_id,
                table_number=table_no,
                session_id=f"sim_{day}",
                items=order_items,
                total=total_sum,
                fiscal=True,
                timestamp=ts,
                tenant_id=tenant
            )
            session.add(db_item)
            
    session.commit()
    print("Done! Simulated history created.")

if __name__ == "__main__":
    seed_products()
