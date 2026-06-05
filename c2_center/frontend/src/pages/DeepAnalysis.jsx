import { useState, useEffect, useCallback } from 'react';
import { useWebSocket, apiFetch } from '../hooks/useWebSocket';
import PolygonDrawer from '../components/PolygonDrawer';

/* ── Metric definitions per algorithm ──────────────────────────── */
const ALGO_METRICS = {
  heatmap: [
    { key: 'vehicle_count', label: 'Vehicles', format: v => v ?? '—' },
  ],
  absolute_count: [
    { key: 'vehicle_count', label: 'In ROI', format: v => v ?? '—' },
  ],
  line_crossing: [
    { key: 'entries',   label: 'Entries',   format: v => v ?? '—' },
    { key: 'exits',     label: 'Exits',     format: v => v ?? '—' },
    { key: 'net_count', label: 'Net Count', format: v => v ?? '—' },
  ],
  area_occupancy: [
    { key: 'occupancy_pct',  label: 'Occupancy %',  format: v => v != null ? `${v.toFixed(1)}%` : '—' },
    { key: 'vehicles_in_roi', label: 'In ROI',      format: v => v ?? '—' },
    { key: 'status',         label: 'Status',        format: v => v || '—' },
  ],
  pce_density: [
    { key: 'pce_density', label: 'PCE/km',  format: v => v != null ? v.toFixed(0) : '—' },
    { key: 'vehicle_count', label: 'Vehicles', format: v => v ?? '—' },
  ],
  fundamental_equation: [
    { key: 'flow_q',    label: 'Flow (veh/h)', format: v => v != null ? v.toFixed(0) : '—' },
    { key: 'avg_speed', label: 'Speed (km/h)', format: v => v != null ? v.toFixed(1) : '—' },
    { key: 'density_k', label: 'Density',       format: v => v != null ? v.toFixed(1) : '—' },
    { key: 'status',    label: 'Status',         format: v => v || '—' },
  ],
};

/* Default fallback metrics: render whatever keys are in stats */
function buildFallbackMetrics(stats) {
  const skip = new Set(['method', 'algorithm']);
  return Object.entries(stats)
    .filter(([k]) => !skip.has(k))
    .map(([k, v]) => ({
      key: k,
      label: k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
      value: typeof v === 'number' ? (Number.isInteger(v) ? v : v.toFixed(2)) : (v ?? '—'),
    }));
}

/* ── Status color helper ──────────────────────────────────────── */
function statusColor(val) {
  if (!val || val === '—') return 'var(--text-muted)';
  const s = String(val).toUpperCase();
  if (s === 'NORMAL' || s === 'FREE') return 'var(--accent-green)';
  if (s === 'HEAVY' || s === 'SLOW') return 'var(--accent-amber)';
  return 'var(--accent-red)';
}

