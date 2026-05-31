import React, { useState, useEffect } from 'react';
import Map, { Marker, Source, Layer } from 'react-map-gl';
import { io } from 'socket.io-client';
import 'mapbox-gl/dist/mapbox-gl.css';
import './App.css';
import TacticalFireMarker from './components/TacticalFireMarker';
import ReactMarkdown from 'react-markdown';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:5000';

/**
 * Extracts and parses JSON content from a string that may contain markdown code blocks or escaped characters.
 * Takes a string input that might be wrapped in ```json``` blocks and returns the parsed JSON object, or null if parsing fails.
 */
const extractJSON = (str) => {
  if (typeof str !== 'string') return str;
  try {
    let cleanStr = str.replace(/```json/gi, '').replace(/```/gi, '').trim();
    cleanStr = cleanStr.replace(/\\n/g, '\\n');
    return JSON.parse(cleanStr);
  } catch (e) {
    return null;
  }
};

/**
 * Processes raw district summaries from the backend by cleaning and extracting nested JSON structures.
 * Takes an object of district summaries, attempts to parse any JSON-stringified values, and returns a cleaned object with only the district_overview text.
 */
const processDistrictSummaries = (rawSummaries) => {
  const cleanSummaries = {};
  for (const [district, summary] of Object.entries(rawSummaries)) {
    let finalSummary = summary;
    // If summary is a JSON string, attempt to extract the district_overview field
    if (typeof summary === 'string' && summary.trim().startsWith('{')) {
      const parsed = extractJSON(summary);
      if (parsed && parsed.district_overview) {
        finalSummary = parsed.district_overview;
      }
    }
    cleanSummaries[district] = finalSummary;
  }
  return cleanSummaries;
};

/**
 * Main application component that renders a real-time fire monitoring dashboard with an interactive map and live feed sidebar.
 * Manages state for fire events, district summaries, fire stations, and map view, while establishing WebSocket connections for real-time updates.
 */
