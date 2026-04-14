import { useState } from 'react';
import Map from 'react-map-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;

function App() {
  const [viewState, setViewState] = useState({
    longitude: 34.8516,
    latitude: 31.0461,
    zoom: 7
  });

  return (
    <div style={{ width: '100vw', height: '100vh', margin: 0 }}>
      <Map
        {...viewState}
        onMove={evt => setViewState(evt.viewState)}
        mapStyle="mapbox://styles/mapbox/dark-v11"
        mapboxAccessToken={MAPBOX_TOKEN}
      />
    </div>
  );
}

export default App;