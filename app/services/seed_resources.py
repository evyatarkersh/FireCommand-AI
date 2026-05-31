"""
Service module for seeding fire station and resource data into the database.
This module provides functionality to populate the database with real Israeli fire stations across all districts,
along with their associated firefighting resources such as vehicles and aircraft.
"""

from app.extensions import db
from app.models.resources import Station, Resource


def seed_real_israel_stations():
    """
    Seeds the database with all Israeli fire stations and their resources across multiple districts.
    Creates stations with geographic coordinates and assigns appropriate resources based on station type (Regional stations get 4 SAAR, 2 ESHED, 2 ROTEM units; Sub-stations get 2 SAAR, 1 ROTEM; Airbases get 4 AIR_TRACTOR aircraft).
    """
    stations_data = [
        # --- Dan District ---
        {"name": "Bnei Brak (Regional)", "district": "Dan", "lat": 32.090961, "lon": 34.839404},
        {"name": "Yehud", "district": "Dan", "lat": 32.0336, "lon": 34.8878},
        {"name": "Or Yehuda-Savyon", "district": "Dan", "lat": 32.037388, "lon": 34.866455},
        {"name": "Givatayim (Regional)", "district": "Dan", "lat": 32.070845, "lon": 34.813145},
        {"name": "Herzliya (Regional)", "district": "Dan", "lat": 32.164558, "lon": 34.824948},
        {"name": "Ramat HaSharon", "district": "Dan", "lat": 32.135232, "lon": 34.8529},
        {"name": "Holon (Regional)", "district": "Dan", "lat": 32.00962, "lon": 34.798239},
        {"name": "Bat Yam", "district": "Dan", "lat": 32.012307, "lon": 34.750451},
        {"name": "Ramat Gan (Regional)", "district": "Dan", "lat": 32.067713, "lon": 34.833227},
        {"name": "Bursa", "district": "Dan", "lat": 32.088682, "lon": 34.801597},
        {"name": "Tel Aviv (Regional)", "district": "Dan", "lat": 32.102845, "lon": 34.78113},
        {"name": "Alon", "district": "Dan", "lat": 32.062329, "lon": 34.792394},
        {"name": "Atidim", "district": "Dan", "lat": 32.106473, "lon": 34.833653},
        {"name": "Jaffa", "district": "Dan", "lat": 32.049614, "lon": 34.763016},
        {"name": "Sarona", "district": "Dan", "lat": 32.072612, "lon": 34.784945},

        # --- South District ---
        {"name": "Eilat (Regional)", "district": "South", "lat": 29.565179, "lon": 34.950331},
        {"name": "Yotvata", "district": "South", "lat": 29.897416, "lon": 35.067873},
        {"name": "Ashkelon (Regional)", "district": "South", "lat": 31.659795, "lon": 34.589168},
        {"name": "Kiryat Gat", "district": "South", "lat": 31.605407, "lon": 34.774893},
        {"name": "Sderot", "district": "South", "lat": 31.529782, "lon": 34.599888},
        {"name": "Ashdod (Regional)", "district": "South", "lat": 31.807734, "lon": 34.661247},
        {"name": "Ad Halom", "district": "South", "lat": 31.780785, "lon": 34.654479},
        {"name": "Kiryat Malakhi", "district": "South", "lat": 31.737179, "lon": 34.749847},
        {"name": "Gan Yavne", "district": "South", "lat": 31.782737, "lon": 34.705862},
        {"name": "Beer Sheva (Regional)", "district": "South", "lat": 31.248818, "lon": 34.819274},
        {"name": "Beer Sheva West", "district": "South", "lat": 31.252998, "lon": 34.756571},
        {"name": "Ramat Hovav", "district": "South", "lat": 31.135492, "lon": 34.782038},
        {"name": "Mitzpe Ramon", "district": "South", "lat": 30.61101, "lon": 34.804063},
        {"name": "Netivot", "district": "South", "lat": 31.415558, "lon": 34.589727},
        {"name": "Ofakim", "district": "South", "lat": 31.318879, "lon": 34.617177},
        {"name": "Rahat", "district": "South", "lat": 31.403636, "lon": 34.755227},
        {"name": "Eshkol", "district": "South", "lat": 31.303782, "lon": 34.431701},
        {"name": "Dimona", "district": "South", "lat": 31.064064, "lon": 35.022489},
        {"name": "Arad", "district": "South", "lat": 31.249449, "lon": 35.207541},
        {"name": "Yeruham", "district": "South", "lat": 30.986084, "lon": 34.936121},
        {"name": "Tamar (Neve Zohar)", "district": "South", "lat": 31.15184, "lon": 35.366357},
        {"name": "Sapir", "district": "South", "lat": 30.61305, "lon": 35.187748},

        # --- Coastal District ---
        {"name": "Hadera (Regional)", "district": "Coastal", "lat": 32.439851, "lon": 34.930794},
        {"name": "Haifa (Regional)", "district": "Coastal", "lat": 32.799099, "lon": 35.021355},
        {"name": "Zvulun (Regional)", "district": "Coastal", "lat": 32.92632, "lon": 35.082783},
        {"name": "Krayot", "district": "Coastal", "lat": 32.861296, "lon": 35.098502},

        # --- Judea and Samaria District ---
        {"name": "Binyamin (Regional)", "district": "Judea and Samaria", "lat": 31.785344, "lon": 35.314132},
        {"name": "Givat Zeev", "district": "Judea and Samaria", "lat": 31.865919, "lon": 35.166538},
        {"name": "Matityahu", "district": "Judea and Samaria", "lat": 31.930173, "lon": 35.026736},
        {"name": "Ofra", "district": "Judea and Samaria", "lat": 31.957675, "lon": 35.257068},
        {"name": "Shomron (Regional)", "district": "Judea and Samaria", "lat": 32.103845, "lon": 35.168432},
        {"name": "Jordan Valley", "district": "Judea and Samaria", "lat": 32.099134, "lon": 35.495271},
        {"name": "Shaked", "district": "Judea and Samaria", "lat": 32.481431, "lon": 35.15925},
        {"name": "Karnei Shomron", "district": "Judea and Samaria", "lat": 32.175164, "lon": 35.097471},
        {"name": "Elkana", "district": "Judea and Samaria", "lat": 32.111448, "lon": 35.035678},
        {"name": "Yehuda (Regional)", "district": "Judea and Samaria", "lat": 31.706715, "lon": 35.12332},
        {"name": "Beitar Illit", "district": "Judea and Samaria", "lat": 31.696, "lon": 35.107},
        {"name": "Kiryat Arba", "district": "Judea and Samaria", "lat": 31.529983, "lon": 35.119114},
        {"name": "Gush Etzion", "district": "Judea and Samaria", "lat": 31.646385, "lon": 35.130404},

        # --- Jerusalem District ---
        {"name": "Beit Shemesh (Regional)", "district": "Jerusalem", "lat": 31.749877, "lon": 34.979757},
        {"name": "Rama", "district": "Jerusalem", "lat": 31.71513, "lon": 34.996383},
        {"name": "Harim", "district": "Jerusalem", "lat": 31.729246, "lon": 35.081832},
        {"name": "Maoz", "district": "Jerusalem", "lat": 31.792005, "lon": 35.144131},
        {"name": "Nahshon", "district": "Jerusalem", "lat": 31.811036, "lon": 34.931884},
        {"name": "HaEla", "district": "Jerusalem", "lat": 31.684909, "lon": 34.947293},
        {"name": "Jerusalem (Regional)", "district": "Jerusalem", "lat": 31.760374, "lon": 35.199704},
        {"name": "Leom", "district": "Jerusalem", "lat": 31.782812, "lon": 35.204781},
        {"name": "Pisga", "district": "Jerusalem", "lat": 31.826619, "lon": 35.238054},
        {"name": "Egoz", "district": "Jerusalem", "lat": 31.785414, "lon": 35.237374},
        {"name": "Itri", "district": "Jerusalem", "lat": 31.75, "lon": 35.21},
        {"name": "Rimon", "district": "Jerusalem", "lat": 31.794, "lon": 35.201},

        # --- Central District ---
        {"name": "Ayalon (Regional)", "district": "Central", "lat": 31.937214, "lon": 34.887063},
        {"name": "Modiin", "district": "Central", "lat": 31.917987, "lon": 35.000792},
        {"name": "Shoham", "district": "Central", "lat": 31.986235, "lon": 34.932933},
        {"name": "HaSharon (Regional)", "district": "Central", "lat": 32.180733, "lon": 34.896814},
        {"name": "Mitzpe Sapir", "district": "Central", "lat": 32.218738, "lon": 34.985315},
        {"name": "Netanya (Regional)", "district": "Central", "lat": 32.321542, "lon": 34.867655},
        {"name": "Yakhon", "district": "Central", "lat": 32.359571, "lon": 34.992987},
        {"name": "Kadima", "district": "Central", "lat": 32.283047, "lon": 34.907955},
        {"name": "Petah Tikva (Regional)", "district": "Central", "lat": 32.098322, "lon": 34.887217},
        {"name": "Rosh HaAyin", "district": "Central", "lat": 32.094128, "lon": 34.941989},
        {"name": "Elad", "district": "Central", "lat": 32.053336, "lon": 34.944679},
        {"name": "Rishon LeZion (Regional)", "district": "Central", "lat": 31.97835, "lon": 34.791257},
        {"name": "Rishon LeZion Ind. Zone", "district": "Central", "lat": 31.986, "lon": 34.771},
        {"name": "Rehovot (Regional)", "district": "Central", "lat": 31.896802, "lon": 34.797826},
        {"name": "Yavne", "district": "Central", "lat": 31.873927, "lon": 34.733493},
        {"name": "Gedera", "district": "Central", "lat": 31.805037, "lon": 34.779896},

        # --- North District ---
        {"name": "Galilee-Golan (Regional)", "district": "North", "lat": 33.195362, "lon": 35.568665},
        {"name": "Hatzor", "district": "North", "lat": 32.985612, "lon": 35.552748},
        {"name": "Safed", "district": "North", "lat": 32.970761, "lon": 35.504223},
        {"name": "Katzrin", "district": "North", "lat": 32.994005, "lon": 35.711231},
        {"name": "Mas'ade", "district": "North", "lat": 33.231827, "lon": 35.756317},
        {"name": "Bnei Yehuda", "district": "North", "lat": 32.797492, "lon": 35.686808},
        {"name": "Central Galilee (Regional)", "district": "North", "lat": 32.924989, "lon": 35.322764},
        {"name": "Ma'alot", "district": "North", "lat": 33.018053, "lon": 35.270841},
        {"name": "Shefa-'Amr", "district": "North", "lat": 32.81176, "lon": 35.16455},
        {"name": "Misgav-Teradion", "district": "North", "lat": 32.870147, "lon": 35.277943},
        {"name": "Tiberias (Regional)", "district": "North", "lat": 32.789901, "lon": 35.515709},
        {"name": "Tamra", "district": "North", "lat": 32.856634, "lon": 35.192969},
        {"name": "Tzemach", "district": "North", "lat": 32.70407, "lon": 35.589873},
        {"name": "Nazareth", "district": "North", "lat": 32.699172, "lon": 35.309252},
        {"name": "Kadoorie", "district": "North", "lat": 32.70576, "lon": 35.407433},
        {"name": "Tzalmon", "district": "North", "lat": 32.87365, "lon": 35.446121},
        {"name": "Afula (Regional)", "district": "North", "lat": 32.616753, "lon": 35.28838},
        {"name": "Beit She'an", "district": "North", "lat": 32.501885, "lon": 35.493112},
        {"name": "Yokneam", "district": "North", "lat": 32.666219, "lon": 35.106238},
        {"name": "Nof HaGalil (Regional)", "district": "North", "lat": 32.729117, "lon": 35.337941},
        {"name": "Migdal HaEmek", "district": "North", "lat": 32.673084, "lon": 35.251715},
        {"name": "Tziporit", "district": "North", "lat": 32.765686, "lon": 35.315008},

        # --- Airbases ---
        {"name": "Megiddo Airbase - Elad Squadron", "district": "North", "type": "AIRBASE", "lat": 32.5975,
         "lon": 35.2289},
        {"name": "Kedma Airbase - Elad Squadron", "district": "South", "type": "AIRBASE", "lat": 31.6315,
         "lon": 34.7942}
    ]

    print("🚀 Starting Seeding of stations and resources...")
    total_resources = 0

    # Iterate through each station data entry and create station records
    for s_data in stations_data:
        # Determine station type from explicit type field or infer from station name
        if "type" in s_data:
            st_type = s_data["type"]
        else:
            st_type = "REGIONAL" if "(Regional)" in s_data["name"] else "SUB_STATION"

        # Create station instance with geographic coordinates and metadata
        station = Station(
            name=s_data["name"],
            district=s_data["district"],
            station_type=st_type,
            latitude=s_data["lat"],
            longitude=s_data["lon"]
        )
        db.session.add(station)
        db.session.flush()

        # Allocate resources based on station type
        resources_to_add = []
        if st_type == "REGIONAL":
            # Regional stations receive full complement of ground units
            resources_to_add = (['SAAR'] * 4) + (['ESHED'] * 2) + (['ROTEM'] * 2)
        elif st_type == "SUB_STATION":
            # Sub-stations receive reduced ground units
            resources_to_add = (['SAAR'] * 2) + (['ROTEM'] * 1)
        elif st_type == "AIRBASE":
            # Airbases receive aerial firefighting aircraft
            resources_to_add = ['AIR_TRACTOR'] * 4

        # Create resource entries for each allocated unit
        for res_type in resources_to_add:
            resource = Resource(
                station_id=station.id,
                resource_type=res_type,
                status='AVAILABLE',
                current_lat=station.latitude,
                current_lon=station.longitude
            )
            db.session.add(resource)
            total_resources += 1

        print(f"✅ Created {station.name} ({st_type}) with {len(resources_to_add)} resources.")

    # Commit all station and resource records to the database
    db.session.commit()
    print(
        f"\n🎉 Done! Created {len(stations_data)} stations/airbases with a total of {total_resources} resources in Neon DB!")
