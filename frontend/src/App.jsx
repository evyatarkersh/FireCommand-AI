import { useState, useEffect } from 'react';
import Map, { Marker } from 'react-map-gl';
import { io } from 'socket.io-client'; // ייבוא ספריית האוזן
import 'mapbox-gl/dist/mapbox-gl.css';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;
// כרגע נכוון לשרת הלוקאלי שלך בפורט 5000. כשנעלה לרנדר נשנה את זה.
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:5000';

function App() {
  const [viewState, setViewState] = useState({
    longitude: 34.8516,
    latitude: 31.0461,
    zoom: 7
  });

  // משתנה סטייט חדש: מערך שישמור את כל השריפות שהשרת דוחף לנו
  const [fires, setFires] = useState([]);

  useEffect(() => {
  // שלב א': הבאת השריפות הקיימות מה-DB (הצילום)
  fetch(`${BACKEND_URL}/active-fires`)
    .then(res => res.json())
    .then(data => {
      console.log("📥 נטענו שריפות קיימות מה-DB:", data);
      setFires(data); 
    })
    .catch(err => console.error("Error fetching fires:", err));

  // שלב ב': חיבור ה-Socket לעדכונים החל מרגע זה (הזרם)
  const socket = io(BACKEND_URL);
  
  socket.on('new_fire', (fireData) => {
    console.log("🔥 התקבלה שריפה חדשה בזמן אמת:", fireData);
    setFires(prev => [...prev, fireData]);
  });

  return () => socket.disconnect();
}, []);

  return (
    <div style={{ width: '100vw', height: '100vh', margin: 0 }}>
      <Map
        {...viewState}
        onMove={evt => setViewState(evt.viewState)}
        mapStyle="mapbox://styles/mapbox/dark-v11"
        mapboxAccessToken={MAPBOX_TOKEN}
      >
        {/* לולאה שעוברת על כל השריפות ומציירת סמן אדום במפה */}
        {fires.map((fire, index) => (
          <Marker
            key={index}
            longitude={fire.lon}
            latitude={fire.lat}
            anchor="center" // ממקם את הסמן בדיוק על הנקודה
          >
            {/* כאן אנחנו יוצרים את הסמן המבצעי שלנו */}
            <div style={{
              fontSize: '24px',
              background: 'rgba(255, 69, 0, 0.2)', // עיגול זוהר סביב הלהבה
              borderRadius: '50%',
              padding: '5px',
              animation: 'pulse 1.5s infinite' // אפשר להוסיף אפקט פעימה
            }}>
              🔥 {/* אתה יכול להשתמש באמוג'י, או בקובץ תמונה אמיתי (SVG) של להבה */}
            </div>
          </Marker>
        ))}
      </Map>
    </div>
  );
}

export default App;