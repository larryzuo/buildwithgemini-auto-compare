"""Client and ADK function tools for the US NHTSA Public Vehicles API.

Free public API from public-apis (no API key required):
https://vpic.nhtsa.dot.gov/api/
"""

import json
import urllib.parse
import urllib.request
from typing import Any, Optional

NHTSA_BASE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles"


def decode_vin(vin: str) -> dict[str, Any]:
    """Decode a Vehicle Identification Number (VIN) using the free US NHTSA public API.

    Fetches verified manufacturer vehicle details including make, model, year, body class,
    powertrain/fuel type, drive type, engine specs, and manufacturing plant country.

    Args:
        vin: 17-character VIN (or partial VIN of at least 10 characters).

    Returns:
        A dictionary with decoded vehicle specifications and NHTSA verified data.
    """
    clean_vin = vin.strip().upper()
    url = f"{NHTSA_BASE_URL}/decodevinvalues/{urllib.parse.quote(clean_vin)}?format=json"
    req = urllib.request.Request(url, headers={"User-Agent": "AutoCompare/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("Results", [])
            if not results:
                return {"status": "error", "message": f"No data returned for VIN {clean_vin}"}

            row = results[0]
            if not row.get("Make") and not row.get("Model"):
                return {
                    "status": "not_found",
                    "vin": clean_vin,
                    "error": row.get("ErrorText", "Vehicle not found for given VIN"),
                }

            return {
                "status": "success",
                "vin": clean_vin,
                "make": row.get("Make", "").title(),
                "model": row.get("Model", ""),
                "model_year": row.get("ModelYear", ""),
                "vehicle_type": row.get("VehicleType", "").title(),
                "body_class": row.get("BodyClass", ""),
                "drive_type": row.get("DriveType", ""),
                "fuel_type": row.get("FuelTypePrimary", ""),
                "electrification_level": row.get("ElectrificationLevel", ""),
                "doors": row.get("Doors", ""),
                "engine_cylinders": row.get("EngineCylinders", ""),
                "engine_hp": row.get("EngineHP", ""),
                "plant_country": row.get("PlantCountry", "").title(),
                "plant_state": row.get("PlantState", "").title(),
                "manufacturer": row.get("Manufacturer", ""),
            }
    except Exception as e:
        return {"status": "error", "message": f"Failed to reach NHTSA API: {str(e)}"}


def lookup_manufacturer_models(make: str, model_year: Optional[int] = None) -> dict[str, Any]:
    """Look up all official vehicle models produced by a manufacturer from the US NHTSA API.

    Args:
        make: Vehicle manufacturer/brand (e.g. 'Porsche', 'Tesla', 'BMW', 'Rivian').
        model_year: Optional model year (e.g. 2024) to filter by.

    Returns:
        A dictionary containing the manufacturer name, count, and list of official models.
    """
    clean_make = make.strip()
    if model_year:
        url = f"{NHTSA_BASE_URL}/GetModelsForMakeYear/make/{urllib.parse.quote(clean_make)}/modelyear/{model_year}?format=json"
    else:
        url = f"{NHTSA_BASE_URL}/getmodelsformake/{urllib.parse.quote(clean_make)}?format=json"

    req = urllib.request.Request(url, headers={"User-Agent": "AutoCompare/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("Results", [])
            models = sorted(list({r.get("Model_Name", "").strip() for r in results if r.get("Model_Name")}))
            return {
                "status": "success",
                "make": clean_make.title(),
                "model_year": model_year,
                "total_models": len(models),
                "models": models[:30],
            }
    except Exception as e:
        return {"status": "error", "message": f"Failed to reach NHTSA API: {str(e)}"}
