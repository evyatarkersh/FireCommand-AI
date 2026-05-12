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
  // הסטייט הזה שומר עכשיו רק את משפט האסטרטגיה הכללי של כל מחוז
  const [districtSummaries, setDistrictSummaries] = useState({});
  const [focusedFireId, setFocusedFireId] = useState(null);
  const [selectedDistrict, setSelectedDistrict] = useState("All");
  const [stations, setStations] = useState(null); // הסטייט החדש לתחנות

  const uniqueDistricts = ["All", ...new Set(fires.map(f => f.district).filter(Boolean))];

  useEffect(() => {
    fetch(`${BACKEND_URL}/active-fires`)
      .then(res => res.json())
      .then(data => {
        setFires(Array.isArray(data.fires) ? data.fires : []);
        if (data.summaries) {
          setDistrictSummaries(data.summaries);
        }
      })
      .catch(err => console.error("Error loading initial data:", err));


    // 2. משיכת התחנות מהראוט החדש שיצרנו בשרת
    fetch(`${BACKEND_URL}/stations`)
      .then(res => res.json())
      .then(data => {
        setStations(data);
        console.log("📍 Stations loaded:", data.features.length);
      })
      .catch(err => console.error("Error loading stations:", err));

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

    // --- העדכון החדש שלנו: טיפול ב-JSON החכם ---
    socket.on('commander_update', (data) => {
      console.log(`👨‍✈️ התקבל עדכון מפקד חכם למחוז ${data.district_name}`, data);

      // 1. מעדכנים את סיכום המחוז הכללי בסטייט של המחוזות
      if (data.district_overview) {
        setDistrictSummaries(prev => ({
          ...prev,
          [data.district_name]: data.district_overview
        }));
      }

      // 2. מעדכנים את השיבוץ הפרטני לכל שריפה בתוך מערך השריפות
      if (data.fires_allocation && Array.isArray(data.fires_allocation)) {
        setFires(prevFires => prevFires.map(fire => {
          // בודקים אם לשריפה הזו יש עדכון במחזור הנוכחי
          const allocationUpdate = data.fires_allocation.find(a => a.event_id === fire.event_id);

          if (allocationUpdate) {
            return {
              ...fire,
              tactical_summary: allocationUpdate.tactical_summary
            };
          }

          // אם אין עדכון לשריפה הזו, אנחנו מחזירים אותה כמו שהיא (ההמלצה הישנה נשמרת!)
          return fire;
        }));
      }
    });

    return () => socket.disconnect();
  }, []);

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

    const cardElement = document.getElementById(`fire-card-${fire.event_id}`);
    if (cardElement) {
      cardElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', direction: 'ltr', backgroundColor: '#000' }}>

      {/* פאנל צדדי (Sidebar) */}
      <div className="sidebar-container">
        <div style={{ padding: '20px', borderBottom: '1px solid #333', background: '#1a1a1a' }}>
          <h2 style={{ color: '#e3eeea', margin: 0, fontSize: '1.4rem', direction: 'ltr' }}>📡 Live Feed</h2>
        </div>

        {/* שורת סינון מחוזות */}
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

        {/* --- באנר אסטרטגיה מחוזי (מופיע רק כשבוחרים מחוז) --- */}
        {selectedDistrict !== "All" && districtSummaries[selectedDistrict] && (
          <div style={{ padding: '15px', background: '#2a1a12', borderBottom: '2px solid #ff4400' }}>
            <h3 style={{ margin: '0 0 8px 0', color: '#ffaa00', fontSize: '1.05rem' }}>
              👨‍✈️ Strategy: {selectedDistrict}
            </h3>
            <p style={{ margin: 0, fontSize: '0.9rem', color: '#ddd', lineHeight: '1.4' }}>
              {districtSummaries[selectedDistrict]}
            </p>
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
                <div style={{ display: 'flex', justifyContent: 'space-between', direction: 'ltr' }}>
                  <strong style={{ color: '#fff' }}>🔥 Event #{fire.event_id}</strong>
                  <span style={{ color: '#888', fontSize: '0.8rem' }}>
                    {new Date(fire.last_update || Date.now()).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>

                <div className="ai-summary" style={{ direction: 'ltr', textAlign: 'left', marginTop: '10px' }}>
                  <ReactMarkdown>
                    {fire.prediction_summary || "Computing Prediction..."}
                  </ReactMarkdown>
                </div>

                {/* --- המלצת שיבוץ טקטית לשריפה --- */}
                {fire.tactical_summary && (
                  <div className="commander-recommendation" style={{
                    marginTop: '12px',
                    padding: '10px',
                    background: '#162424',
                    borderRadius: '6px',
                    borderLeft: '4px solid #00ffcc'
                  }}>
                    <div style={{ fontSize: '0.95rem', color: '#fff', lineHeight: '1.4', direction: 'ltr', textAlign: 'left' }}>
                      {fire.tactical_summary}
                    </div>
                  </div>
                )}

                <div style={{ marginTop: '12px', direction: 'rtl' }}>
                  <span className="tag" style={{ fontSize: '1rem', background: '#333' }}>Intensity: {fire.intensity}</span>
                  {fire.prediction_polygon && <span className="tag" style={{ background: '#224422', color: '#44ff44' }}>Active Prediction 🛡️</span>}
                </div>
              </div>
            ));
          })()}
        </div>
      </div>

      {/* אזור המפה */}
      <div style={{ flex: 1, position: 'relative' }}>
        <Map
          {...viewState}
          onMove={evt => setViewState(evt.viewState)}
          mapStyle="mapbox://styles/mapbox/dark-v11"
          mapboxAccessToken={MAPBOX_TOKEN}
        >
          {/* ---> כאן מדביקים את שכבת התחנות <--- */}
          {stations && (
            <Source id="stations-data" type="geojson" data={stations}>
              <Layer
                id="station-icons"
                type="symbol"
                layout={{
                  'text-field': '🚒', // פשוט מחליף לאמוג'י של כבאית (אפשר גם 🛡️ או 🏢)
                  'text-size': 16,    // גודל האייקון
                  'text-allow-overlap': true, // מאפשר להם להופיע תמיד
                  'text-ignore-placement': true
                }}
                paint={{
                  // אמוג'י לא צריכים צבע, אבל אפשר להוסיף להם הילה כדי שיבלטו מהרקע
                  'text-halo-color': '#111', 
                  'text-halo-width': 2
                }}
              />
              <Layer
                id="station-labels"
                type="symbol"
                minzoom={9}
                layout={{
                  'text-field': ['get', 'name'],
                  'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold'],
                  'text-offset': [0, 1.2],
                  'text-anchor': 'top',
                  'text-size': 11,
                  'text-allow-overlap': false
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