export default function DeepAnalysis() {
  const [streams, setStreams] = useState([]);
  const [activeStream, setActiveStream] = useState('');
  const [algorithms, setAlgorithms] = useState([]);
  const [activeAlgo, setActiveAlgo] = useState('heatmap');
  const [frame, setFrame] = useState(null);
  const [stats, setStats] = useState({});
  const [classCounts, setClassCounts] = useState({});
  const [health, setHealth] = useState(null);

  // --- Drawing State ---
  const [drawMode, setDrawMode] = useState(null); // 'polygon' | 'entry_line' | 'exit_line'
  const [lockedFrameUrl, setLockedFrameUrl] = useState(null);
  const [naturalSize, setNaturalSize] = useState({ width: 0, height: 0 });
  const [zones, setZones] = useState({});
  const [isSavingZones, setIsSavingZones] = useState(false);

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

    // Fetch ALL algorithms (not just live) — let backend reject offline on PUT
    apiFetch('/api/analytics/algorithms')
      .then(data => {
        setAlgorithms(data || []);
        if (data?.length > 0 && !data.find(a => a.slug === 'heatmap')) {
          setActiveAlgo(data[0].slug);
        }
      })
      .catch(console.error);
  }, []);

  // Fetch the currently active algorithm when stream changes
  useEffect(() => {
    if (!activeStream) return;
    apiFetch(`/api/analytics/algorithm/${activeStream}`)
      .then(data => {
        if (data?.algorithm) setActiveAlgo(data.algorithm);
      })
      .catch(() => {});
      
    // Also fetch zones for this stream
    apiFetch(`/api/zones/${activeStream}`)
      .then(data => {
        setZones(data || {});
      })
      .catch(() => setZones({}));
  }, [activeStream]);

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
      const d = msg.data || {};
      setStats(d);

      // Update active algo from stats if backend provides it
      if (d.algorithm) setActiveAlgo(d.algorithm);

      // Extract per-class counts if available
      if (d.class_counts) {
        setClassCounts(d.class_counts);
      } else if (d.vehicle_count !== undefined) {
        // Fallback: just show total
        setClassCounts({ total: d.vehicle_count });
      }
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
    setStats({});
    setClassCounts({});
    if (activeStream) {
      try {
        const resp = await apiFetch(`/api/analytics/algorithm/${activeStream}`, {
          method: 'PUT', body: JSON.stringify({ algorithm: slug }),
        });
      } catch (e) {
        console.error('Algorithm switch failed:', e);
      }
    }
  };

  // --- Drawing Handlers ---
  const lockFrame = useCallback(() => {
    if (!frame) return;
    const img = new Image();
    img.onload = () => {
      setNaturalSize({ width: img.naturalWidth, height: img.naturalHeight });
      setLockedFrameUrl(frame);
      setDrawMode(null);
    };
    img.src = frame;
  }, [frame]);

  const unlockFrame = useCallback(() => {
    setLockedFrameUrl(null);
    setNaturalSize({ width: 0, height: 0 });
    setDrawMode(null);
  }, []);

  const handleZoneComplete = useCallback((points) => {
    const key = drawMode === 'polygon' ? 'roi_polygon' :
      drawMode === 'entry_line' ? 'entry_line' : 'exit_line';
    setZones(prev => ({ 
      ...prev, 
      [key]: points,
      roi_config_resolution: [naturalSize.width, naturalSize.height]
    }));
    setDrawMode(null);
  }, [drawMode, naturalSize]);

  const clearZones = useCallback(() => {
    setZones({});
    setDrawMode(null);
  }, []);

  const saveZones = useCallback(async () => {
    if (!activeStream) return;
    setIsSavingZones(true);
    try {
      await apiFetch(`/api/zones/${activeStream}`, {
        method: 'PUT',
        body: JSON.stringify(zones),
      });
      unlockFrame();
    } catch (e) {
      console.error('Failed to save zones:', e);
      alert('Failed to save zones: ' + e.message);
    } finally {
      setIsSavingZones(false);
    }
  }, [activeStream, zones, unlockFrame]);

  // Build dynamic metrics
  const algoMetrics = ALGO_METRICS[activeAlgo];
  const metricItems = algoMetrics
    ? algoMetrics.map(m => ({
        key: m.key,
        label: m.label,
        value: m.format(stats[m.key]),
      }))
    : buildFallbackMetrics(stats);

  return (
    <div className="deep-analysis-layout">
      <div className="da-main">
        {health && (!health.kafka_connected || health.status !== 'ok') && (
          <div className="glass-card da-alert da-alert-error">
            ⚠️ {health.kafka_connected ? 'Backend degraded' : 'Kafka / DeepStream not connected'}
          </div>
        )}
        {(videoStatus !== 'connected' || statsStatus !== 'connected') && (
          <div className="glass-card da-alert da-alert-warn">
            🔌 WS: video={videoStatus}, stats={statsStatus}
          </div>
        )}

        {/* Video feed — takes all available space */}
        <div className="glass-card da-video-container" style={{ position: 'relative' }}>
          {lockedFrameUrl ? (
            <>
              <img src={lockedFrameUrl} alt="Locked frame" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
              <PolygonDrawer 
                mode={drawMode} 
                onComplete={handleZoneComplete} 
                existingZones={zones} 
                naturalWidth={naturalSize.width}
                naturalHeight={naturalSize.height}
              />
              <div style={{ position: 'absolute', top: 16, left: 16, display: 'flex', gap: 6, zIndex: 10 }}>
                <button className="btn btn-ghost" onClick={unlockFrame} style={{ background: 'rgba(0,0,0,0.6)', padding: '6px 12px' }}>🔓 Unlock</button>
              </div>
            </>
          ) : frame ? (
            <img src={frame} alt="stream" />
          ) : (
            <div className="da-video-placeholder">
              <div style={{ fontSize: 48, marginBottom: 12 }}>📡</div>
              <div>Waiting for stream...</div>
            </div>
          )}
        </div>
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
            {algorithms.map(a => (
              <option key={a.slug} value={a.slug}>
                {a.name}{a.mode === 'offline' ? ' (offline)' : ''}
              </option>
            ))}
          </select>
        </div>

        {/* Draw Tools */}
        {activeStream && (
          <div className="glass-card controls-panel">
            <div className="section-title"><span>🖊</span> Draw Zones</div>
            
            {!lockedFrameUrl ? (
              <button className="btn btn-primary" onClick={lockFrame} style={{ width: '100%' }} disabled={!frame}>
                🔒 Lock Frame to Draw
              </button>
            ) : (
              <>
                {(algorithms.find(a => a.slug === activeAlgo)?.geometry_type === 'polygon') && (
                  <button className={`btn ${drawMode === 'polygon' ? 'btn-primary' : 'btn-ghost'}`}
                    onClick={() => setDrawMode(drawMode === 'polygon' ? null : 'polygon')} style={{ width: '100%', marginBottom: 4 }}>
                    {drawMode === 'polygon' ? '✏️ Drawing ROI...' : 'Draw ROI Polygon'}
                  </button>
                )}

                {(['line', 'dual_line'].includes(algorithms.find(a => a.slug === activeAlgo)?.geometry_type)) && (
                  <>
                    <button className={`btn ${drawMode === 'entry_line' ? 'btn-primary' : 'btn-ghost'}`}
                      onClick={() => setDrawMode(drawMode === 'entry_line' ? null : 'entry_line')} style={{ width: '100%', marginBottom: 4 }}>
                      {drawMode === 'entry_line' ? '✏️ Drawing Entry...' : 'Draw Entry Line'}
                    </button>
                    {algorithms.find(a => a.slug === activeAlgo)?.geometry_type === 'dual_line' && (
                      <button className={`btn ${drawMode === 'exit_line' ? 'btn-primary' : 'btn-ghost'}`}
                        onClick={() => setDrawMode(drawMode === 'exit_line' ? null : 'exit_line')} style={{ width: '100%', marginBottom: 4 }}>
                        {drawMode === 'exit_line' ? '✏️ Drawing Exit...' : 'Draw Exit Line'}
                      </button>
                    )}
                  </>
                )}

                <div style={{ display: 'flex', gap: 4, marginTop: 8 }}>
                  <button className="btn btn-success" onClick={saveZones} disabled={isSavingZones} style={{ flex: 1 }}>
                    {isSavingZones ? '⏳' : '💾 Save'}
                  </button>
                  <button className="btn btn-danger" onClick={clearZones} style={{ flex: 1 }}>
                    Clear
                  </button>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8, textAlign: 'center', fontStyle: 'italic' }}>
                  Overrides `stream_profiles.json`
                </div>
              </>
            )}
          </div>
        )}

        {/* Per-class detection counts */}
        <div className="glass-card controls-panel">
          <div className="section-title"><span>🏷</span> Detections</div>
          <div className="da-class-list">
            {Object.keys(classCounts).length > 0 ? (
              Object.entries(classCounts).map(([cls, count]) => (
                <div key={cls} className="da-class-item">
                  <span className="da-class-name">{cls}</span>
                  <span className="da-class-count">{count}</span>
                </div>
              ))
            ) : (
              <div className="da-class-item" style={{ color: 'var(--text-muted)' }}>
                No detections
              </div>
            )}
          </div>
        </div>

        {/* Dynamic Live Metrics */}
        <div className="glass-card controls-panel">
          <div className="section-title"><span>📊</span> Live Metrics</div>
          <div className="da-algo-badge">{activeAlgo.replace(/_/g, ' ')}</div>
          <div className="metrics-grid">
            {metricItems.map(m => (
              <div key={m.key} className="metric-card">
                <div
                  className="metric-value"
                  style={m.key === 'status' ? { fontSize: 14, color: statusColor(m.value), background: 'none', WebkitTextFillColor: 'unset' } : {}}
                >
                  {m.value}
                </div>
                <div className="metric-label">{m.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
