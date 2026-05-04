import { useState, useEffect } from 'react';
import StreamCard from '../components/StreamCard';
import { apiFetch } from '../hooks/useWebSocket';

export default function GridView() {
  const [streams, setStreams] = useState([]);
  const [fullscreen, setFullscreen] = useState(null);

  useEffect(() => {
    apiFetch('/api/streams')
      .then(data => setStreams(data || []))
      .catch(() => setStreams([{ stream_id: 'stream_1' }, { stream_id: 'stream_2' }]));
  }, []);

  return (
    <>
      <div className="stream-grid">
        {streams.map(s => (
          <StreamCard key={s.stream_id} streamId={s.stream_id} onClick={setFullscreen} />
        ))}
        {streams.length === 0 && (
          <div className="glass-card" style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)' }}>
            <p style={{ fontSize: 36, marginBottom: 12 }}>📡</p>
            <p>No streams available</p>
            <p style={{ fontSize: 12, marginTop: 4 }}>Start the backend and camera simulators</p>
          </div>
        )}
      </div>

      {fullscreen && (
        <div className="modal-overlay" onClick={() => setFullscreen(null)}>
          <StreamCard streamId={fullscreen} />
        </div>
      )}
    </>
  );
}
