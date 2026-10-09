import React, { useState, useEffect, useRef } from 'react';

/**
 * Baby3D
 * An interactive, animated 3D embryo inside a bioluminescent amniotic sphere.
 * Features:
 * - Real 3D perspective mouse parallax / tilt
 * - Continuous organic 3D floating and breathing motion
 * - Rhythmic maternal heartbeat pulse halo
 * - Revolving concentric 3D orbital rings with particle nodes
 * - Glassmorphic specular lighting and depth refraction
 * - Floating bioluminescent cellular dust particles
 */
export const Baby3D: React.FC = () => {
  const [mouseOffset, setMouseOffset] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;

      // Calculate normalized offset from the center of the baby
      const dx = (e.clientX - centerX) / window.innerWidth;
      const dy = (e.clientY - centerY) / window.innerHeight;

      setMouseOffset({ x: dx, y: dy });
    };

    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  // Compute smooth 3D tilt angles based on mouse offset
  const tiltX = -mouseOffset.y * 18;
  const tiltY = mouseOffset.x * 18;

  return (
    <div
      ref={containerRef}
      className="fixed bottom-2 left-2 sm:bottom-4 sm:left-4 md:bottom-6 md:left-6 z-0 select-none pointer-events-none"
      style={{ perspective: '1000px' }}
      title="3D Embryo Vista"
    >
      {/* 3D Transformed Card Container */}
      <div
        className="relative w-40 h-40 sm:w-48 sm:h-48 md:w-56 md:h-56 transition-transform duration-300 ease-out animate-baby-float"
        style={{
          transformStyle: 'preserve-3d',
          transform: `rotateX(${tiltX}deg) rotateY(${tiltY}deg) scale(1)`,
        }}
      >
        {/* 1. Ambient Heartbeat Aura Pulse (Back Layer, translateZ -30px) */}
        <div
          className="absolute inset-0 rounded-full bg-radial from-[#F08080]/35 via-[#FBC4AB]/25 to-transparent blur-xl animate-baby-heartbeat"
          style={{ transform: 'translateZ(-30px)' }}
        />

        {/* 2. Concentric 3D Orbital Rings (Middle Layer) */}
        {/* Outer Ring */}
        <div
          className="absolute -inset-3 sm:-inset-4 rounded-full border border-[#F5B8B1]/40 border-dashed animate-orbit-3d pointer-events-none"
          style={{ transform: 'translateZ(-10px)' }}
        >
          {/* Revolving nutrient satellite node */}
          <div className="absolute top-1 left-1/2 -translate-x-1/2 w-2.5 h-2.5 rounded-full bg-gradient-to-r from-white to-[#F08080] shadow-[0_0_8px_#F08080]" />
        </div>

        {/* Middle Soft Glow Ring */}
        <div
          className="absolute -inset-1 rounded-full border border-[#FFF0ED]/70 animate-orbit-reverse-3d pointer-events-none"
          style={{ transform: 'translateZ(-5px)' }}
        >
          <div className="absolute bottom-2 right-1/4 w-2 h-2 rounded-full bg-white/90 shadow-[0_0_6px_#FBC4AB]" />
        </div>

        {/* 3. Main Glass Amniotic Sphere */}
        <div
          className="relative w-full h-full rounded-full overflow-hidden shadow-[0_12px_36px_-6px_rgba(240,128,128,0.35),_0_0_24px_rgba(251,196,171,0.4),_inset_0_0_24px_rgba(255,255,255,0.7)] border-2 border-white/60 bg-gradient-to-br from-white/40 via-[#FFF9F7]/30 to-[#FCE4E0]/40 backdrop-blur-xs transition-shadow duration-300 group-hover:shadow-[0_16px_44px_-4px_rgba(240,128,128,0.5),_0_0_32px_rgba(251,196,171,0.6)]"
          style={{ transform: 'translateZ(10px)' }}
        >
          {/* 3D Baby Embryo Image */}
          <img
            src="/baby-3d.png"
            alt="3D Embryo Baby"
            className="w-full h-full object-contain pointer-events-none drop-shadow-[0_8px_16px_rgba(240,128,128,0.25)] transition-transform duration-500 group-hover:scale-105"
            style={{
              mixBlendMode: 'multiply',
            }}
          />

          {/* Bioluminescent Heart Core Glow */}
          <div className="absolute top-[48%] left-[46%] -translate-x-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-radial from-[#F08080]/60 via-[#F4978E]/30 to-transparent blur-md animate-baby-heartbeat pointer-events-none" />

          {/* Glass Specular Reflection Highlight (Top Left Arch) */}
          <div
            className="absolute -top-12 -left-12 w-32 h-32 rounded-full bg-gradient-to-br from-white/70 via-white/20 to-transparent pointer-events-none blur-[1px]"
            style={{ transform: 'rotate(-25deg)' }}
          />

          {/* Secondary Specular Sweeping Gleam */}
          <div className="absolute inset-0 bg-gradient-to-tr from-transparent via-white/25 to-transparent pointer-events-none animate-specular-gleam" />
        </div>

        {/* 4. Bioluminescent Floating Micro-Dust Particles */}
        <div
          className="absolute -top-3 left-6 w-1.5 h-1.5 rounded-full bg-white shadow-[0_0_6px_#F5B8B1] animate-pulse"
          style={{ animationDuration: '3.5s' }}
        />
        <div
          className="absolute bottom-4 -right-2 w-2 h-2 rounded-full bg-[#F5B8B1] shadow-[0_0_8px_#F08080] animate-pulse"
          style={{ animationDuration: '4.8s' }}
        />
        <div
          className="absolute top-1/2 -left-3 w-1.5 h-1.5 rounded-full bg-[#FFDAB9] shadow-[0_0_6px_white] animate-pulse"
          style={{ animationDuration: '2.8s' }}
        />
      </div>
    </div>
  );
};
