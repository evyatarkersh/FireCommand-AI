// src/components/TacticalFireMarker.jsx
import React from 'react';
import './TacticalFireMarker.css';

/**
 * A tactical fire marker component that displays an animated fire emoji with a pulsing radar effect. The component accepts an intensity prop (0-100) that dynamically scales the fire emoji size, with higher intensity values resulting in larger fire icons on the map.
 */
const TacticalFireMarker = ({ intensity = 100 }) => {
  // Calculate emoji size based on intensity (higher intensity = larger emoji)
  const baseSize = 18;
  const dynamicSize = Math.max(18, baseSize * (intensity / 100)); 

  return (
    <div className="fire-emoji-container">
      {/* Pulsing ring (radar effect) behind the fire */}
      <div className="pulse-ring"></div>
      
      {/* The emoji itself in the center */}
      <span
        className="fire-emoji" 
        style={{ fontSize: `${dynamicSize}px` }}
      >
        🔥
      </span>
    </div>
  );
};

export default TacticalFireMarker;