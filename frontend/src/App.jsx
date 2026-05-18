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
  const [districtSummaries, setDistrictSummaries] = useState({});
  const [focusedFireId, setFocusedFireId] = useState(null);
  const [selectedDistrict, setSelectedDistrict] = useState("All");
  const [stations, setStations] = useState(null);
  const [iconLoaded, setIconLoaded] = useState(false);
  const [isStrategyOpen, setIsStrategyOpen] = useState(true);

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

    // --- העדכון: טיפול ב-JSON החכם והמרתו ---
    socket.on('commander_update', (payload) => {
      console.log(`👨‍✈️ Raw commander update received:`, payload);
      
      let data = payload;

      // אם השרת שלח לנו את ה-JSON בתור מחרוזת טקסט, נמיר אותו לאובייקט
      if (typeof payload === 'string') {
        try {
          data = JSON.parse(payload);
        } catch (e) {
          console.error("❌ Failed to parse LLM JSON:", e);
          return; // עוצרים אם זה לא JSON תקין
        }
      }

      if (data.district_overview) {
        setDistrictSummaries(prev => ({
          ...prev,
          [data.district_name]: data.district_overview
        }));
      }

      if (data.fires_allocation && Array.isArray(data.fires_allocation)) {
        setFires(prevFires => prevFires.map(fire => {
          const allocationUpdate = data.fires_allocation.find(a => a.event_id === fire.event_id);
          return allocationUpdate ? { ...fire, tactical_summary: allocationUpdate.tactical_summary } : fire;
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

  const onMapLoad = (evt) => {
    const map = evt.target;

    map.loadImage('/fire-station.png', (error, image) => {
      if (error) {
        console.error("❌ שגיאה בטעינת קובץ ה-PNG. ודא שהוא בתיקיית public ושמו מדויק:", error);
        return;
      }
      if (!map.hasImage('station-icon')) {
        map.addImage('station-icon', image);
      }
      setIconLoaded(true);
    });
  };

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', direction: 'ltr', backgroundColor: '#000' }}>

      <div className="sidebar-container">
        <div style={{ padding: '20px', borderBottom: '1px solid #333', background: '#1a1a1a' }}>
          <h2 style={{ color: '#e3eeea', margin: 0, fontSize: '1.4rem', direction: 'ltr' }}>📡 Live Feed</h2>
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

        {/* --- באנר אסטרטגיה מחוזי (מתקפל!) --- */}
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
                <span style={{ fontSize: '1.2rem' }}>🎖️</span>
                <h3 style={{ margin: 0, color: '#ff9900', fontSize: '1rem', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  Command Strategy: {selectedDistrict}
                </h3>
              </div>
              <span style={{ color: '#ff9900', fontSize: '1.2rem', fontWeight: 'bold' }}>
                {isStrategyOpen ? '−' : '+'}
              </span>
            </div>
            
            {/* התוכן יוצג רק אם הבאנר פתוח */}
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
                <div style={{ display: 'flex', justifyContent: 'space-between', direction: 'ltr' }}>
                  <strong style={{ color: '#fff' }}>🔥 Event #{fire.event_id}</strong>
                  <span style={{ color: '#888', fontSize: '0.8rem' }}>
                    {new Date(fire.created_at || Date.now()).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>

                <div className="ai-summary" style={{ 
                  direction: 'ltr', 
                  textAlign: 'left', 
                  marginTop: '12px', 
                  color: '#9ca3af', 
                  fontSize: '0.9rem', 
                  lineHeight: '1.6' 
                }}>
                  <ReactMarkdown>
                    {fire.prediction_summary || "Computing Prediction..."}
                  </ReactMarkdown>
                </div>

                {/* --- הושארה רק קופסת שיבוץ אחת! --- */}
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

                <div style={{ marginTop: '12px', direction: 'rtl' }}>
                  <span className="tag" style={{ fontSize: '1rem', background: '#333' }}>Intensity: {fire.intensity}</span>
                  {fire.prediction_polygon && <span className="tag" style={{ background: '#224422', color: '#44ff44' }}>Active Prediction 🛡️</span>}
                </div>
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