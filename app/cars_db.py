"""Firestore vehicle catalog backend for AutoCompare."""

from typing import Any, Optional
from google.cloud import firestore

# Hardcoded GCP project ID as required to avoid project number resolution on Agent Platform
PROJECT_ID = "qwiklabs-gcp-04-228ecee47c16"
COLLECTION_NAME = "cars"

_client: Optional[firestore.Client] = None


def get_db() -> firestore.Client:
    """Return the Firestore client initialized with the hardcoded project ID."""
    global _client
    if _client is None:
        _client = firestore.Client(project=PROJECT_ID)
    return _client


def search_cars(
    query: str = "",
    max_price: Optional[int] = None,
    body_style: Optional[str] = None,
    fuel_type: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Search the vehicle catalog in Firestore by keywords, price, body style, or fuel type.

    Args:
        query: Optional search keyword to match against make, model, summary, or tags (e.g. 'electric', 'Porsche', 'coupe').
        max_price: Optional maximum MSRP price limit (e.g. 70000).
        body_style: Optional body style filter (e.g. 'Sedan', 'Coupe', 'SUV', 'Crossover').
        fuel_type: Optional fuel type filter (e.g. 'Electric', 'Gasoline', 'Plug-in Hybrid').

    Returns:
        A list of matching car documents with their full specifications.
    """
    db = get_db()
    docs = db.collection(COLLECTION_NAME).stream()
    results = []

    q_lower = query.lower().strip() if query else ""
    body_lower = body_style.lower().strip() if body_style else ""
    fuel_lower = fuel_type.lower().strip() if fuel_type else ""

    for doc in docs:
        car = doc.to_dict()
        car["id"] = doc.id

        # Price filter
        if max_price is not None and car.get("price_msrp", 0) > max_price:
            continue

        # Body style filter
        if body_lower and body_lower not in car.get("body_style", "").lower():
            continue

        # Fuel type filter
        if fuel_lower and fuel_lower not in car.get("fuel_type", "").lower():
            continue

        # Keyword filter across make, model, summary, and tags
        if q_lower:
            searchable = (
                f"{car.get('make', '')} {car.get('model', '')} {car.get('summary', '')} "
                f"{' '.join(car.get('tags', []))}"
            ).lower()
            if q_lower not in searchable:
                continue

        results.append(car)

    return results


def get_car_specs(make_or_model: str) -> dict[str, Any]:
    """Retrieve full specifications for a specific car from the Firestore catalog.

    Args:
        make_or_model: The make and/or model of the car (e.g. 'Porsche 911', 'Model 3', 'Corvette').

    Returns:
        The complete car details dictionary, or a message indicating the car was not found.
    """
    db = get_db()
    target = make_or_model.lower().strip()
    docs = db.collection(COLLECTION_NAME).stream()

    for doc in docs:
        car = doc.to_dict()
        car["id"] = doc.id
        full_name = f"{car.get('year', '')} {car.get('make', '')} {car.get('model', '')}".lower()
        make_match = car.get("make", "").lower() in target
        model_match = car.get("model", "").lower() in target or target in car.get("model", "").lower()
        id_match = doc.id in target or target in doc.id

        if target in full_name or (make_match and model_match) or id_match:
            return car

    return {
        "status": "not_found",
        "message": f"Car '{make_or_model}' not found in the catalog. Try searching with search_cars.",
    }


def compare_cars(car_queries: list[str]) -> dict[str, Any]:
    """Compare specifications of two or more cars from the Firestore catalog side-by-side.

    Args:
        car_queries: List of car names or models to compare (e.g. ['Tesla Model 3', 'Porsche 911', 'BMW M3']).

    Returns:
        A structured comparison with specs for each found car and comparison highlights.
    """
    found_cars = []
    missing = []

    for query in car_queries:
        car = get_car_specs(query)
        if car.get("status") == "not_found":
            missing.append(query)
        else:
            found_cars.append(car)

    return {
        "compared_cars_count": len(found_cars),
        "cars": found_cars,
        "not_found": missing,
    }


def add_car(
    make: str,
    model: str,
    year: int,
    body_style: str,
    price_msrp: int,
    horsepower: int,
    torque_lb_ft: int,
    zero_to_sixty_mph: float,
    fuel_type: str,
    mpg_or_mpge: str = "",
    drivetrain: str = "AWD",
    top_speed_mph: Optional[int] = None,
    cargo_volume_cu_ft: Optional[float] = None,
    summary: str = "",
    tags: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Add a new vehicle or update an existing vehicle in the Firestore catalog.

    Args:
        make: Vehicle manufacturer (e.g. 'Rivian', 'Lucid', 'Audi').
        model: Vehicle model name (e.g. 'Air Sapphire', 'R1T').
        year: Model year (e.g. 2024).
        body_style: Vehicle body type (e.g. 'Sedan', 'SUV', 'Coupe', 'Truck').
        price_msrp: Base MSRP in USD (e.g. 89000).
        horsepower: Peak engine or motor horsepower (e.g. 600).
        torque_lb_ft: Peak torque in lb-ft (e.g. 650).
        zero_to_sixty_mph: 0 to 60 mph acceleration time in seconds (e.g. 3.1).
        fuel_type: Primary fuel/powertrain type (e.g. 'Electric', 'Gasoline', 'Hybrid').
        mpg_or_mpge: Fuel economy rating or electric equivalent (e.g. '74 MPGe' or '22 city / 31 hwy').
        drivetrain: Drivetrain configuration ('AWD', 'RWD', 'FWD').
        top_speed_mph: Optional top speed in mph.
        cargo_volume_cu_ft: Optional cargo space in cubic feet.
        summary: Optional 1-2 sentence description of the vehicle's key selling points.
        tags: Optional keywords for search (e.g. ['luxury', 'electric', 'offroad']).

    Returns:
        Status message with the ID of the created or updated document.
    """
    db = get_db()
    # Normalize ID: e.g. rivian-r1t-2024
    clean_make = make.lower().replace(" ", "-")
    clean_model = model.lower().replace(" ", "-")
    doc_id = f"{clean_make}-{clean_model}-{year}"

    car_data: dict[str, Any] = {
        "id": doc_id,
        "make": make,
        "model": model,
        "year": year,
        "body_style": body_style,
        "price_msrp": price_msrp,
        "horsepower": horsepower,
        "torque_lb_ft": torque_lb_ft,
        "zero_to_sixty_mph": zero_to_sixty_mph,
        "fuel_type": fuel_type,
        "mpg_or_mpge": mpg_or_mpge,
        "drivetrain": drivetrain,
        "top_speed_mph": top_speed_mph or 0,
        "cargo_volume_cu_ft": cargo_volume_cu_ft or 0.0,
        "summary": summary,
        "tags": tags or [make.lower(), model.lower(), body_style.lower(), fuel_type.lower()],
    }

    doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
    doc_ref.set(car_data)

    return {
        "status": "success",
        "message": f"Successfully added {year} {make} {model} to Firestore catalog.",
        "car_id": doc_id,
        "car": car_data,
    }


def compare_running_costs(
    car_queries: list[str],
    annual_miles: int = 12000,
    gas_price_per_gal: float = 3.65,
    electricity_price_per_kwh: float = 0.16,
) -> dict[str, Any]:
    """Compare estimated annual and 5-year fuel/electricity energy costs between cars.

    Args:
        car_queries: List of car names or models to compare (e.g. ['Tesla Model 3', 'Porsche 911']).
        annual_miles: Estimated miles driven per year (default 12,000).
        gas_price_per_gal: Average gasoline price in USD per gallon (default $3.65).
        electricity_price_per_kwh: Average electricity price in USD per kWh (default $0.16).

    Returns:
        Dictionary with per-vehicle annual & 5-year fuel/charging costs and comparison breakdown.
    """
    import re

    breakdown = []
    for query in car_queries:
        car = get_car_specs(query)
        if car.get("status") == "not_found":
            continue

        fuel_type = car.get("fuel_type", "Gasoline")
        mpg_str = car.get("mpg_or_mpge", "")
        numbers = [float(n) for n in re.findall(r"\b\d+(?:\.\d+)?\b", mpg_str)]

        if "electric" in fuel_type.lower():
            efficiency = numbers[0] if numbers else 100.0
            # 33.7 kWh per gallon equivalent
            kwh_per_mile = 33.7 / max(efficiency, 1.0)
            annual_cost = round(annual_miles * kwh_per_mile * electricity_price_per_kwh, 2)
            efficiency_display = f"{efficiency:.0f} MPGe"
        elif "hybrid" in fuel_type.lower():
            efficiency = numbers[0] if numbers else 38.0
            # Estimate 50% gas, 50% electric blend
            gas_cost = (annual_miles * 0.5 / max(efficiency, 1.0)) * gas_price_per_gal
            elec_cost = (annual_miles * 0.5 * (33.7 / 90.0)) * electricity_price_per_kwh
            annual_cost = round(gas_cost + elec_cost, 2)
            efficiency_display = f"{efficiency:.0f} MPG (Hybrid)"
        else:
            # Gas: average of city & hwy
            efficiency = (sum(numbers) / len(numbers)) if numbers else 22.0
            gallons = annual_miles / max(efficiency, 1.0)
            annual_cost = round(gallons * gas_price_per_gal, 2)
            efficiency_display = f"{efficiency:.1f} MPG"

        breakdown.append({
            "car": f"{car.get('year', '')} {car.get('make', '')} {car.get('model', '')}",
            "fuel_type": fuel_type,
            "efficiency": efficiency_display,
            "annual_energy_cost_usd": annual_cost,
            "five_year_energy_cost_usd": round(annual_cost * 5, 2),
            "monthly_energy_cost_usd": round(annual_cost / 12, 2),
        })

    # Sort from lowest running cost to highest
    breakdown.sort(key=lambda x: x["annual_energy_cost_usd"])

    result: dict[str, Any] = {
        "annual_miles": annual_miles,
        "assumptions": {
            "gas_price_per_gal": f"${gas_price_per_gal:.2f}",
            "electricity_price_per_kwh": f"${electricity_price_per_kwh:.2f}",
        },
        "vehicles": breakdown,
    }

    if len(breakdown) >= 2:
        diff_annual = round(breakdown[-1]["annual_energy_cost_usd"] - breakdown[0]["annual_energy_cost_usd"], 2)
        diff_5year = round(diff_annual * 5, 2)
        result["savings_comparison"] = (
            f"The {breakdown[0]['car']} saves ${diff_annual:,.2f} per year "
            f"(${diff_5year:,.2f} over 5 years) in energy costs compared to the {breakdown[-1]['car']}."
        )

    return result

