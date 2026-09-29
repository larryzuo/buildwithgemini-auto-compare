import asyncio
import os
import re
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types
from google.cloud import storage, firestore

PROJECT_ID = "qwiklabs-gcp-04-228ecee47c16"
BUCKET_NAME = "autocompare-cars-228ecee4"

storage_client = storage.Client(project=PROJECT_ID)
bucket = storage_client.bucket(BUCKET_NAME)
db = firestore.Client(project=PROJECT_ID)
genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")

VEHICLES = [
    ("BMW", "M3 Competition"),
    ("Chevrolet", "Corvette Stingray"),
    ("Ford", "Mustang Mach-E GT"),
    ("Hyundai", "Ioniq 5 N"),
    ("Porsche", "911 Carrera"),
    ("Rivian", "R1T Quad-Motor"),
    ("Tesla", "Model 3 Performance"),
    ("Toyota", "RAV4 Prime"),
    ("BMW", "X5"),
]

def generate_image_for_vehicle(trunk_bytes: bytes, trunk_mime: str, prompt: str) -> Optional[bytes]:
    try:
        res = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=[
                types.Part.from_bytes(data=trunk_bytes, mime_type=trunk_mime),
                prompt,
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        if res.candidates and res.candidates[0].content and res.candidates[0].content.parts:
            for part in res.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    return part.inline_data.data
        if res.candidates:
            print("  [Warn] Finish reason:", res.candidates[0].finish_reason, res.candidates[0].finish_message)
    except Exception as e:
        print("  [Error during generation]:", e)
    return None

async def process_vehicle(make: str, model: str):
    car_name = f"{make} {model}"
    slug = re.sub(r"[^a-z0-9]+", "-", f"{make}-{model}".lower()).strip("-")
    print(f"\n==========================================")
    print(f"Processing {car_name} (slug: {slug})...")

    # 1. Retrieve existing trunk image from GCS
    trunk_bytes = None
    trunk_mime = "image/webp"
    for fname, mime in [
        (f"cars/{slug}/trunk_space.webp", "image/webp"),
        (f"cars/{slug}/trunk_space.jpg", "image/jpeg"),
        (f"cars/{slug}/rear_angled.webp", "image/webp"),
        (f"cars/{slug}/trunk_space.png", "image/png"),
    ]:
        blob = bucket.blob(fname)
        if blob.exists():
            trunk_bytes = blob.download_as_bytes()
            trunk_mime = mime
            print(f"  Found source trunk image: {fname} ({len(trunk_bytes)} bytes)")
            break

    if not trunk_bytes:
        print(f"  [Error] No trunk image found for {car_name} in GCS!")
        return

    # 2. Prompt for Empty Open Trunk (No watermarks, clean studio)
    print(f"  1/2 Generating empty open trunk image...")
    prompt_empty = (
        f"A professional studio photograph of the rear of this {car_name} with its trunk lid or tailgate wide open, "
        "clearly displaying the clean, empty interior cargo space, trunk floor lining, and luggage compartment in high detail. "
        "Pristine automotive showroom lighting and clean studio environment."
    )
    empty_bytes = generate_image_for_vehicle(trunk_bytes, trunk_mime, prompt_empty)
    empty_url = None
    if empty_bytes:
        empty_path = f"cars/{slug}/open_trunk_empty.jpg"
        bucket.blob(empty_path).upload_from_string(empty_bytes, content_type="image/jpeg")
        empty_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{empty_path}"
        print(f"  Uploaded empty open trunk: {empty_url}")
    else:
        print(f"  [Failed] Could not generate empty trunk image.")

    # 3. Prompt for Open Trunk with Luggage
    print(f"  2/2 Generating open trunk with luggage image...")
    prompt_luggage = (
        f"A professional studio photograph of the rear of this {car_name} with its trunk lid or tailgate wide open, "
        "neatly packed with realistic travel luggage (suitcases, carry-on bags, and a duffel bag) "
        "arranged inside the cargo area to demonstrate its storage capacity. "
        "Pristine automotive showroom lighting and clean studio environment."
    )
    luggage_bytes = generate_image_for_vehicle(trunk_bytes, trunk_mime, prompt_luggage)
    luggage_url = None
    if luggage_bytes:
        luggage_path = f"cars/{slug}/open_trunk_luggage.jpg"
        bucket.blob(luggage_path).upload_from_string(luggage_bytes, content_type="image/jpeg")
        luggage_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{luggage_path}"
        print(f"  Uploaded luggage open trunk: {luggage_url}")
    else:
        print(f"  [Failed] Could not generate luggage trunk image.")

    # 4. Update Firestore if matching record exists
    try:
        cars_ref = db.collection("cars")
        make_variants = list({make, make.title(), make.upper()})
        query_docs = list(cars_ref.where(filter=firestore.FieldFilter("make", "in", make_variants)).stream())
        for doc in query_docs:
            d_data = doc.to_dict()
            if model.lower() in d_data.get("model", "").lower() or d_data.get("model", "").lower() in model.lower():
                update_fields = {}
                if empty_url:
                    update_fields["open_trunk_empty_image_url"] = empty_url
                if luggage_url:
                    update_fields["open_trunk_luggage_image_url"] = luggage_url
                    update_fields["luggage_visualization_url"] = luggage_url
                if update_fields:
                    cars_ref.document(doc.id).update(update_fields)
                    print(f"  Updated Firestore record {doc.id} with new open trunk URLs.")
                break
    except Exception as e:
        print(f"  [Warn updating Firestore]: {e}")

async def main():
    print("Starting generation of open trunk images (empty & luggage) for all vehicles...")
    for make, model in VEHICLES:
        await process_vehicle(make, model)
    print("\nAll open trunk images processed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
