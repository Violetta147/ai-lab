import { useRef, useState, useEffect, useCallback } from 'react';

/**
 * PolygonDrawer — Canvas overlay for drawing zones/lines on video.
 *
 * Props:
 *   mode: 'polygon' | 'line' | null
 *   onComplete: (points) => void
 *   onClear: () => void
 *   existingZones: { roi_polygon, entry_line, exit_line }
 */
export default function PolygonDrawer({ mode, onComplete, existingZones = {} }) {
  const canvasRef = useRef(null);
  const [points, setPoints] = useState([]);

  // Draw existing zones + current drawing
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw existing ROI polygon
    if (existingZones.roi_polygon?.length > 2) {
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(239, 68, 68, 0.8)';
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);
      existingZones.roi_polygon.forEach(([x, y], i) => {
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.closePath();
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Draw existing entry line
    if (existingZones.entry_line?.length === 2) {
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(34, 197, 94, 0.8)';
      ctx.lineWidth = 3;
      ctx.moveTo(...existingZones.entry_line[0]);
      ctx.lineTo(...existingZones.entry_line[1]);
      ctx.stroke();
    }

    // Draw existing exit line
    if (existingZones.exit_line?.length === 2) {
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(239, 68, 68, 0.8)';
      ctx.lineWidth = 3;
      ctx.moveTo(...existingZones.exit_line[0]);
      ctx.lineTo(...existingZones.exit_line[1]);
      ctx.stroke();
    }

    // Draw current drawing
    if (points.length > 0) {
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(99, 102, 241, 0.9)';
      ctx.lineWidth = 2;
      ctx.fillStyle = 'rgba(99, 102, 241, 0.15)';

      points.forEach(([x, y], i) => {
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        // Draw vertex dot
        ctx.fillStyle = 'rgba(99, 102, 241, 0.9)';
        ctx.beginPath();
        ctx.arc(x, y, 5, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.stroke();
    }
  }, [points, existingZones]);

  const handleClick = useCallback((e) => {
    if (!mode) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.round(e.clientX - rect.left);
    const y = Math.round(e.clientY - rect.top);

    if (mode === 'line' || mode === 'entry_line' || mode === 'exit_line') {
      const newPoints = [...points, [x, y]];
      if (newPoints.length >= 2) {
        onComplete?.(newPoints.slice(0, 2));
        setPoints([]);
      } else {
        setPoints(newPoints);
      }
    } else if (mode === 'polygon') {
      const newPoints = [...points, [x, y]];
      // Close polygon if clicking near first point
      if (newPoints.length > 2) {
        const [fx, fy] = newPoints[0];
        if (Math.abs(x - fx) < 15 && Math.abs(y - fy) < 15) {
          onComplete?.(newPoints.slice(0, -1));
          setPoints([]);
          return;
        }
      }
      setPoints(newPoints);
    }
  }, [mode, points, onComplete]);

  return (
    <canvas
      ref={canvasRef}
      onClick={handleClick}
      style={{ cursor: mode ? 'crosshair' : 'default' }}
    />
  );
}
