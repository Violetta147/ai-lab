import { useState, useCallback, useRef } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';

export default function StreamCard({ streamId, onClick }) {
  const [frame, setFrame] = useState(null);
  const imgRef = useRef(null);

  const handleMessage = useCallback((msg) => {
    if (msg.type === 'frame' && msg.data) {
      setFrame(`data:image/jpeg;base64,${msg.data}`);
    }
  }, []);

  const { status } = useWebSocket(`/ws/stream/${streamId}`, {
    onMessage: handleMessage,
    enabled: true,
  });

  const statusColor = status === 'connected' ? 'var(--accent-green)' :
    status === 'connecting' ? 'var(--accent-amber)' : 'var(--accent-red)';

  return (
    <div className="glass-card stream-card" onClick={() => onClick?.(streamId)}>
      {frame ? (
        <img ref={imgRef} src={frame} alt={streamId} />
      ) : (
        <div style={{ aspectRatio: '1', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
          Waiting for stream...
        </div>
      )}
      <div className="stream-card-header">
        <span className="stream-card-label">{streamId}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: statusColor }} />
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.7)' }}>{status}</span>
        </div>
      </div>
    </div>
  );
}