function App() {
  const [viewState, setViewState] = useState({
    longitude: 34.8516,
    latitude: 31.0461,
    zoom: 7
  });

  const [fires, setFires] = useState([]);
  const [districtSummaries, setDistrictSummaries] = useState({});
  const [focusedFireId, setFocusedFireId] = useState(null);
  const [selectedDistrict, setSelectedDistrict] = useState("All");
  const [stations, setStations] = useState(null);
  const [iconLoaded, setIconLoaded] = useState(false);
  const [isStrategyOpen, setIsStrategyOpen] = useState(true);

  const uniqueDistricts = ["All", ...new Set(fires.map(f => f.district).filter(Boolean))];

  useEffect(() => {
    // Load initial active fires data from backend
    fetch(`${BACKEND_URL}/active-fires`)
      .then(res => res.json())
      .then(data => {
        setFires(Array.isArray(data.fires) ? data.fires : []);
        if (data.summaries) {
          // Process and clean district summaries on initial load
          setDistrictSummaries(processDistrictSummaries(data.summaries));
        }
      })
      .catch(err => console.error("Error loading initial data:", err));

    // Load fire stations data from backend
    fetch(`${BACKEND_URL}/stations`)
      .then(res => res.json())
      .then(data => {
        setStations(data);
        console.log("📍 Stations loaded:", data.features.length);
      })
      .catch(err => console.error("Error loading stations:", err));

    const socket = io(BACKEND_URL);

    // Handle new fire event notifications
    socket.on('new_fire', (fireData) => {
      console.log('🔥 new_fire received:', fireData);
      setFires(prev => {
        const idx = prev.findIndex(f => f.event_id === fireData.event_id);
        // Update existing fire or add new one
        if (idx >= 0) {
          const updated = [...prev];
          updated[idx] = fireData;
          return updated;
        }
        return [...prev, fireData];
      });
    });

    // Handle fire prediction updates
    socket.on('prediction_update', (updateData) => {
      console.log('🛡️ prediction_update received:', updateData);
      setFires(prev => prev.map(fire =>
        fire.event_id === updateData.event_id
          ? {
            ...fire,
            prediction_polygon: updateData.prediction_polygon,
            prediction_summary: updateData.prediction_summary
          }
          : fire
      ));
    });

    // Handle commander updates for district strategy and fire allocations
    socket.on('commander_update', (payload) => {
      console.log(`👨‍✈️ Raw commander update received:`, payload);
      
      let data = payload;

      // Parse string payloads as JSON
      if (typeof payload === 'string') {
        data = extractJSON(payload) || { district_overview: payload };
      }

      // Extract nested district_overview if it's JSON-stringified
      if (data && typeof data.district_overview === 'string' && data.district_overview.trim().startsWith('{')) {
        const parsedInner = extractJSON(data.district_overview);
        if (parsedInner) {
          data = { ...data, ...parsedInner };
        }
      }

      // Update district summaries with clean overview text
      if (data.district_overview && typeof data.district_overview === 'string' && !data.district_overview.trim().startsWith('{')) {
        setDistrictSummaries(prev => ({
          ...prev,
          [data.district_name]: data.district_overview
        }));
      }

      // Update fire tactical summaries based on allocation data
      if (data.fires_allocation && Array.isArray(data.fires_allocation)) {
        setFires(prevFires => prevFires.map(fire => {
          const allocationUpdate = data.fires_allocation.find(a => a.event_id === fire.event_id);
          if (allocationUpdate && allocationUpdate.tactical_summary) {
            return { ...fire, tactical_summary: allocationUpdate.tactical_summary };
          }
          return fire;
        }));
      }
    });

    return () => socket.disconnect();
  }, []);

  /**
   * Handles click events on fire event cards in the sidebar.
   * Focuses the clicked fire and animates the map to zoom to its location.
   */
  const handleCardClick = (fire) => {
    setFocusedFireId(fire.event_id);
    setViewState({
      ...viewState,
      longitude: fire.lon,
      latitude: fire.lat,
      zoom: 12,
      transitionDuration: 1000
    });
  };

  /**
   * Handles click events on fire markers on the map.
   * Prevents event propagation, focuses the fire, zooms to its location, and scrolls the corresponding card into view.
   */
  const handleMarkerClick = (e, fire) => {
    e.originalEvent.stopPropagation();
    setFocusedFireId(fire.event_id);
    setViewState({
      ...viewState,
      longitude: fire.lon,
      latitude: fire.lat,
      zoom: 12,
      transitionDuration: 1000
    });

    // Scroll the corresponding card into view in the sidebar
    const cardElement = document.getElementById(`fire-card-${fire.event_id}`);
    if (cardElement) {
      cardElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  /**
   * Handles the map load event by loading and registering the custom fire station icon image.
   * Once the image is successfully loaded and added to the map, sets the iconLoaded state to true to enable rendering of station layers.
   */
  const onMapLoad = (evt) => {
    const map = evt.target;

    map.loadImage('/fire-station.png', (error, image) => {
      if (error) {
        console.error("❌ Error loading PNG file:", error);
        return;
      }
      if (!map.hasImage('station-icon')) {
        map.addImage('station-icon', image);
      }
      setIconLoaded(true);
    });
  };

  const handleResetDatabase = async () => {
    // חלון אישור קופץ כדי שלא תלחץ בטעות באמצע המצגת
    if (!window.confirm("🚨 Are you sure you want to reset the system and delete all data?")) {
      return;
    }

    try {
      // פנייה לראוט החדש שיצרנו בשרת
      const response = await fetch(`${BACKEND_URL}/api/debug/reset`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });

      const data = await response.json();

      if (response.ok) {
        console.log("🔄 Database initialized successfully:", data.message);
        
        setFires([]); // מרוקן מיד את רשימת השריפות מהמסך ללא צורך ברענון!
        setFocusedFireId(null); // מאפס את הפוקוס במפה
        
        alert("המערכת אותחלה בהצלחה! כל השריפות נמחקו והתחנות נטענו מחדש.");
      } else {
        alert(`שגיאה באיפוס המערכת: ${data.message || 'שגיאה לא ידועה'}`);
      }
    } catch (error) {
      console.error("Error connecting to reset endpoint:", error);
      alert("שגיאה בתקשורת עם השרת - ודא ששרת ה-Flask רץ");
    }
  };

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', direction: 'ltr', backgroundColor: '#000' }}>
      <div className="sidebar-container">
        {/* כותרת ה-Live Feed המקורית והנקייה - ללא פלקסבוקס שיזיז את הטקסט */}
        <div style={{ 
          padding: '20px', 
          borderBottom: '1px solid #333', 
          background: '#1a1a1a', 
          position: 'relative' // קריטי כדי שהכפתור יתמקד לפי הריבוע הזה
        }}>
          <h2 style={{ color: '#e3eeea', margin: 0, fontSize: '1.4rem', direction: 'ltr' }}>
            📡 Live Feed
          </h2>
          
          {/* כפתור איפוס צף - ממוקם אבסולוטית בפינה הימנית ללא שום קשר לכותרת */}
          <button
            onClick={handleResetDatabase}
            title="איפוס סימולציה ומחיקת נתונים"
            style={{
              position: 'absolute',
              right: '20px', 
              top: '50%', 
              transform: 'translateY(-50%)', 
              background: '#27272a', // רקע כהה שמפריד אותו מהכותרת
              color: '#e4e4e7', // טקסט בהיר וקריא
              border: '1px solid #3f3f46', // מסגרת עדינה
              borderRadius: '6px', // פינות מעוגלות מודרניות
              padding: '6px 12px', // הגדלנו מעט את ה-Padding שיהיה שטח לחיצה נוח
              fontSize: '0.75rem',
              fontWeight: 'bold',
              letterSpacing: '0.5px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: '0 2px 4px rgba(0, 0, 0, 0.3)', // צל קליל שיוצר עומק ותחושת לחיצות
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => { 
              e.currentTarget.style.background = '#dc2626'; // נצבע באדום ברור ב-Hover
              e.currentTarget.style.borderColor = '#b91c1c';
              e.currentTarget.style.color = '#fff';
            }}
            onMouseLeave={(e) => { 
              e.currentTarget.style.background = '#27272a'; // חוזר למצב רגיל
              e.currentTarget.style.borderColor = '#3f3f46';
              e.currentTarget.style.color = '#e4e4e7';
            }}
          >
            🔄 RESET
          </button>
        </div>
      
        {uniqueDistricts.length > 1 && (
          <div style={{
            padding: '10px 20px',
            borderBottom: '1px solid #333',
            background: '#121212',
            display: 'flex',
            gap: '8px',
            overflowX: 'auto',
            whiteSpace: 'nowrap'
          }}>
            {uniqueDistricts.map(district => (
              <button
                key={district}
                onClick={() => setSelectedDistrict(district)}
                style={{
                  backgroundColor: selectedDistrict === district ? '#ff4400' : '#2a2a2a',
                  color: selectedDistrict === district ? '#fff' : '#aaa',
                  border: 'none',
                  borderRadius: '20px',
                  padding: '6px 14px',
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  fontWeight: selectedDistrict === district ? 'bold' : 'normal'
                }}
              >
                {district === "All" ? "All" : district}
              </button>
            ))}
          </div>
        )}

        {selectedDistrict !== "All" && districtSummaries[selectedDistrict] && (
          <div style={{ 
            padding: '16px', 
            background: '#1a1d21', 
            borderLeft: '4px solid #ff9900', 
            marginBottom: '10px',
            direction: 'ltr',
            textAlign: 'left'
          }}>
            <div 
              style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
              onClick={() => setIsStrategyOpen(!isStrategyOpen)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '1.2rem' }}></span>
                <h3 style={{ margin: 0, color: '#ff9900', fontSize: '1rem', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  Command Strategy: {selectedDistrict}
                </h3>
              </div>
              <span style={{ color: '#ff9900', fontSize: '1.2rem', fontWeight: 'bold' }}>
                {isStrategyOpen ? '−' : '+'}
              </span>
            </div>
            
            {isStrategyOpen && (
              <div style={{ marginTop: '12px', fontSize: '0.9rem', color: '#d1d5db', lineHeight: '1.6' }} className="markdown-container">
                <ReactMarkdown>{districtSummaries[selectedDistrict]}</ReactMarkdown>
              </div>
            )}
          </div>
        )}

        <div style={{ flex: 1, overflowY: 'auto' }}>
          {(() => {
            const filteredFires = selectedDistrict === "All"
              ? fires
              : fires.filter(f => f.district === selectedDistrict);

            if (fires.length === 0) {
              return <p style={{ color: '#888', padding: '20px', textAlign: 'center' }}>....Waiting for data</p>;
            }
            if (filteredFires.length === 0) {
              return <p style={{ color: '#888', padding: '20px', textAlign: 'center' }}>No active events in this district.</p>;
            }

            return [...filteredFires].reverse().map(fire => (
              <div
                id={`fire-card-${fire.event_id}`}
                key={fire.event_id}
                className={`event-card ${focusedFireId === fire.event_id ? 'focused' : ''}`}
                onClick={() => handleCardClick(fire)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', direction: 'ltr', marginBottom: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <strong style={{ color: '#fff', fontSize: '1.1rem', letterSpacing: '0.5px' }}>
                      🔥 Event {fire.event_id}
                    </strong>
                  </div>
                  <span style={{ color: '#888', fontSize: '0.8rem' }}>
                    {new Date(fire.created_at || Date.now()).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>

                {/* שורת תגיות (Badges) - צבעים לפי רמת סיכון וסוג שטח */}
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '12px', direction: 'ltr' }}>
                  <span style={{
                    background: fire.risk === 'CRITICAL' ? '#dc2626' : fire.risk === 'HIGH' ? '#ea580c' : '#ca8a04',
                    color: '#fff', padding: '3px 10px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 'bold'
                  }}>
                    {fire.risk || "MODERATE"} RISK
                  </span>
                  
                  <span style={{ background: '#1e3a8a', color: '#bfdbfe', padding: '3px 10px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 'bold' }}>
                    📍 {fire.district || "Unknown District"}
                  </span>
                  
                </div>

                

                {/* --- קופסת החיזוי (Forecast) המעודכנת --- */}
                {fire.prediction_summary && (
                  <div style={{ 
                    marginTop: '12px', 
                    padding: '12px 16px', 
                    background: 'rgba(255, 102, 0, 0.05)', 
                    borderLeft: '3px solid #ff6600', 
                    borderRadius: '0 4px 4px 0',
                    direction: 'ltr',
                    textAlign: 'left'
                  }}>
                    <div style={{ color: '#ff6600', fontSize: '0.75rem', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
                      Fire Behavior Forecast
                    </div>
                    <div style={{ fontSize: '0.9rem', color: '#e5e7eb', lineHeight: '1.5' }} className="markdown-container">
                      <ReactMarkdown>{fire.prediction_summary}</ReactMarkdown>
                    </div>
                  </div>
                )}

                {fire.tactical_summary && (
                  <div className="commander-recommendation" style={{ 
                    marginTop: '16px', 
                    padding: '12px 16px', 
                    background: 'rgba(0, 255, 204, 0.05)',
                    borderLeft: '3px solid #00ffcc',
                    borderRadius: '0 4px 4px 0',
                    direction: 'ltr',
                    textAlign: 'left'
                  }}>
                    <div style={{ color: '#00ffcc', fontSize: '0.75rem', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
                      Action Required
                    </div>
                    <div style={{ fontSize: '0.9rem', color: '#e5e7eb', lineHeight: '1.5' }} className="markdown-container">
                      <ReactMarkdown>{fire.tactical_summary}</ReactMarkdown>
                    </div>
                  </div>
                )}

              
              </div>
            ));
          })()}
        </div>
      </div>

      <div style={{ flex: 1, position: 'relative' }}>
        <Map
          {...viewState}
          onMove={evt => setViewState(evt.viewState)}
          onLoad={onMapLoad}
          mapStyle="mapbox://styles/mapbox/dark-v11"
          mapboxAccessToken={MAPBOX_TOKEN}
        >
          {stations && iconLoaded && (
            <Source id="stations-data" type="geojson" data={stations}>
              <Layer
                id="station-icons"
                type="symbol"
                layout={{
                  'icon-image': 'station-icon',
                  'icon-size': 0.038,
                  'icon-allow-overlap': true,
                  'icon-ignore-placement': true
                }}
                paint={{
                  'icon-opacity': 0.9
                }}
              />
              <Layer
                id="station-labels"
                type="symbol"
                minzoom={10}
                layout={{
                  'text-field': ['get', 'name'],
                  'text-size': 11,
                  'text-offset': [0, 1.5],
                  'text-anchor': 'top'
                }}
                paint={{
                  'text-color': '#9eb3bf',
                  'text-halo-color': '#000',
                  'text-halo-width': 1
                }}
              />
            </Source>
          )}

          {fires.map((fire) => (
            <React.Fragment key={fire.event_id}>
              {fire.prediction_polygon && (
                <Source id={`src-${fire.event_id}`} type="geojson" data={fire.prediction_polygon}>
                  <Layer id={`poly-${fire.event_id}`} type="fill" paint={{ 'fill-color': '#ff6600', 'fill-opacity': 0.2 }} />
                  <Layer id={`outline-${fire.event_id}`} type="line" paint={{ 'line-color': '#ff4400', 'line-width': 2, 'line-dasharray': [2, 2] }} />
                </Source>
              )}
              <Marker
                latitude={fire.lat}
                longitude={fire.lon}
                anchor="center"
                onClick={(e) => handleMarkerClick(e, fire)}
                style={{ cursor: 'pointer' }}
              >
                <TacticalFireMarker intensity={fire.intensity} />
              </Marker>
            </React.Fragment>
          ))}
        </Map>
      </div>
    </div>
  );
}

export default App;