// src/components/TacticalFireMarker.jsx
import React from 'react';
import './TacticalFireMarker.css';

const TacticalFireMarker = ({ intensity = 100 }) => {
  // חישוב גודל האימוג'י לפי העוצמה (ככל שהשריפה חזקה, האימוג'י גדול יותר)
  const baseSize = 18; 
  const dynamicSize = Math.max(18, baseSize * (intensity / 100)); 

  return (
    <div className="fire-emoji-container">
      {/* הטבעת הפועמת (המכ"ם) שמאחורי האש */}
      <div className="pulse-ring"></div>
      
      {/* האימוג'י עצמו במרכז */}
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