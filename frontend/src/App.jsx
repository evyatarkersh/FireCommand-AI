import React, { useState, useEffect } from 'react';
import Map, { Marker, Source, Layer } from 'react-map-gl';
import { io } from 'socket.io-client';
import 'mapbox-gl/dist/mapbox-gl.css';
import './App.css';
import TacticalFireMarker from './components/TacticalFireMarker';
import ReactMarkdown from 'react-markdown';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:5000';

function App() {
  const [viewState, setViewState] = useState({
    longitude: 34.8516,
    latitude: 31.0461,
    zoom: 7
  });

  const [fires, setFires] = useState([]);
  // הסטייט של המלצות המפקד - עבר לתוך הפונקציה
  const [districtSummaries, setDistrictSummaries] = useState({});
  // שומר את ה-ID של האירוע עליו המפקד מסתכל כרגע
  const [focusedFireId, setFocusedFireId] = useState(null);
  const [selectedDistrict, setSelectedDistrict] = useState("All");

  const uniqueDistricts = ["All", ...new Set(fires.map(f => f.district).filter(Boolean))];

  useEffect(() => {
    fetch(`${BACKEND_URL}/active-fires`)
      .then(res => res.json())
      .then(data => {
        // עדכון רשימת השריפות
        setFires(Array.isArray(data.fires) ? data.fires : []);
        
        // עדכון סיכומי המחוזות מהדאטה-בייס כדי שלא ייעלמו ברענון
        if (data.summaries) {
          setDistrictSummaries(data.summaries);
        }
      })
      .catch(err => console.error("Error loading initial data:", err));

    const socket = io(BACKEND_URL);

    socket.on('new_fire', (fireData) => {
      console.log('🔥 new_fire received:', fireData);
      setFires(prev => {
        const idx = prev.findIndex(f => f.event_id === fireData.event_id);
        if (idx >= 0) {
          const updated = [...prev];
          updated[idx] = fireData;
          return updated;
        }
        return [...prev, fireData];
      });
    });

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

    // האזנה לעדכוני מפקד (Commander Agent)
    socket.on('commander_update', (data) => {
      console.log(`👨‍✈️ התקבל עדכון מפקד למחוז ${data.district}`);
      setDistrictSummaries(prev => ({
        ...prev,
        [data.district]: data.summary
      }));
    });

    return () => socket.disconnect();
  }, []);

  // פונקציה כשלוחצים על כרטיס בפיד
  const handleCardClick = (fire) => {
    setFocusedFireId(fire.event_id);
    setViewState({
      ...viewState,
      longitude: fire.lon,
      latitude: fire.lat,
      zoom: 12, // זום קרוב
      transitionDuration: 1000 // אנימציית טיסה חלקה של שנייה
    });
  };

  // פונקציה כשלוחצים על מרקר במפה
  const handleMarkerClick = (e, fire) => {
    e.originalEvent.stopPropagation(); // מונע מהלחיצה לעבור למפה עצמה
    setFocusedFireId(fire.event_id);

    // מטיס את המפה
    setViewState({
      ...viewState,
      longitude: fire.lon,
      latitude: fire.lat,
      zoom: 12,
      transitionDuration: 1000
    });

    // גולל את הפיד בצד ישר לכרטיס המתאים!
    const cardElement = document.getElementById(`fire-card-${fire.event_id}`);
    if (cardElement) {
      cardElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', direction: 'ltr', backgroundColor: '#000' }}>

      {/* 1. פאנל צדדי (Sidebar) */}
      <div className="sidebar-container">
        <div style={{ padding: '20px', borderBottom: '1px solid #333', background: '#1a1a1a' }}>
          <h2 style={{ color: '#e3eeea', margin: 0, fontSize: '1.4rem', direction: 'ltr' }}>📡 Live Feed</h2>
        </div>

        {/* שורת סינון מחוזות (District Filter) */}
        {uniqueDistricts.length > 1 && (
          <div style={{
            padding: '10px 20px',
            borderBottom: '1px solid #333',
            background: '#121212',
            display: 'flex',
            gap: '8px',
            overflowX: 'auto', // מאפשר גלילה אופקית אם יש הרבה מחוזות
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


        <div style={{ flex: 1, overflowY: 'auto' }}>
          {(() => {
            // 1. קודם כל מסננים את השריפות לפי המחוז שנבחר
            const filteredFires = selectedDistrict === "All"
              ? fires
              : fires.filter(f => f.district === selectedDistrict);

            // 2. בדיקות מצב ריק
            if (fires.length === 0) {
              return <p style={{ color: '#888', padding: '20px', textAlign: 'center' }}>....Waiting for data</p>;
            }
            if (filteredFires.length === 0) {
              return <p style={{ color: '#888', padding: '20px', textAlign: 'center' }}>No active events in this district.</p>;
            }

            // 3. מרנדרים רק את השריפות המסוננות
            return [...filteredFires].reverse().map(fire => (
              <div
                id={`fire-card-${fire.event_id}`} /* חשוב כדי שהגלילה תדע לאן ללכת */
                key={fire.event_id}
                className={`event-card ${focusedFireId === fire.event_id ? 'focused' : ''}`}
                onClick={() => handleCardClick(fire)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', direction: 'ltr' }}>
                  <strong style={{ color: '#fff' }}>🔥 Event #{fire.event_id}</strong>
                  <span style={{ color: '#888', fontSize: '0.8rem' }}>
                    {new Date().toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>

                {/* סיכום חיזוי מעוצב - שינוי עדין ליישור */}
                <div className="ai-summary" style={{ direction: 'ltr', textAlign: 'left' }}>
                  <ReactMarkdown>
                    {fire.prediction_summary || "Computing Prediction and Recommendation"}
                  </ReactMarkdown>
                </div>

                {/* המלצת מפקד - שינוי עדין ליישור הטקסט הפנימי בלבד */}
                {districtSummaries[fire.district] && (
                  <div className="commander-recommendation">
                    <div style={{ fontSize: '0.95rem', color: '#fff', lineHeight: '1.4', direction: 'ltr', textAlign: 'left' }}>
                      <ReactMarkdown>
                        {districtSummaries[fire.district]}
                      </ReactMarkdown>
                    </div>
                  </div>
                )}

                <div style={{ marginTop: '10px', direction: 'rtl' }}>
                  <span className="tag" style={{ fontSize: '1rem' }}>Intensity: {fire.intensity}</span>
                  {fire.prediction_polygon && <span className="tag" style={{ color: '#44ff44' }}>Active Prediction 🛡️</span>}
                </div>
              </div>
            ));
          })()}
        </div>
      </div>

      {/* 2. אזור המפה */}
      <div style={{ flex: 1, position: 'relative' }}>
        <Map
          {...viewState}
          onMove={evt => setViewState(evt.viewState)}
          mapStyle="mapbox://styles/mapbox/dark-v11"
          mapboxAccessToken={MAPBOX_TOKEN}
        >
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