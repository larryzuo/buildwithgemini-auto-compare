"""Tool to fetch studio car photos from carimagesapi.com
and store them in Google Cloud Storage for permanent public access.
"""

import json
import logging
import os
import re
import urllib.parse
import urllib.request
from typing import Any, Optional

from google import genai
from google.adk.tools import ToolContext
from google.cloud import firestore, storage
from google.genai import types

logger = logging.getLogger(__name__)

# Hardcoded project ID and bucket strings (avoids Agent Platform project number issue)
PROJECT_ID = "qwiklabs-gcp-04-228ecee47c16"
BUCKET_NAME = "autocompare-cars-228ecee4"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

storage_client = storage.Client(project=PROJECT_ID)
db = firestore.Client(project=PROJECT_ID)


def _get_api_key() -> str:
    """Retrieve CarImages API key from environment variables."""
    api_key = os.environ.get("CARIMAGES_API_KEY") or os.environ.get("CAR_IMAGES_API_KEY")
    if not api_key:
        raise ValueError(
            "CARIMAGES_API_KEY environment variable is not set. "
            "Please configure your carimagesapi.com API key."
        )
    return api_key.strip()


def _fetch_from_carimagesapi(
    make: str,
    model: str,
    year: Optional[int] = None,
    view: str = "front34",
) -> Optional[tuple[bytes, str]]:
    """Fetch vehicle image bytes and content-type from carimagesapi.com using signed URLs.

    Args:
        make: Vehicle manufacturer (e.g. 'Porsche', 'BMW').
        model: Vehicle model name (e.g. '911', 'M3').
        year: Optional model year (e.g. 2024).
        view: Camera angle ('front34', 'rear34', 'rear', 'side', 'front').

    Returns:
        Tuple of (image_bytes, content_type) or None if fetch failed.
    """
    api_key = _get_api_key()
    headers = {"User-Agent": USER_AGENT}

    # Model candidates: try full model name first, then simplified name if multi-word
    model_candidates = [model.strip()]
    parts = model.strip().split()
    if len(parts) > 1:
        model_candidates.append(parts[0])

    for cand in model_candidates:
        params: dict[str, str] = {
            "api_key": api_key,
            "make": make.strip(),
            "model": cand,
            "view": view,
        }
        if year:
            params["year"] = str(year)

        signed_url_endpoint = (
            f"https://carimagesapi.com/api/v1/signed-url?{urllib.parse.urlencode(params)}"
        )
        try:
            req = urllib.request.Request(signed_url_endpoint, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode())
                img_url = data.get("url")

            if not img_url:
                continue

            # Fetch actual image from signed URL (automatically follows 302 redirect to CDN)
            img_req = urllib.request.Request(img_url, headers=headers)
            with urllib.request.urlopen(img_req, timeout=15) as img_resp:
                img_bytes = img_resp.read()
                content_type = img_resp.headers.get("Content-Type", "image/webp")
                if img_bytes and len(img_bytes) > 500:
                    return img_bytes, content_type
        except Exception as e:
            logger.warning(f"Error fetching {make} {cand} ({view}) from carimagesapi: {e}")
            continue

    return None


def _upload_to_gcs(content: bytes, content_type: str, dest_path: str) -> str:
    """Upload image bytes to Google Cloud Storage and return public HTTPS URL."""
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(dest_path)
    blob.upload_from_string(content, content_type=content_type)
    return f"https://storage.googleapis.com/{BUCKET_NAME}/{dest_path}"


