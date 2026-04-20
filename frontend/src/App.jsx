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

  useEffect(() => {
    fetch(`${BACKEND_URL}/active-fires`)
      .then(res => res.json())
      .then(data => setFires(Array.isArray(data) ? data : []))
      .catch(err => console.error("Error:", err));

    const socket = io(BACKEND_URL);

    socket.on('new_fire', (fireData) => {
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

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', direction: 'ltr', backgroundColor: '#000' }}>

      {/* 1. פאנל צדדי (Sidebar) */}
      <div className="sidebar-container">
        <div style={{ padding: '20px', borderBottom: '1px solid #333', background: '#1a1a1a' }}>
          <h2 style={{ color: '#ff4400', margin: 0, fontSize: '1.4rem' }}>📡 Live Feed</h2>
        </div>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          {fires.length === 0 ? (
            <p style={{ color: '#888', padding: '20px', textAlign: 'center' }}>ממתין לנתונים...</p>
          ) : (
            [...fires].reverse().map(fire => (
              <div key={fire.event_id} className="event-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', direction: 'rtl' }}>
                  <strong style={{ color: '#fff' }}>🔥 אירוע #{fire.event_id}</strong>
                  <span style={{ color: '#888', fontSize: '0.8rem' }}>
                    {new Date().toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>

                {/* סיכום חיזוי מעוצב */}
                <div className="ai-summary">
                  <ReactMarkdown>
                    {fire.prediction_summary || "מחשב תחזית AI..."}
                  </ReactMarkdown>
                </div>

                {/* המלצת מפקד מעוצבת */}
                {districtSummaries[fire.district] && (
                  <div className="commander-recommendation">
                    <strong style={{ color: '#00ff0d', fontSize: '0.9rem', display: 'block', marginBottom: '5px' }}>
                      👨‍✈️ הנחיית אופטימיזציה מחוזית:
                    </strong>
                    <div style={{ fontSize: '0.95rem', color: '#fff', lineHeight: '1.4' }}>
                      <ReactMarkdown>
                        {districtSummaries[fire.district]}
                      </ReactMarkdown>
                    </div>
                  </div>
                )}

                <div style={{ marginTop: '10px', direction: 'rtl' }}>
                  <span className="tag">עוצמה: {fire.intensity}</span>
                  {fire.prediction_polygon && <span className="tag" style={{ color: '#44ff44' }}>🛡️ חיזוי פעיל</span>}
                </div>
              </div>
            ))
          )}
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
              <Marker latitude={fire.lat} longitude={fire.lon} anchor="center">
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