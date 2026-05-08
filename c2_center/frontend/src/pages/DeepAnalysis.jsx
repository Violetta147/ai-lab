import { useState, useEffect, useCallback } from 'react';
import PolygonDrawer from '../components/PolygonDrawer';
import TrafficChart from '../components/TrafficChart';
import { useWebSocket, apiFetch } from '../hooks/useWebSocket';

const ALGORITHMS = [
  { slug: 'absolute_count', name: 'Absolute Count' },
  { slug: 'area_occupancy', name: 'Area Occupancy (BEV)' },
  { slug: 'pce_density', name: 'PCE-Aware Density' },
  { slug: 'fundamental_equation', name: 'Fundamental Equation' },
  { slug: 'heatmap', name: 'Heatmap' },
  { slug: 'line_crossing', name: 'Line Crossing' },
];

export default function DeepAnalysis() {
  const [streams, setStreams] = useState([]);
  const [activeStream, setActiveStream] = useState('');
  const [activeAlgo, setActiveAlgo] = useState('absolute_count');
  const [drawMode, setDrawMode] = useState(null); // 'polygon' | 'entry_line' | 'exit_line'
  const [zones, setZones] = useState({});
  const [frame, setFrame] = useState(null);
  const [stats, setStats] = useState({});
  const [chartData, setChartData] = useState([]);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    apiFetch('/api/streams')
      .then(data => {
        const list = data || [];
        setStreams(list);
        if (list.length > 0) setActiveStream(list[0].stream_id);
      })
      .catch(() => {
        setStreams([{ stream_id: 'stream_1' }]);
        setActiveStream('stream_1');
      });
  }, []);

  useEffect(() => {
    let timer;
    const pollHealth = async () => {
      try {
        const data = await apiFetch('/api/health');
        setHealth(data);
      } catch (e) {
        setHealth({ status: 'error', kafka_connected: false, error: e.message });
      }
    };
    pollHealth();
    timer = setInterval(pollHealth, 5000);
    return () => clearInterval(timer);
  }, []);

  // Video WS
  const handleVideoMsg = useCallback((msg) => {
    if (msg.type === 'frame') setFrame(`data:image/jpeg;base64,${msg.data}`);
  }, []);
  const videoSocket = useWebSocket(activeStream ? `/ws/stream/${activeStream}` : null, {
    onMessage: handleVideoMsg, enabled: !!activeStream,
  });

  // Stats WS
  const handleStatsMsg = useCallback((msg) => {
    if (msg.type === 'stats') {
      setStats(msg.data || {});
      setChartData(prev => {
        const next = [...prev, {
          time: new Date().toLocaleTimeString(),
          count: msg.data?.vehicle_count || msg.data?.vehicles_in_roi || 0,
          flow: msg.data?.flow_q || 0,
        }];
        return next.slice(-120);
      });
    }
  }, []);
  const statsSocket = useWebSocket(activeStream ? `/ws/stats/${activeStream}` : null, {
    onMessage: handleStatsMsg, enabled: !!activeStream,
  });

  const videoStatus = videoSocket.status;
  const statsStatus = statsSocket.status;

  // Switch algorithm
  const switchAlgo = async (slug) => {
    setActiveAlgo(slug);
    if (activeStream) {
      try {
        await apiFetch(`/api/analytics/algorithm/${activeStream}`, {
          method: 'PUT', body: JSON.stringify({ algorithm: slug }),
        });
      } catch (e) {}
    }
  };

  // Handle zone completion
  const handleZoneComplete = async (points) => {
    const key = drawMode === 'polygon' ? 'roi_polygon' :
      drawMode === 'entry_line' ? 'entry_line' : 'exit_line';
    const updated = { ...zones, [key]: points };
    setZones(updated);
    setDrawMode(null);
    if (activeStream) {
      try {
        await apiFetch(`/api/zones/${activeStream}`, {
          method: 'PUT', body: JSON.stringify(updated),
        });
      } catch (e) {}
    }
  };

  const clearZones = async () => {
    setZones({});
    if (activeStream) {
      try { await apiFetch(`/api/zones/${activeStream}`, { method: 'DELETE' }); } catch (e) {}
    }
  };

  return (
    <div className="split-layout">
      <div className="split-main">
        {health && (!health.kafka_connected || health.status !== 'ok') && (
          <div className="glass-card" style={{ marginBottom: 12, padding: '10px 14px', border: '1px solid rgba(239, 68, 68, 0.35)', color: 'var(--accent-red)' }}>
            Live pipeline warning: {health.kafka_connected ? 'Kafka connected but backend reports a degraded state' : 'Kafka / DeepStream feed is not connected'}
          </div>
        )}
        {(videoStatus !== 'connected' || statsStatus !== 'connected') && (
          <div className="glass-card" style={{ marginBottom: 12, padding: '10px 14px', border: '1px solid rgba(245, 158, 11, 0.35)', color: 'var(--accent-amber)' }}>
            WebSocket status: video={videoStatus}, stats={statsStatus}
          </div>
        )}
        {/* Video + Canvas overlay */}
        <div className="glass-card video-canvas-container" style={{ flex: 1 }}>
          {frame ? <img src={frame} alt="stream" /> : (
            <div style={{ aspectRatio: '1', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
              Select a stream...
            </div>
          )}
          <PolygonDrawer mode={drawMode} onComplete={handleZoneComplete} existingZones={zones} />
        </div>

        {/* Traffic chart */}
        <TrafficChart data={chartData} />
      </div>

      <div className="split-sidebar">
        {/* Stream selector */}
        <div className="glass-card controls-panel">
          <div className="section-title"><span>📡</span> Stream</div>
          <select className="control-select" value={activeStream} onChange={e => setActiveStream(e.target.value)}>
            {streams.map(s => <option key={s.stream_id} value={s.stream_id}>{s.stream_id}</option>)}
          </select>
        </div>

        {/* Algorithm selector */}
        <div className="glass-card controls-panel">
          <div className="section-title"><span>🎛</span> Algorithm</div>
          <select className="control-select" value={activeAlgo} onChange={e => switchAlgo(e.target.value)}>
            {ALGORITHMS.map(a => <option key={a.slug} value={a.slug}>{a.name}</option>)}
          </select>
        </div>

        {/* Draw tools */}
        <div className="glass-card controls-panel">
          <div className="section-title"><span>🖊</span> Draw Tools</div>
          <button className={`btn ${drawMode === 'polygon' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setDrawMode(drawMode === 'polygon' ? null : 'polygon')} style={{ width: '100%' }}>
            {drawMode === 'polygon' ? '✏️ Drawing Polygon...' : 'Draw ROI Polygon'}
          </button>
          <button className={`btn ${drawMode === 'entry_line' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setDrawMode(drawMode === 'entry_line' ? null : 'entry_line')} style={{ width: '100%' }}>
            {drawMode === 'entry_line' ? '✏️ Drawing Entry...' : 'Draw Entry Line'}
          </button>
          <button className={`btn ${drawMode === 'exit_line' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setDrawMode(drawMode === 'exit_line' ? null : 'exit_line')} style={{ width: '100%' }}>
            {drawMode === 'exit_line' ? '✏️ Drawing Exit...' : 'Draw Exit Line'}
          </button>
          <button className="btn btn-danger" onClick={clearZones} style={{ width: '100%' }}>
            Clear All Zones
          </button>
        </div>

        {/* Live Dashboard */}
        <div className="glass-card controls-panel">
          <div className="section-title"><span>📊</span> Live Metrics</div>
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-value">{stats.flow_q?.toFixed(0) || stats.vehicle_count || '—'}</div>
              <div className="metric-label">{stats.flow_q !== undefined ? 'Flow (veh/h)' : 'Vehicles'}</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{stats.avg_speed?.toFixed(1) || stats.occupancy_pct?.toFixed(1) || '—'}</div>
              <div className="metric-label">{stats.avg_speed !== undefined ? 'Speed (km/h)' : 'Occupancy %'}</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{stats.density_k?.toFixed(1) || stats.pce_density?.toFixed(0) || '—'}</div>
              <div className="metric-label">{stats.pce_density !== undefined ? 'PCE/km' : 'Density'}</div>
            </div>
            <div className="metric-card">
              <div className="metric-value" style={{ fontSize: 14, color: stats.status === 'NORMAL' ? 'var(--accent-green)' : stats.status === 'HEAVY' ? 'var(--accent-amber)' : 'var(--accent-red)' }}>
                {stats.status || '—'}
              </div>
              <div className="metric-label">Status</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