def fetch_and_store_car_images(
    make: str,
    model: str,
    year: Optional[int] = None,
) -> dict[str, Any]:
    """Fetch studio car photos (front-angled ¾, rear-angled ¾, and rear cargo view)
    from carimagesapi.com, download them, and save them to Google Cloud Storage for
    permanent public access.

    Args:
        make: Vehicle manufacturer (e.g. 'Porsche', 'Tesla', 'BMW', 'Toyota').
        model: Vehicle model name (e.g. '911', 'Model 3', 'M3', 'RAV4 Prime').
        year: Optional model year (e.g. 2024).

    Returns:
        A dictionary containing the public Cloud Storage URLs for the vehicle photos.
    """
    clean_make = make.strip()
    clean_model = model.strip()
    car_name = f"{clean_make} {clean_model}"
    slug = re.sub(r"[^a-z0-9]+", "-", f"{clean_make}-{clean_model}".lower()).strip("-")

    results: dict[str, Any] = {
        "status": "success",
        "car": car_name,
        "bucket": BUCKET_NAME,
        "images": {},
    }

    # 1. Fetch front-angled ¾ view ('front34')
    front_data = _fetch_from_carimagesapi(clean_make, clean_model, year=year, view="front34")
    if front_data:
        img_bytes, ctype = front_data
        dest_path = f"cars/{slug}/front_angled.webp"
        try:
            pub_url = _upload_to_gcs(img_bytes, ctype, dest_path)
            results["images"]["front_angled"] = {
                "public_url": pub_url,
                "caption": f"{car_name} - Front ¾ Studio View",
                "source": "carimagesapi.com",
            }
        except Exception as e:
            results["images"]["front_angled_error"] = str(e)
    else:
        results["images"]["front_angled"] = None

    # 2. Fetch rear-angled ¾ view ('rear34')
    rear34_data = _fetch_from_carimagesapi(clean_make, clean_model, year=year, view="rear34")
    if rear34_data:
        img_bytes, ctype = rear34_data
        dest_path = f"cars/{slug}/rear_angled.webp"
        try:
            pub_url = _upload_to_gcs(img_bytes, ctype, dest_path)
            results["images"]["rear_angled"] = {
                "public_url": pub_url,
                "caption": f"{car_name} - Rear ¾ Studio View",
                "source": "carimagesapi.com",
            }
        except Exception as e:
            results["images"]["rear_angled_error"] = str(e)
    else:
        results["images"]["rear_angled"] = None

    # 3. Fetch straight rear view ('rear') for trunk / cargo space reference
    rear_data = _fetch_from_carimagesapi(clean_make, clean_model, year=year, view="rear")
    if rear_data:
        img_bytes, ctype = rear_data
        dest_path = f"cars/{slug}/trunk_space.webp"
        try:
            pub_url = _upload_to_gcs(img_bytes, ctype, dest_path)
            results["images"]["trunk_space"] = {
                "public_url": pub_url,
                "caption": f"{car_name} - Rear Cargo & Tailgate View",
                "source": "carimagesapi.com",
            }
        except Exception as e:
            results["images"]["trunk_space_error"] = str(e)
    elif rear34_data:
        img_bytes, ctype = rear34_data
        dest_path = f"cars/{slug}/trunk_space.webp"
        try:
            pub_url = _upload_to_gcs(img_bytes, ctype, dest_path)
            results["images"]["trunk_space"] = {
                "public_url": pub_url,
                "caption": f"{car_name} - Rear ¾ Cargo View",
                "source": "carimagesapi.com",
            }
        except Exception as e:
            results["images"]["trunk_space_error"] = str(e)
    else:
        results["images"]["trunk_space"] = None

    # Update matching Firestore car record
    try:
        cars_ref = db.collection("cars")
        make_variants = list({clean_make, clean_make.title(), clean_make.upper()})
        query_docs = list(cars_ref.where(filter=firestore.FieldFilter("make", "in", make_variants)).stream())
        for doc in query_docs:
            d_data = doc.to_dict()
            if clean_model.lower() in d_data.get("model", "").lower() or d_data.get("model", "").lower() in clean_model.lower():
                update_fields = {}
                if results["images"].get("front_angled"):
                    update_fields["front_angled_image_url"] = results["images"]["front_angled"]["public_url"]
                if results["images"].get("rear_angled"):
                    update_fields["rear_angled_image_url"] = results["images"]["rear_angled"]["public_url"]
                if results["images"].get("trunk_space"):
                    update_fields["trunk_space_image_url"] = results["images"]["trunk_space"]["public_url"]
                if update_fields:
                    cars_ref.document(doc.id).update(update_fields)
                break
    except Exception as e:
        logger.warning(f"Error updating Firestore car record with images: {e}")

    return results


