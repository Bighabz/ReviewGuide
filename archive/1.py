import requests
import re

# -------------------------------------------------------------
# CONFIG - your exact keys
# -------------------------------------------------------------
CLIENT_ID = "wnmYljcFaA4M4AjuFDPfZPLRMDZbmVWY"
CLIENT_SECRET = "H94AtoKx7ft2VkJZ"

# Real cities → Sandbox cities
SANDBOX_CITY_MAP = {
    "ho chi minh": "PAR",
    "saigon": "PAR",
    "hcmc": "PAR",
    "tokyo": "BER",
    "japan": "BER",
}

OUTBOUND_DATE = "2026-02-10"
INBOUND_DATE = "2026-02-15"


# -------------------------------------------------------------
# AUTH
# -------------------------------------------------------------
def get_access_token():
    print("Requesting access token...")
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    token = r.json()["access_token"]
    print("Got token.")
    return token


ACCESS_TOKEN = get_access_token()
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}"}


# -------------------------------------------------------------
# CITY RESOLUTION
# -------------------------------------------------------------
def resolve_city(city_name):
    city = city_name.lower()
    for key, val in SANDBOX_CITY_MAP.items():
        if key in city:
            return val
    return None


# -------------------------------------------------------------
# FLIGHT SEARCH (raw API)
# -------------------------------------------------------------
def get_flights(origin, destination):
    print(f"\nSearching flights {origin} → {destination}")
    url = "https://test.api.amadeus.com/v2/shopping/flight-offers"

    params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": OUTBOUND_DATE,
        "adults": 2,
        "max": 5,
    }

    r = requests.get(url, headers=HEADERS, params=params)
    print("Raw flight response:", r.json())
    return r.json().get("data", [])


# -------------------------------------------------------------
# HOTEL LIST (hotelIds)
# -------------------------------------------------------------
def get_hotel_ids(city_code):
    print(f"\nFetching hotels in {city_code}...")

    url = "https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-city"
    params = {"cityCode": city_code}

    r = requests.get(url, headers=HEADERS, params=params)
    data = r.json().get("data", [])

    hotel_ids = [h["hotelId"] for h in data][:5]
    print("Hotel IDs:", hotel_ids)

    return hotel_ids


# -------------------------------------------------------------
# HOTEL OFFERS (raw API)
# -------------------------------------------------------------
def get_hotel_offers(hotel_ids):
    print(f"\nFetching hotel offers for: {hotel_ids}")

    url = "https://test.api.amadeus.com/v3/shopping/hotel-offers"
    params = {
        "hotelIds": ",".join(hotel_ids),
        "adults": 2,
        "checkInDate": OUTBOUND_DATE,
        "checkOutDate": INBOUND_DATE,
    }

    r = requests.get(url, headers=HEADERS, params=params)
    print("Raw hotel offers:", r.json())

    return r.json().get("data", [])


# -------------------------------------------------------------
# TRIP PLANNER
# -------------------------------------------------------------
def plan_trip(text):
    print("\n=== TRIP REQUEST ===")
    print(text)

    match = re.findall(r"from (.*?) to (.*?) in", text.lower())
    if not match:
        print("Could not parse cities.")
        return

    origin_raw, dest_raw = match[0]

    origin = resolve_city(origin_raw)
    destination = resolve_city(dest_raw)

    if not origin or not destination:
        print("❌ city not supported in sandbox.")
        return

    print(f"\nResolved Origin: {origin}")
    print(f"Resolved Destination: {destination}")

    # Flights
    print("\n=== GET FLIGHTS ===")
    flights = get_flights(origin, destination)

    # Hotels
    print("\n=== GET HOTELS ===")
    hotel_ids = get_hotel_ids(destination)
    hotel_offers = get_hotel_offers(hotel_ids)

    print("\n=== COMPLETE ===")
    print("Flights:", flights[:2])
    print("Hotels:", hotel_offers[:2])


# -------------------------------------------------------------
# RUN
# -------------------------------------------------------------
text = "Plan a 5-day trip from Ho Chi Minh to Tokyo in December for 2 adults"
plan_trip(text)
