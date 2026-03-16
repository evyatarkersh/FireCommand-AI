from app.extensions import db
from app.models.resources import Station, Resource


def seed_real_israel_stations():
    stations_data = [
        # --- Dan District ---
        {"name": "Bnei Brak (Regional)", "district": "Dan", "lat": 32.0849, "lon": 34.8352},
        {"name": "Yehud", "district": "Dan", "lat": 32.0336, "lon": 34.8878},
        {"name": "Or Yehuda-Savyon", "district": "Dan", "lat": 32.0294, "lon": 34.8617},
        {"name": "Givatayim (Regional)", "district": "Dan", "lat": 32.0722, "lon": 34.8089},
        {"name": "Herzliya (Regional)", "district": "Dan", "lat": 32.1624, "lon": 34.8446},
        {"name": "Ramat HaSharon", "district": "Dan", "lat": 32.1396, "lon": 34.8400},
        {"name": "Holon (Regional)", "district": "Dan", "lat": 32.0108, "lon": 34.7797},
        {"name": "Bat Yam", "district": "Dan", "lat": 32.0158, "lon": 34.7436},
        {"name": "Ramat Gan (Regional)", "district": "Dan", "lat": 32.0823, "lon": 34.8105},
        {"name": "Bursa", "district": "Dan", "lat": 32.0838, "lon": 34.8005},
        {"name": "Tel Aviv (Regional)", "district": "Dan", "lat": 32.0911, "lon": 34.7794},
        {"name": "Alon", "district": "Dan", "lat": 32.0673, "lon": 34.7955},
        {"name": "Atidim", "district": "Dan", "lat": 32.1099, "lon": 34.8402},
        {"name": "Jaffa", "district": "Dan", "lat": 32.0494, "lon": 34.7672},
        {"name": "Sarona", "district": "Dan", "lat": 32.0720, "lon": 34.7850},

        # --- South District ---
        {"name": "Eilat (Regional)", "district": "South", "lat": 29.5581, "lon": 34.9482},
        {"name": "Yotvata", "district": "South", "lat": 29.8953, "lon": 35.0606},
        {"name": "Ashkelon (Regional)", "district": "South", "lat": 31.6693, "lon": 34.5715},
        {"name": "Kiryat Gat", "district": "South", "lat": 31.6061, "lon": 34.7717},
        {"name": "Sderot", "district": "South", "lat": 31.5235, "lon": 34.5956},
        {"name": "Ashdod (Regional)", "district": "South", "lat": 31.7959, "lon": 34.6500},
        {"name": "Ad Halom", "district": "South", "lat": 31.7650, "lon": 34.6650},
        {"name": "Kiryat Malakhi", "district": "South", "lat": 31.7274, "lon": 34.7445},
        {"name": "Gan Yavne", "district": "South", "lat": 31.7825, "lon": 34.7080},
        {"name": "Beer Sheva (Regional)", "district": "South", "lat": 31.2518, "lon": 34.7913},
        {"name": "Beer Sheva West", "district": "South", "lat": 31.2450, "lon": 34.7700},
        {"name": "Ramat Hovav", "district": "South", "lat": 31.1370, "lon": 34.7900},
        {"name": "Mitzpe Ramon", "district": "South", "lat": 30.6080, "lon": 34.8030},
        {"name": "Netivot", "district": "South", "lat": 31.4166, "lon": 34.5885},
        {"name": "Ofakim", "district": "South", "lat": 31.3146, "lon": 34.6203},
        {"name": "Rahat", "district": "South", "lat": 31.3921, "lon": 34.7570},
        {"name": "Eshkol", "district": "South", "lat": 31.2910, "lon": 34.4230},
        {"name": "Dimona", "district": "South", "lat": 31.0667, "lon": 35.0333},
        {"name": "Arad", "district": "South", "lat": 31.2588, "lon": 35.2125},
        {"name": "Yeruham", "district": "South", "lat": 30.9878, "lon": 34.9297},
        {"name": "Tamar (Neve Zohar)", "district": "South", "lat": 31.1340, "lon": 35.3640},
        {"name": "Sapir", "district": "South", "lat": 30.6050, "lon": 35.1900},

        # --- Coastal District ---
        {"name": "Hadera (Regional)", "district": "Coastal", "lat": 32.4340, "lon": 34.9197},
        {"name": "Haifa (Regional)", "district": "Coastal", "lat": 32.7940, "lon": 34.9896},
        {"name": "Zvulun (Regional)", "district": "Coastal", "lat": 32.9277, "lon": 35.0839},
        {"name": "Krayot", "district": "Coastal", "lat": 32.8427, "lon": 35.0898},

        # --- Judea and Samaria District ---
        {"name": "Binyamin (Regional)", "district": "Judea and Samaria", "lat": 31.7764, "lon": 35.3038},
        {"name": "Givat Zeev", "district": "Judea and Samaria", "lat": 31.8606, "lon": 35.1664},
        {"name": "Matityahu", "district": "Judea and Samaria", "lat": 31.9320, "lon": 35.0290},
        {"name": "Ofra", "district": "Judea and Samaria", "lat": 31.9540, "lon": 35.2710},
        {"name": "Shomron (Regional)", "district": "Judea and Samaria", "lat": 32.1045, "lon": 35.1745},
        {"name": "Jordan Valley", "district": "Judea and Samaria", "lat": 32.0520, "lon": 35.4390},
        {"name": "Shaked", "district": "Judea and Samaria", "lat": 32.5030, "lon": 35.1630},
        {"name": "Karnei Shomron", "district": "Judea and Samaria", "lat": 32.1700, "lon": 35.0970},
        {"name": "Elkana", "district": "Judea and Samaria", "lat": 32.1120, "lon": 35.0340},
        {"name": "Yehuda (Regional)", "district": "Judea and Samaria", "lat": 31.6500, "lon": 35.1200},
        {"name": "Beitar Illit", "district": "Judea and Samaria", "lat": 31.6960, "lon": 35.1070},
        {"name": "Kiryat Arba", "district": "Judea and Samaria", "lat": 31.5360, "lon": 35.1150},
        {"name": "Gush Etzion", "district": "Judea and Samaria", "lat": 31.6440, "lon": 35.1220},

        # --- Jerusalem District ---
        {"name": "Beit Shemesh (Regional)", "district": "Jerusalem", "lat": 31.7470, "lon": 34.9881},
        {"name": "Rama", "district": "Jerusalem", "lat": 31.7300, "lon": 34.9800},
        {"name": "Harim", "district": "Jerusalem", "lat": 31.7350, "lon": 35.0680},
        {"name": "Maoz", "district": "Jerusalem", "lat": 31.8020, "lon": 35.1470},
        {"name": "Nahshon", "district": "Jerusalem", "lat": 31.7820, "lon": 34.9190},
        {"name": "HaEla", "district": "Jerusalem", "lat": 31.6880, "lon": 34.9540},
        {"name": "Jerusalem (Regional)", "district": "Jerusalem", "lat": 31.7683, "lon": 35.2137},
        {"name": "Leom", "district": "Jerusalem", "lat": 31.7810, "lon": 35.2040},
        {"name": "Pisga", "district": "Jerusalem", "lat": 31.8260, "lon": 35.2400},
        {"name": "Egoz", "district": "Jerusalem", "lat": 31.7900, "lon": 35.2350},
        {"name": "Itri", "district": "Jerusalem", "lat": 31.7500, "lon": 35.2100},
        {"name": "Rimon", "district": "Jerusalem", "lat": 31.7940, "lon": 35.2010},

        # --- Central District ---
        {"name": "Ayalon (Regional)", "district": "Central", "lat": 31.9510, "lon": 34.8881},
        {"name": "Modiin", "district": "Central", "lat": 31.9010, "lon": 35.0070},
        {"name": "Shoham", "district": "Central", "lat": 31.9980, "lon": 34.9450},
        {"name": "HaSharon (Regional)", "district": "Central", "lat": 32.1750, "lon": 34.9069},
        {"name": "Mitzpe Sapir", "district": "Central", "lat": 32.2350, "lon": 35.0050},
        {"name": "Netanya (Regional)", "district": "Central", "lat": 32.3215, "lon": 34.8532},
        {"name": "Yakhon", "district": "Central", "lat": 32.3550, "lon": 35.0080},
        {"name": "Kadima", "district": "Central", "lat": 32.2770, "lon": 34.9040},
        {"name": "Petah Tikva (Regional)", "district": "Central", "lat": 32.0840, "lon": 34.8878},
        {"name": "Rosh HaAyin", "district": "Central", "lat": 32.0950, "lon": 34.9560},
        {"name": "Elad", "district": "Central", "lat": 32.0520, "lon": 34.9510},
        {"name": "Rishon LeZion (Regional)", "district": "Central", "lat": 31.9730, "lon": 34.7925},
        {"name": "Rishon LeZion Ind. Zone", "district": "Central", "lat": 31.9860, "lon": 34.7710},
        {"name": "Rehovot (Regional)", "district": "Central", "lat": 31.8928, "lon": 34.8113},
        {"name": "Yavne", "district": "Central", "lat": 31.8770, "lon": 34.7390},
        {"name": "Gedera", "district": "Central", "lat": 31.8130, "lon": 34.7780},

        # --- North District ---
        {"name": "Galilee-Golan (Regional)", "district": "North", "lat": 33.2073, "lon": 35.5695},
        {"name": "Hatzor", "district": "North", "lat": 32.9800, "lon": 35.5520},
        {"name": "Safed", "district": "North", "lat": 32.9640, "lon": 35.4980},
        {"name": "Katzrin", "district": "North", "lat": 32.9920, "lon": 35.6900},
        {"name": "Mas'ade", "district": "North", "lat": 33.2350, "lon": 35.7600},
        {"name": "Bnei Yehuda", "district": "North", "lat": 32.7930, "lon": 35.6830},
        {"name": "Central Galilee (Regional)", "district": "North", "lat": 32.9130, "lon": 35.2960},
        {"name": "Ma'alot", "district": "North", "lat": 33.0120, "lon": 35.2720},
        {"name": "Shefa-'Amr", "district": "North", "lat": 32.8050, "lon": 35.1680},
        {"name": "Misgav-Teradion", "district": "North", "lat": 32.8640, "lon": 35.2530},
        {"name": "Tiberias (Regional)", "district": "North", "lat": 32.7945, "lon": 35.5315},
        {"name": "Tamra", "district": "North", "lat": 32.8530, "lon": 35.1970},
        {"name": "Tzemach", "district": "North", "lat": 32.7040, "lon": 35.5840},
        {"name": "Nazareth", "district": "North", "lat": 32.6990, "lon": 35.3030},
        {"name": "Kadoorie", "district": "North", "lat": 32.7350, "lon": 35.4050},
        {"name": "Tzalmon", "district": "North", "lat": 32.8580, "lon": 35.4220},
        {"name": "Afula (Regional)", "district": "North", "lat": 32.6090, "lon": 35.2890},
        {"name": "Beit She'an", "district": "North", "lat": 32.5000, "lon": 35.4980},
        {"name": "Yokneam", "district": "North", "lat": 32.6590, "lon": 35.1050},
        {"name": "Nof HaGalil (Regional)", "district": "North", "lat": 32.7050, "lon": 35.3240},
        {"name": "Migdal HaEmek", "district": "North", "lat": 32.6680, "lon": 35.2370},
        {"name": "Tziporit", "district": "North", "lat": 32.7600, "lon": 35.2900},

        # --- Airbases ---
        {"name": "Megiddo Airbase - Elad Squadron", "district": "North", "type": "AIRBASE", "lat": 32.5975,
         "lon": 35.2289},
        {"name": "Kedma Airbase - Elad Squadron", "district": "South", "type": "AIRBASE", "lat": 31.6315,
         "lon": 34.7942}
    ]

    print("🚀 Starting Seeding of stations and resources...")
    total_resources = 0

    for s_data in stations_data:
        if "type" in s_data:
            st_type = s_data["type"]
        else:
            # Updated to look for English string
            st_type = "REGIONAL" if "(Regional)" in s_data["name"] else "SUB_STATION"

        station = Station(
            name=s_data["name"],
            district=s_data["district"],
            station_type=st_type,
            latitude=s_data["lat"],
            longitude=s_data["lon"]
        )
        db.session.add(station)
        db.session.flush()

        resources_to_add = []
        if st_type == "REGIONAL":
            resources_to_add = (['SAAR'] * 4) + (['ESHED'] * 2) + (['ROTEM'] * 2)
        elif st_type == "SUB_STATION":
            resources_to_add = (['SAAR'] * 2) + (['ROTEM'] * 1)
        elif st_type == "AIRBASE":
            resources_to_add = ['AIR_TRACTOR'] * 4

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

    db.session.commit()
    print(
        f"\n🎉 Done! Created {len(stations_data)} stations/airbases with a total of {total_resources} resources in Neon DB!")