async def visualize_trunk_luggage(
    make: str,
    model: str,
    tool_context: Optional[ToolContext] = None,
) -> dict[str, Any]:
    """Generate an illustrative luggage visualization showing standard travel luggage
    packed into the vehicle's trunk using the existing trunk image and gemini-3.1-flash-lite-image.

    The generated image is saved to ADK artifacts (Playground Artifacts panel) and uploaded
    to the public Cloud Storage bucket.

    Args:
        make: Vehicle manufacturer (e.g. 'Porsche', 'Tesla', 'BMW').
        model: Vehicle model name (e.g. '911', 'Model 3', 'M3').
        tool_context: ADK ToolContext injected automatically at runtime.

    Returns:
        A dictionary with the public Cloud Storage HTTPS URL of the luggage visualization image.
    """
    clean_make = make.strip()
    clean_model = model.strip()
    car_name = f"{clean_make} {clean_model}"
    slug = re.sub(r"[^a-z0-9]+", "-", f"{clean_make}-{clean_model}".lower()).strip("-")

    # 1. Retrieve the existing trunk/rear image bytes
    trunk_bytes: Optional[bytes] = None
    trunk_mime: str = "image/webp"
    bucket = storage_client.bucket(BUCKET_NAME)

    # Check GCS first for trunk_space or rear_angled
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
            break

    # If not in GCS yet, fetch rear view from carimagesapi.com
    if not trunk_bytes:
        rear_data = _fetch_from_carimagesapi(clean_make, clean_model, view="rear") or _fetch_from_carimagesapi(clean_make, clean_model, view="rear34")
        if rear_data:
            trunk_bytes, trunk_mime = rear_data
            dest_blob = bucket.blob(f"cars/{slug}/trunk_space.webp")
            dest_blob.upload_from_string(trunk_bytes, content_type=trunk_mime)

    if not trunk_bytes:
        return {
            "status": "error",
            "message": f"Could not find a vehicle rear/cargo image for {car_name} to base visualization on.",
        }

    # 2. Call gemini-3.1-flash-lite-image in global region
    genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")

    prompt = (
        f"This image shows the rear and cargo/trunk space of the {car_name}. "
        "Generate a clear, realistic visualization showing standard travel luggage "
        "(suitcases, carry-on bags, duffel bags) neatly packed inside this exact vehicle's cargo area "
        "to clearly demonstrate real-world luggage and cargo storage capacity."
    )

    contents = [
        types.Part.from_bytes(data=trunk_bytes, mime_type=trunk_mime),
        prompt,
    ]

    response = genai_client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=contents,
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )

    generated_bytes: Optional[bytes] = None
    if response.candidates and response.candidates[0].content:
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                generated_bytes = part.inline_data.data
                break

    if not generated_bytes:
        return {
            "status": "error",
            "message": f"Failed to generate luggage visualization image for {car_name}.",
        }

    # 3. (1) Save with tool_context.save_artifact so it shows up in Playground Artifacts panel
    artifact_filename = f"{slug}_trunk_luggage.jpg"
    artifact_saved = False
    if tool_context and hasattr(tool_context, "save_artifact"):
        try:
            artifact_part = types.Part.from_bytes(data=generated_bytes, mime_type="image/jpeg")
            await tool_context.save_artifact(filename=artifact_filename, artifact=artifact_part)
            artifact_saved = True
        except Exception as e:
            logger.warning(f"Could not save artifact to tool_context: {e}")

    # 4. (2) Upload same image bytes to public Cloud Storage bucket
    dest_path = f"cars/{slug}/luggage_visualization.jpg"
    dest_blob = bucket.blob(dest_path)
    dest_blob.upload_from_string(generated_bytes, content_type="image/jpeg")
    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{dest_path}"

    # 5. Optionally update Firestore record
    try:
        cars_ref = db.collection("cars")
        make_variants = list({clean_make, clean_make.title(), clean_make.upper()})
        query_docs = list(cars_ref.where(filter=firestore.FieldFilter("make", "in", make_variants)).stream())
        for doc in query_docs:
            d_data = doc.to_dict()
            if clean_model.lower() in d_data.get("model", "").lower() or d_data.get("model", "").lower() in clean_model.lower():
                cars_ref.document(doc.id).update({"luggage_visualization_url": public_url})
                break
    except Exception as e:
        logger.warning(f"Error updating Firestore: {e}")

    return {
        "status": "success",
        "vehicle": car_name,
        "luggage_visualization_url": public_url,
        "artifact_saved": artifact_filename if artifact_saved else None,
        "model_used": "gemini-3.1-flash-lite-image (global)",
        "message": f"Luggage visualization for {car_name} trunk generated and uploaded.",
    }


