"""Seed script for AutoCompare Firestore vehicle catalog."""

from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-04-228ecee47c16"
COLLECTION_NAME = "cars"

SEEDED_CARS = [
    {
        "id": "porsche-911-carrera-2024",
        "make": "Porsche",
        "model": "911 Carrera",
        "year": 2024,
        "body_style": "Coupe",
        "price_msrp": 114400,
        "horsepower": 388,
        "torque_lb_ft": 331,
        "zero_to_sixty_mph": 3.9,
        "top_speed_mph": 183,
        "fuel_type": "Gasoline",
        "mpg_or_mpge": "18 city / 24 hwy",
        "cargo_volume_cu_ft": 4.6,
        "drivetrain": "RWD",
        "summary": "Iconic rear-engine German sports car with exceptional handling and timeless styling.",
        "tags": ["sports car", "luxury", "coupe", "german", "gasoline"]
    },
    {
        "id": "tesla-model-3-perf-2024",
        "make": "Tesla",
        "model": "Model 3 Performance",
        "year": 2024,
        "body_style": "Sedan",
        "price_msrp": 54990,
        "horsepower": 510,
        "torque_lb_ft": 546,
        "zero_to_sixty_mph": 2.9,
        "top_speed_mph": 163,
        "fuel_type": "Electric",
        "mpg_or_mpge": "113 MPGe",
        "cargo_volume_cu_ft": 24.1,
        "drivetrain": "AWD",
        "summary": "High-performance electric sedan featuring blistering acceleration, track mode, and minimal interior.",
        "tags": ["electric", "sedan", "ev", "performance", "fast", "tech"]
    },
    {
        "id": "bmw-m3-comp-2024",
        "make": "BMW",
        "model": "M3 Competition",
        "year": 2024,
        "body_style": "Sedan",
        "price_msrp": 80200,
        "horsepower": 503,
        "torque_lb_ft": 479,
        "zero_to_sixty_mph": 3.4,
        "top_speed_mph": 180,
        "fuel_type": "Gasoline",
        "mpg_or_mpge": "16 city / 23 hwy",
        "cargo_volume_cu_ft": 13.0,
        "drivetrain": "AWD",
        "summary": "Track-bred luxury sports sedan with twin-turbo inline-6 engine and aggressive driving dynamics.",
        "tags": ["sports sedan", "luxury", "german", "gasoline", "track capable"]
    },
    {
        "id": "ford-mustang-mache-gt-2024",
        "make": "Ford",
        "model": "Mustang Mach-E GT",
        "year": 2024,
        "body_style": "SUV",
        "price_msrp": 53995,
        "horsepower": 480,
        "torque_lb_ft": 600,
        "zero_to_sixty_mph": 3.3,
        "top_speed_mph": 124,
        "fuel_type": "Electric",
        "mpg_or_mpge": "84 MPGe",
        "cargo_volume_cu_ft": 29.7,
        "drivetrain": "AWD",
        "summary": "All-electric performance crossover SUV combining Mustang lineage with family-friendly cargo space.",
        "tags": ["electric", "suv", "crossover", "american", "family", "performance"]
    },
    {
        "id": "toyota-rav4-prime-2024",
        "make": "Toyota",
        "model": "RAV4 Prime",
        "year": 2024,
        "body_style": "SUV",
        "price_msrp": 43690,
        "horsepower": 302,
        "torque_lb_ft": 288,
        "zero_to_sixty_mph": 5.7,
        "top_speed_mph": 117,
        "fuel_type": "Plug-in Hybrid",
        "mpg_or_mpge": "38 MPG / 94 MPGe",
        "cargo_volume_cu_ft": 33.5,
        "drivetrain": "AWD",
        "summary": "Practical, efficient plug-in hybrid SUV with 42 miles of pure electric range and quick acceleration.",
        "tags": ["hybrid", "phev", "suv", "reliable", "japanese", "family", "efficient"]
    },
    {
        "id": "hyundai-ioniq-5-n-2025",
        "make": "Hyundai",
        "model": "Ioniq 5 N",
        "year": 2025,
        "body_style": "Crossover",
        "price_msrp": 66100,
        "horsepower": 641,
        "torque_lb_ft": 568,
        "zero_to_sixty_mph": 3.0,
        "top_speed_mph": 162,
        "fuel_type": "Electric",
        "mpg_or_mpge": "78 MPGe",
        "cargo_volume_cu_ft": 26.1,
        "drivetrain": "AWD",
        "summary": "Enthusiast-focused EV crossover with simulated dual-clutch shifting, synthesized engine sound, and track drift modes.",
        "tags": ["electric", "performance", "crossover", "korean", "fun", "track capable"]
    },
    {
        "id": "chevrolet-corvette-stingray-2024",
        "make": "Chevrolet",
        "model": "Corvette Stingray",
        "year": 2024,
        "body_style": "Coupe",
        "price_msrp": 68300,
        "horsepower": 495,
        "torque_lb_ft": 470,
        "zero_to_sixty_mph": 2.9,
        "top_speed_mph": 194,
        "fuel_type": "Gasoline",
        "mpg_or_mpge": "16 city / 24 hwy",
        "cargo_volume_cu_ft": 12.6,
        "drivetrain": "RWD",
        "summary": "Mid-engine American sports car with naturally aspirated 6.2L V8 and exotic supercar performance.",
        "tags": ["supercar", "sports car", "american", "gasoline", "v8"]
    }
]


def seed():
    print(f"Connecting to Firestore with project '{PROJECT_ID}'...")
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection(COLLECTION_NAME)

    for car in SEEDED_CARS:
        doc_id = car["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(car)
        print(f"  ✓ Seeded {car['year']} {car['make']} {car['model']} ({doc_id})")

    print(f"\nSuccessfully seeded {len(SEEDED_CARS)} vehicles to collection '{COLLECTION_NAME}' in project '{PROJECT_ID}'.")


if __name__ == "__main__":
    seed()
