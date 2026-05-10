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
/**
 * PolygonDrawer — Canvas overlay for drawing zones/lines on video.
 */
export default function PolygonDrawer({ mode, onComplete, existingZones = {}, naturalWidth = 1, naturalHeight = 1 }) {
  const canvasRef = useRef(null);
  const [points, setPoints] = useState([]); // Internal state: Natural pixels

  // Helper to scale Natural -> CSS
  const toCSS = useCallback((x, y) => {
    const canvas = canvasRef.current;
    if (!canvas) return [x, y];
    const rect = canvas.getBoundingClientRect();
    const sx = rect.width / naturalWidth;
    const sy = rect.height / naturalHeight;
    return [x * sx, y * sy];
  }, [naturalWidth, naturalHeight]);

  // Helper to scale CSS -> Natural
  const toNatural = useCallback((x, y) => {
    const canvas = canvasRef.current;
    if (!canvas) return [x, y];
    const rect = canvas.getBoundingClientRect();
    const sx = naturalWidth / rect.width;
    const sy = naturalHeight / rect.height;
    return [Math.round(x * sx), Math.round(y * sy)];
  }, [naturalWidth, naturalHeight]);

  // Draw existing zones + current drawing
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    
    // Set internal resolution to match displayed size for sharp lines
    canvas.width = rect.width;
    canvas.height = rect.height;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw existing ROI polygon
    if (existingZones.roi_polygon?.length > 2) {
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(239, 68, 68, 0.8)';
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);
      existingZones.roi_polygon.forEach(([nx, ny], i) => {
        const [x, y] = toCSS(nx, ny);
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
      const p1 = toCSS(...existingZones.entry_line[0]);
      const p2 = toCSS(...existingZones.entry_line[1]);
      ctx.moveTo(...p1);
      ctx.lineTo(...p2);
      ctx.stroke();
    }

    // Draw existing exit line
    if (existingZones.exit_line?.length === 2) {
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(239, 68, 68, 0.8)';
      ctx.lineWidth = 3;
      const p1 = toCSS(...existingZones.exit_line[0]);
      const p2 = toCSS(...existingZones.exit_line[1]);
      ctx.moveTo(...p1);
      ctx.lineTo(...p2);
      ctx.stroke();
    }

    // Draw current drawing points (also in natural pixels)
    if (points.length > 0) {
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(99, 102, 241, 0.9)';
      ctx.lineWidth = 2;

      points.forEach(([nx, ny], i) => {
        const [x, y] = toCSS(nx, ny);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        // Draw vertex dot
        ctx.fillStyle = 'rgba(99, 102, 241, 0.9)';
        ctx.beginPath();
        ctx.arc(x, y, 5, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.stroke();
    }
  }, [points, existingZones, toCSS]);

  const handleClick = useCallback((e) => {
    if (!mode) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const cssX = e.clientX - rect.left;
    const cssY = e.clientY - rect.top;
    
    const [x, y] = toNatural(cssX, cssY);

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
      // Close polygon if clicking near first point (in natural pixels)
      if (newPoints.length > 2) {
        const [fnx, fny] = newPoints[0];
        // Scale the "click near" threshold to natural pixels too
        const threshold = toNatural(15, 0)[0] - toNatural(0, 0)[0];
        if (Math.abs(x - fnx) < Math.max(15, threshold) && Math.abs(y - fny) < Math.max(15, threshold)) {
          onComplete?.(newPoints.slice(0, -1));
          setPoints([]);
          return;
        }
      }
      setPoints(newPoints);
    }
  }, [mode, points, onComplete, toNatural]);

  return (
    <canvas
      ref={canvasRef}
      onClick={handleClick}
      style={{ 
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        cursor: mode ? 'crosshair' : 'default' 
      }}
    />
  );
}