async def generate_open_trunk_images(
    make: str,
    model: str,
    tool_context: Optional[ToolContext] = None,
) -> dict[str, Any]:
    """Generate two open trunk/cargo images for a vehicle: one with an empty trunk
    and one packed with travel luggage, using gemini-3.1-flash-lite-image.

    Both images are rendered in a clean studio setting with watermarks removed,
    saved to the ADK Playground Artifacts panel (if tool_context is provided),
    and uploaded to the public Google Cloud Storage bucket.

    Args:
        make: Vehicle manufacturer (e.g. 'BMW', 'Porsche', 'Tesla').
        model: Vehicle model name (e.g. 'M3', '911', 'Model 3').
        tool_context: ADK ToolContext injected automatically at runtime.

    Returns:
        A dictionary with public URLs for both the empty open trunk and luggage-packed trunk.
    """
    clean_make = make.strip()
    clean_model = model.strip()
    car_name = f"{clean_make} {clean_model}"
    slug = re.sub(r"[^a-z0-9]+", "-", f"{clean_make}-{clean_model}".lower()).strip("-")

    # 1. Retrieve the existing trunk/rear image bytes
    trunk_bytes: Optional[bytes] = None
    trunk_mime: str = "image/webp"
    bucket = storage_client.bucket(BUCKET_NAME)

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
            break

    if not trunk_bytes:
        rear_data = _fetch_from_carimagesapi(clean_make, clean_model, view="rear") or _fetch_from_carimagesapi(clean_make, clean_model, view="rear34")
        if rear_data:
            trunk_bytes, trunk_mime = rear_data
            dest_blob = bucket.blob(f"cars/{slug}/trunk_space.webp")
            dest_blob.upload_from_string(trunk_bytes, content_type=trunk_mime)

    if not trunk_bytes:
        return {
            "status": "error",
            "message": f"Could not find a vehicle rear/cargo image for {car_name} to base generation on.",
        }

    genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")

    # Helper function to generate an image
    def _generate_image(prompt_text: str) -> Optional[bytes]:
        res = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=[
                types.Part.from_bytes(data=trunk_bytes, mime_type=trunk_mime),
                prompt_text,
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        if res.candidates and res.candidates[0].content and res.candidates[0].content.parts:
            for part in res.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    return part.inline_data.data
        return None

    # 2. Generate Empty Open Trunk image
    prompt_empty = (
        f"A professional studio photograph of the rear of this {car_name} with its trunk lid or tailgate wide open, "
        "clearly displaying the clean, empty interior cargo space, trunk floor lining, and luggage compartment in high detail. "
        "Pristine automotive showroom lighting and clean studio environment."
    )
    empty_bytes = _generate_image(prompt_empty)

    # 3. Generate Open Trunk With Luggage image
    prompt_luggage = (
        f"A professional studio photograph of the rear of this {car_name} with its trunk lid or tailgate wide open, "
        "neatly packed with realistic travel luggage (suitcases, carry-on bags, and a duffel bag) "
        "arranged inside the cargo area to demonstrate its storage capacity. "
        "Pristine automotive showroom lighting and clean studio environment."
    )
    luggage_bytes = _generate_image(prompt_luggage)

    results: dict[str, Any] = {
        "status": "success",
        "vehicle": car_name,
        "bucket": BUCKET_NAME,
        "images": {},
    }

    # 4. Upload to GCS and save artifacts
    if empty_bytes:
        empty_path = f"cars/{slug}/open_trunk_empty.jpg"
        bucket.blob(empty_path).upload_from_string(empty_bytes, content_type="image/jpeg")
        empty_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{empty_path}"
        results["images"]["open_trunk_empty"] = empty_url

        if tool_context and hasattr(tool_context, "save_artifact"):
            try:
                part = types.Part.from_bytes(data=empty_bytes, mime_type="image/jpeg")
                await tool_context.save_artifact(filename=f"{slug}_open_trunk_empty.jpg", artifact=part)
            except Exception as e:
                logger.warning(f"Could not save empty trunk artifact: {e}")

    if luggage_bytes:
        luggage_path = f"cars/{slug}/open_trunk_luggage.jpg"
        bucket.blob(luggage_path).upload_from_string(luggage_bytes, content_type="image/jpeg")
        luggage_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{luggage_path}"
        results["images"]["open_trunk_luggage"] = luggage_url

        if tool_context and hasattr(tool_context, "save_artifact"):
            try:
                part = types.Part.from_bytes(data=luggage_bytes, mime_type="image/jpeg")
                await tool_context.save_artifact(filename=f"{slug}_open_trunk_luggage.jpg", artifact=part)
            except Exception as e:
                logger.warning(f"Could not save luggage trunk artifact: {e}")

    # 5. Update Firestore car record
    try:
        cars_ref = db.collection("cars")
        make_variants = list({clean_make, clean_make.title(), clean_make.upper()})
        query_docs = list(cars_ref.where(filter=firestore.FieldFilter("make", "in", make_variants)).stream())
        for doc in query_docs:
            d_data = doc.to_dict()
            if clean_model.lower() in d_data.get("model", "").lower() or d_data.get("model", "").lower() in clean_model.lower():
                update_fields = {}
                if "open_trunk_empty" in results["images"]:
                    update_fields["open_trunk_empty_image_url"] = results["images"]["open_trunk_empty"]
                if "open_trunk_luggage" in results["images"]:
                    update_fields["open_trunk_luggage_image_url"] = results["images"]["open_trunk_luggage"]
                    update_fields["luggage_visualization_url"] = results["images"]["open_trunk_luggage"]
                if update_fields:
                    cars_ref.document(doc.id).update(update_fields)
                break
    except Exception as e:
        logger.warning(f"Error updating Firestore: {e}")

    return results


