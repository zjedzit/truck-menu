import os
import random
import uuid
import sys
from datetime import datetime, timedelta, timezone

# Allow imports from main
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import SessionLocal, MongoCompatibility, tenant_context

def seed_bar_data():
    # Set context for the compatibility layer
    tenant_context.set("bar")
    if os.environ.get("BRAND", "").lower() != "bar":
        print("This script is meant to be run inside the 'bar' tenant (bar_app container).")
        print(f"Current BRAND: {os.environ.get('BRAND')}")
        return

    session = SessionLocal()
    db = MongoCompatibility(session)

    print("Seeding Menu Products...")
    
    # Products with detailed descriptions
    products = {
        "classic_burger": {
            "name": "Klasyczny Burger",
            "price": 35.00,
            "description": "Soczysta wołowina 100% z polskiej hodowli (200g), podawana w idealnie zgrillowanej brioszce z chrupiącą sałatą lodową, pomidorem, piklami i naszą autorską konfiturą z czerwonej cebuli. Klasyk, który zawsze się sprawdza.",
            "allergens": "Gluten, laktoza, gorczyca, sezam",
            "kcal": "620",
            "weight": "350",
            "sort_order": 1,
            "to_kitchen": True,
            "no_rating": False,
            "image": "classic_burger.png"
        },
        "cheese_burger": {
            "name": "Serowy Potwór",
            "price": 42.00,
            "description": "Podwójna dawka przyjemności dla fanów sera! Wołowina (200g) owinięta w podwójny, lejący się cheddar i panierowany ser Mimolette, z sosem BBQ, boczkiem i krążkami cebulowymi.",
            "allergens": "Gluten, laktoza, seler, sezam, jaja",
            "kcal": "890",
            "weight": "420",
            "sort_order": 2,
            "to_kitchen": True,
            "no_rating": False,
            "image": "cheese_burger.png"
        },
        "fries": {
            "name": "Chrupiące Frytki",
            "price": 12.00,
            "description": "Złociste, cienkie i klasyczne. Idealnie chrupiące z zewnątrz i puszyste w środku. Podawane z solą gruboziarnistą morską.",
            "allergens": "Brak",
            "kcal": "450",
            "weight": "200",
            "sort_order": 3,
            "to_kitchen": True,
            "no_rating": True,
            "image": "fries.png"
        },
        "cola": {
            "name": "Cola 0.5L",
            "price": 8.00,
            "description": "Kultowy, orzeźwiający napój gazowany. Najlepiej smakuje mocno schłodzony, prosto z oryginalnej, szklanej butelki.",
            "allergens": "Phenylalanine",
            "kcal": "210",
            "weight": "500",
            "sort_order": 4,
            "to_kitchen": False,
            "no_rating": True,
            "image": "cola.png"
        },
        "ketchup": {
            "name": "Ketchup Heinz",
            "price": 3.00,
            "description": "Oryginalny sos pomidorowy do frytek i burgerów.",
            "allergens": "Gorczyca, seler",
            "kcal": "35",
            "weight": "25",
            "sort_order": 5,
            "to_kitchen": False,
            "no_rating": True,
            "image": "ketchup.png"
        },
        "sauce": {
            "name": "Sos Czosnkowy",
            "price": 4.00,
            "description": "Nasz domowy sos na bazie kremowego majonezu i pieczonego czosnku z nutą bieszczadzkich ziół.",
            "allergens": "Jaja, gorczyca, mleko",
            "kcal": "120",
            "weight": "30",
            "sort_order": 6,
            "to_kitchen": False,
            "no_rating": True,
            "image": "sauce.png"
        }
    }

    # Upsert menu products to database
    for key, data in products.items():
        db["menu"].update_one({"_id": key}, {"$set": data}, upsert=True)

    print("Menu seeded successfully.")
    print("Generating simulated historical monthly sales (approx. 600 orders)...")

    # Generate roughly 30 days of sales history
    now = datetime.now(timezone.utc)
    
    # We will simulate ~20 tables a day * 30 days = 600 pos_history entries
    for day in range(30):
        # We process past dates, starting from 30 days ago up to today
        target_date = now - timedelta(days=30-day)
        
        # 10 to 30 receipts per day
        daily_receipts = random.randint(10, 30)
        
        for _ in range(daily_receipts):
            table_no = str(random.randint(1, 12)) # Tables from 1 to 12
            
            # Form an order (items)
            # A typical order has 1-3 burgers, some fries and drinks
            order_items = []
            
            num_burgers = random.choice([1, 1, 2, 2, 3, 4])
            for _ in range(num_burgers):
                b_key = random.choice(["classic_burger", "cheese_burger", "classic_burger"])
                b_data = products[b_key]
                order_items.append({
                    "id": str(uuid.uuid4()),
                    "table_number": table_no,
                    "burger_name": b_data["name"],
                    "price": float(b_data["price"]),
                    "note": "",
                    "to_kitchen": b_data["to_kitchen"],
                    "session_id": f"sim_{day}",
                    "status": "ready",
                    "paid": True
                })
                
                # Add fries sometimes
                if random.random() < 0.7:
                    order_items.append({
                        "id": str(uuid.uuid4()),
                        "table_number": table_no,
                        "burger_name": products["fries"]["name"],
                        "price": float(products["fries"]["price"]),
                        "note": "",
                        "to_kitchen": True,
                        "session_id": f"sim_{day}",
                        "status": "ready",
                        "paid": True
                    })
                
                # Add cola sometimes
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
            
            # Assign random time spanning from 11:00 AM to 22:00 PM for that specific date
            h = random.randint(11, 21)
            m = random.randint(0, 59)
            s = random.randint(0, 59)
            ts = target_date.replace(hour=h, minute=m, second=s)
            
            history_id = f"pos_{ts.strftime('%Y%m%d_%H%M%S')}_{table_no}"
            
            # Format according to current history rules
            # We must use raw AppConfig bypass or manual insertion because MongoCompatibility
            # might complain. Wait, let's just insert proper SQLAlchemy entry.
            # But the simplest way is to just use MongoCompatibility's AppConfig trick or
            # directly make pos_history items.
            from main import POSHistory
            db_item = POSHistory(
                id=history_id,
                table_number=table_no,
                session_id=f"sim_{day}",
                items=order_items,
                total=total_sum,
                fiscal=random.choice([True, True, True, False]), # 75% fiscal
                timestamp=ts
            )
            session.add(db_item)
            
    # Commit all history to DB
    session.commit()
    print("Done! Simulated past orders created. The admin panel charts will now explode with data!")

if __name__ == "__main__":
    seed_bar_data()
