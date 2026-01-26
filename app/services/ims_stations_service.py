import csv
import math
import os

CSV_PATH = "stations.csv" 
stations_cache = []

def load_stations():
    """טוען את רשימת התחנות מהקובץ הנקי (StationId, StationName, Lat, Lon)"""
    global stations_cache
    if stations_cache: return
    
    if not os.path.exists(CSV_PATH):
        print(f"⚠️ Warning: {CSV_PATH} not found. Using default station (Bet Dagan).")
        return

    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        
        # דילוג על שורת הכותרת
        headers = next(reader, None)
        
        for row in reader:
            # בדיקה שיש לנו את 4 העמודות הנחוצות
            if len(row) < 4: continue
            
            try:
                # המבנה של הקובץ הנקי שיצרנו:
                # 0: StationId
                # 1: StationName
                # 2: Lat
                # 3: Lon
                
                s_id = int(row[0]) 
                name = row[1]
                lat = float(row[2])
                lon = float(row[3])
                
                stations_cache.append({
                    "id": s_id, 
                    "name": name, 
                    "lat": lat, 
                    "lon": lon
                })
            except ValueError:
                continue
                
    print(f"✅ Loaded {len(stations_cache)} stations from CSV.")

def get_nearest_station(lat, lon):
    """מוצא את התחנה הקרובה ביותר לנ.צ. של השריפה"""
    load_stations()
    
    # אם עדיין אין תחנות (קובץ ריק או תקול), ברירת מחדל בית דגן
    if not stations_cache:
        return {"id": 24, "name": "Bet Dagan Default", "lat": 32.0, "lon": 34.8}

    nearest = None
    min_dist = float('inf')

    for station in stations_cache:
        # חישוב מרחק אוקלידי פשוט (שורש סכום הריבועים)
        dist = math.sqrt((station['lat'] - lat)**2 + (station['lon'] - lon)**2)
        
        if dist < min_dist:
            min_dist = dist
            nearest = station
            
    return nearest