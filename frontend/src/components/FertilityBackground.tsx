import React from 'react';

/**
 * FertilityBackground
 * Implements the soft, elegant, premium healthcare AI aesthetic matching
 * the reference image with flowing coral-pink wave ribbons, embryo illustration
 * in a circular aura, delicate molecular structures, and soft radial glows.
 *
 * Full-screen 16:9 responsive presentation with pointer-events-none and z-0
 * to ensure clinical dashboard readability and complete click-through functionality.
 */
export const FertilityBackground: React.FC = () => {
  return (
    <div
      aria-hidden="true"
      className="fixed inset-0 pointer-events-none select-none overflow-hidden z-0"
    >
      {/* 1. Underlying warm off-white and soft blush-pink gradient */}
      <div className="absolute inset-0 bg-gradient-to-b from-[#FFFDFD] via-[#FFF9F7] via-50% to-[#FFF0ED]" />

      {/* 2. Full-screen 16:9 High-Fidelity Reference Backdrop */}
      <div
        className="absolute inset-0 bg-cover bg-center bg-no-repeat opacity-95 transition-opacity duration-300"
        style={{
          backgroundImage: `url('/fertility-bg.png')`,
          backgroundAttachment: 'fixed',
        }}
      />

      {/* 3. Ambient layered radial gradient glows for depth & cohesion */}
      {/* Top right warmth */}
      <div className="absolute -top-24 right-0 w-[36rem] h-[36rem] rounded-full bg-radial from-[#F5B8B1]/20 via-[#FFF0ED]/30 to-transparent blur-3xl" />
      {/* Bottom left coral glow around embryo area */}
      <div className="absolute -bottom-28 -left-20 w-[42rem] h-[42rem] rounded-full bg-radial from-[#F5B8B1]/30 via-[#FCE4E0]/25 to-transparent blur-3xl" />
      {/* Bottom right wave sweep warmth */}
      <div className="absolute -bottom-24 right-0 w-[38rem] h-[38rem] rounded-full bg-radial from-[#FBC4AB]/25 via-[#FFF0ED]/20 to-transparent blur-3xl" />

      {/* 4. Center softening overlay: keeps the central clinical dashboard crystal-clear and readable */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_rgba(255,255,255,0.78)_0%,_rgba(255,255,255,0.45)_55%,_transparent_100%)]" />

      {/* 5. Scalable High-Res Vector Overlay for Ultra-Crisp Sharpness (16:9 Aspect Ratio) */}
      <svg
        className="absolute inset-0 w-full h-full opacity-65"
        viewBox="0 0 1920 1080"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          {/* Node 3D Spherical Radial Gradient */}
          <radialGradient id="nodeGradient" cx="35%" cy="35%" r="65%">
            <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.9" />
            <stop offset="35%" stopColor="#F5B8B1" stopOpacity="0.85" />
            <stop offset="75%" stopColor="#F08080" stopOpacity="0.75" />
            <stop offset="100%" stopColor="#D96666" stopOpacity="0.7" />
          </radialGradient>

          {/* Soft Wave Stroke Gradient */}
          <linearGradient id="waveStroke" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#F5B8B1" stopOpacity="0.5" />
            <stop offset="50%" stopColor="#FFF0ED" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#F5B8B1" stopOpacity="0.45" />
          </linearGradient>

          {/* Embryo Silhouette Radial Glow */}
          <radialGradient id="embryoGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#F4978E" stopOpacity="0.35" />
            <stop offset="60%" stopColor="#FBC4AB" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#FFF0ED" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Molecular Network: Top-Right Cluster */}
        <g id="molecules-top-right" stroke="#F5B8B1" strokeWidth="1.5" strokeOpacity="0.75">
          <line x1="1480" y1="52" x2="1538" y2="28" />
          <line x1="1538" y1="28" x2="1605" y2="72" />
          <line x1="1480" y1="52" x2="1498" y2="118" />
          <line x1="1498" y1="118" x2="1452" y2="158" />
          <line x1="1605" y1="72" x2="1590" y2="140" />
          <line x1="1590" y1="140" x2="1638" y2="182" />
          <line x1="1605" y1="72" x2="1685" y2="40" />

          {/* Spherical Nodes with 3D Gloss */}
          <circle cx="1538" cy="28" r="13" fill="url(#nodeGradient)" stroke="none" />
          <circle cx="1605" cy="72" r="10" fill="url(#nodeGradient)" stroke="none" />
          <circle cx="1480" cy="52" r="8.5" fill="url(#nodeGradient)" stroke="none" />
          <circle cx="1498" cy="118" r="8" fill="url(#nodeGradient)" stroke="none" />
          <circle cx="1452" cy="158" r="7" fill="url(#nodeGradient)" stroke="none" />
          <circle cx="1590" cy="140" r="7.5" fill="url(#nodeGradient)" stroke="none" />
          <circle cx="1638" cy="182" r="6" fill="url(#nodeGradient)" stroke="none" />
          <circle cx="1685" cy="158" r="6.5" fill="url(#nodeGradient)" stroke="none" />
        </g>

        {/* Molecular Network: Bottom-Left (near embryo) */}
        <g id="molecules-bottom-left" stroke="#F5B8B1" strokeWidth="1.5" strokeOpacity="0.7">
          <line x1="380" y1="840" x2="435" y2="805" />
          <line x1="435" y1="805" x2="482" y2="848" />
          <line x1="380" y1="840" x2="405" y2="905" />
          <line x1="405" y1="905" x2="465" y2="938" />
          <line x1="465" y1="938" x2="482" y2="848" />
          <line x1="482" y1="848" x2="540" y2="868" />
          <line x1="465" y1="938" x2="520" y2="980" />

          <circle cx="380" cy="840" r="8" fill="url(#nodeGradient)" stroke="none" />
          <circle cx="435" cy="805" r="9" fill="url(#nodeGradient)" stroke="none" />
          <circle cx="482" cy="848" r="8.5" fill="url(#nodeGradient)" stroke="none" />
          <circle cx="405" cy="905" r="8" fill="url(#nodeGradient)" stroke="none" />
          <circle cx="465" cy="938" r="9.5" fill="url(#nodeGradient)" stroke="none" />
          <circle cx="540" cy="868" r="6.5" fill="url(#nodeGradient)" stroke="none" />
          <circle cx="520" cy="980" r="7" fill="url(#nodeGradient)" stroke="none" />
        </g>

        {/* Molecular Network: Mid-Right Border */}
        <g id="molecules-right-edge" stroke="#F5B8B1" strokeWidth="1.5" strokeOpacity="0.7">
          <line x1="1720" y1="605" x2="1775" y2="635" />
          <line x1="1775" y1="635" x2="1835" y2="595" />
          <line x1="1835" y1="595" x2="1855" y2="538" />
          <line x1="1775" y1="635" x2="1778" y2="702" />

          <circle cx="1720" cy="605" r="9" fill="url(#nodeGradient)" stroke="none" />
          <circle cx="1775" cy="635" r="8.5" fill="url(#nodeGradient)" stroke="none" />
          <circle cx="1835" cy="595" r="7.5" fill="url(#nodeGradient)" stroke="none" />
          <circle cx="1855" cy="538" r="10" fill="url(#nodeGradient)" stroke="none" />
          <circle cx="1778" cy="702" r="6" fill="url(#nodeGradient)" stroke="none" />
        </g>

        {/* Floating Soft Ambient Micro-Nodes */}
        <circle cx="230" cy="430" r="8.5" fill="#F5B8B1" fillOpacity="0.45" />
        <circle cx="218" cy="510" r="4.5" fill="#F5B8B1" fillOpacity="0.35" />
        <circle cx="550" cy="670" r="7" fill="#F5B8B1" fillOpacity="0.38" />
        <circle cx="680" cy="775" r="8" fill="#F5B8B1" fillOpacity="0.3" />
        <circle cx="1060" cy="780" r="9.5" fill="#F5B8B1" fillOpacity="0.28" />
        <circle cx="1710" cy="740" r="5" fill="#F5B8B1" fillOpacity="0.35" />
        <circle cx="1780" cy="265" r="5" fill="#F5B8B1" fillOpacity="0.32" />
        <circle cx="1035" cy="175" r="4.5" fill="#F5B8B1" fillOpacity="0.3" />

        {/* Bottom-Left Concentric Embryo Capsule Overlay */}
        <g id="embryo-capsule" transform="translate(180, 810)">
          {/* Subtle Outer Concentric Orbit Rings */}
          <circle cx="0" cy="0" r="120" stroke="#F5B8B1" strokeWidth="1.2" strokeOpacity="0.35" fill="none" />
          <circle cx="0" cy="0" r="102" stroke="#FFF0ED" strokeWidth="1.8" strokeOpacity="0.5" fill="none" />
          <circle cx="0" cy="0" r="84" stroke="#F5B8B1" strokeWidth="1.5" strokeOpacity="0.45" fill="url(#embryoGlow)" />
          <circle cx="0" cy="0" r="64" stroke="#FBC4AB" strokeWidth="1" strokeOpacity="0.4" fill="none" />

          {/* Delicate Embryo Silhouette vector */}
          <path
            d="M -5 -38
               C 12 -38, 26 -24, 26 -8
               C 26 6, 16 18, 20 30
               C 23 39, 32 44, 28 52
               C 23 60, 6 62, -8 52
               C -22 42, -26 28, -26 15
               C -26 -5, -16 -18, -18 -26
               C -20 -33, -15 -38, -5 -38 Z"
            fill="#F08080"
            fillOpacity="0.32"
          />
          {/* Embryo Head & Core Definition */}
          <circle cx="6" cy="-14" r="18" fill="#F08080" fillOpacity="0.38" />
          {/* Umbilical Arc */}
          <path
            d="M 12 18 C 28 24, 42 36, 44 54 C 45 68, 38 78, 30 84"
            stroke="#F5B8B1"
            strokeWidth="1.5"
            strokeOpacity="0.5"
            fill="none"
          />
        </g>
      </svg>
    </div>
  );
};
