import { useState, useEffect } from 'react';
import FileDropZone from '../components/FileDropZone';
import DetectionControls from '../components/DetectionControls';
import { apiFetch, API_BASE } from '../hooks/useWebSocket';

const DEFAULT_SETTINGS = {
  confidence: 25,
  overlap: 45,
  opacity: 60,
  labelFilter: 'all',
  drawConfidence: true,
  drawLabels: true,
  drawBoxes: true,
  censor: false,
};

const DEFAULT_PARAMS = `{
  "roi_polygon": [
    [10, 10],
    [400, 10],
    [400, 400],
    [10, 400]
  ],
  "entry_line": [[10, 100], [400, 100]],
  "exit_line": [[10, 300], [400, 300]],
  "road_length_km": 0.05,
  "line_distance_km": 0.02
}`;

function base64ToBlob(base64, mimeType) {
  const sliceSize = 1024 * 1024;
  const byteCharacters = atob(base64);
  const byteArrays = [];

  for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {
    const slice = byteCharacters.slice(offset, offset + sliceSize);
    const byteNumbers = new Array(slice.length);
    for (let i = 0; i < slice.length; i += 1) {
      byteNumbers[i] = slice.charCodeAt(i);
    }
    byteArrays.push(new Uint8Array(byteNumbers));
  }

  return new Blob(byteArrays, { type: mimeType });
}

export default function ModelPlayground() {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [file, setFile] = useState(null);
  const [resultImage, setResultImage] = useState(null);
  const [resultVideo, setResultVideo] = useState(null);
  const [resultVideoUrl, setResultVideoUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [info, setInfo] = useState(null);
  const [metrics, setMetrics] = useState(null);
  
  const [models, setModels] = useState([]);
  const [activeModel, setActiveModel] = useState('');

  // Mode and Analytics state
  const [runMode, setRunMode] = useState('detect'); // 'detect' | 'analyze'
  const [algorithms, setAlgorithms] = useState([]);
  const [activeAlgo, setActiveAlgo] = useState('');
  const [paramsJson, setParamsJson] = useState(DEFAULT_PARAMS);

  useEffect(() => {
    // Fetch available YOLO models
    apiFetch('/api/models').then(data => {
      setModels(data.models || []);
      setActiveModel(data.active || '');
    }).catch(console.error);

    // Fetch all analytics algorithms (both live and offline are valid in playground)
    apiFetch('/api/analytics/algorithms').then(data => {
      const list = data || [];
      setAlgorithms(list);
      if (list.length > 0) setActiveAlgo(list[0].slug);
    }).catch(console.error);
  }, []);

  useEffect(() => {
    return () => {
      if (resultVideoUrl) {
        URL.revokeObjectURL(resultVideoUrl);
      }
    };
  }, [resultVideoUrl]);

  const handleRun = async () => {
    if (!file) return;
    setLoading(true);
    setResultImage(null);
    setResultVideo(null);
    setMetrics(null);
    if (resultVideoUrl) {
      URL.revokeObjectURL(resultVideoUrl);
      setResultVideoUrl(null);
    }
    setInfo(null);
    
    try {
      const form = new FormData();
      form.append('file', file);
      
      const endpoint = runMode === 'analyze' 
        ? `${API_BASE}/api/playground/analyze` 
        : `${API_BASE}/api/playground/detect`;

      if (runMode === 'detect') {
        form.append('confidence', settings.confidence / 100);
        form.append('overlap', settings.overlap / 100);
        form.append('opacity', settings.opacity / 100);
        form.append('class_filter', settings.labelFilter);
        form.append('draw_confidence', settings.drawConfidence);
        form.append('draw_labels', settings.drawLabels);
        form.append('draw_boxes', settings.drawBoxes);
        form.append('censor', settings.censor);
      } else {
        // Analytics mode
        form.append('algorithm', activeAlgo);
        form.append('confidence', settings.confidence / 100);
        form.append('overlap', settings.overlap / 100);
        // validate JSON before sending
        try {
          JSON.parse(paramsJson);
          form.append('params_json', paramsJson);
        } catch (e) {
          setInfo(`Invalid JSON parameters: ${e.message}`);
          setLoading(false);
          return;
        }
      }

      const res = await fetch(endpoint, { method: 'POST', body: form });
      
      if (!res.ok) {
        const errorText = await res.text();
        setInfo(`Server error: ${res.status} ${errorText}`);
        setLoading(false);
        return;
      }
      
      const data = await res.json();
      
      // The new endpoints return slightly different structure, but both return data_b64 / video
      const isVideo = data.video || data.kind === 'video';
      const b64Data = data.video || data.data_b64 || data.image;
      const framesCount = data.frames_processed || data.detections_count || 0;
      
      if (isVideo && b64Data) {
        const mime = data.video_mime || data.mime || 'video/mp4';
        const blob = base64ToBlob(b64Data, mime);
        const objectUrl = URL.createObjectURL(blob);
        setResultVideoUrl(objectUrl);
        setResultVideo(objectUrl);
        setInfo(`${framesCount} frames processed — model: ${data.model}`);
      } else if (b64Data) {
        setResultImage(`data:image/jpeg;base64,${b64Data}`);
        setInfo(`${framesCount} ${runMode === 'detect' ? 'detections' : 'frames processed'} — model: ${data.model}`);
      } else {
        setInfo("No visual output returned from backend.");
      }

      if (data.metrics) {
        setMetrics(data.metrics);
      }

    } catch (e) {
      console.error('Playground run error:', e);
      setInfo(`Error: ${e.message}`);
    }
    setLoading(false);
  };

  const switchModel = async (name) => {
    try {
      await apiFetch('/api/models/active', { method: 'PUT', body: JSON.stringify({ name }) });
      setActiveModel(name);
    } catch (e) {}
  };

  return (
    <div className="split-layout">
      <div className="split-main">
        <div className="glass-card" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          {resultVideo ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
              <video
                src={resultVideo}
                controls
                autoPlay
                muted
                loop
                playsInline
                style={{ maxWidth: '100%', maxHeight: '100%', borderRadius: 'var(--radius-md)' }}
              />
            </div>
          ) : resultImage ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
              <img src={resultImage} alt="Analysis result" style={{ maxWidth: '100%', maxHeight: '100%', borderRadius: 'var(--radius-md)' }} />
            </div>
          ) : (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
              <FileDropZone onFile={setFile} />
            </div>
          )}
          
          {metrics && (
             <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border-glass)', background: 'rgba(0,0,0,0.2)' }}>
               <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8 }}>Final Metrics:</div>
               <div className="metrics-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 8 }}>
                 {Object.entries(metrics).map(([k, v]) => (
                   <div key={k} className="metric-card" style={{ padding: '8px' }}>
                     <div className="metric-value" style={{ fontSize: 16 }}>
                       {typeof v === 'number' ? (v % 1 === 0 ? v : v.toFixed(2)) : String(v)}
                     </div>
                     <div className="metric-label" style={{ fontSize: 11 }}>{k}</div>
                   </div>
                 ))}
               </div>
             </div>
          )}

          {info && (
            <div style={{ padding: '8px 16px', borderTop: '1px solid var(--border-glass)', fontSize: 12, color: 'var(--text-muted)' }}>
              {info}
            </div>
          )}
        </div>
      </div>

      <div className="split-sidebar">
        
        {/* Mode Toggle */}
        <div className="glass-card controls-panel" style={{ padding: 8 }}>
          <div style={{ display: 'flex', gap: 4 }}>
            <button 
              className={`btn ${runMode === 'detect' ? 'btn-primary' : 'btn-ghost'}`} 
              style={{ flex: 1, padding: '8px' }}
              onClick={() => setRunMode('detect')}
            >
              Raw Detection
            </button>
            <button 
              className={`btn ${runMode === 'analyze' ? 'btn-primary' : 'btn-ghost'}`} 
              style={{ flex: 1, padding: '8px' }}
              onClick={() => setRunMode('analyze')}
            >
              Analytics
            </button>
          </div>
        </div>

        {/* Model selector */}
        <div className="glass-card controls-panel">
          <div className="section-title"><span>🧠</span> Model</div>
          <select className="control-select" value={activeModel} onChange={e => switchModel(e.target.value)}>
            {models.map(m => (
              <option key={m.name} value={m.name}>{m.name} ({m.num_classes} classes)</option>
            ))}
          </select>
        </div>

        {/* Analytics Configuration */}
        {runMode === 'analyze' && (
          <div className="glass-card controls-panel">
            <div className="section-title"><span>📈</span> Analytics Settings</div>
            
            <div className="control-group">
              <label className="control-label">Algorithm</label>
              <select className="control-select" value={activeAlgo} onChange={e => setActiveAlgo(e.target.value)}>
                {algorithms.map(a => (
                  <option key={a.slug} value={a.slug}>
                    {a.name} {a.mode === 'offline' ? '(Offline)' : ''}
                  </option>
                ))}
              </select>
            </div>

            <div className="control-group" style={{ marginTop: 12 }}>
              <label className="control-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Calibration JSON</span>
                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>params_json</span>
              </label>
              <textarea 
                className="control-input"
                style={{ 
                  height: 120, 
                  fontFamily: 'monospace', 
                  fontSize: 11, 
                  background: 'rgba(0,0,0,0.2)',
                  resize: 'vertical'
                }}
                value={paramsJson}
                onChange={e => setParamsJson(e.target.value)}
                spellCheck="false"
              />
            </div>
          </div>
        )}

        {/* Core Settings (applicable to both, but mostly detect) */}
        <div className="glass-card">
          <DetectionControls settings={settings} onChange={setSettings} runMode={runMode} />
        </div>

        {/* Run button */}
        <button className="btn btn-primary" onClick={handleRun} disabled={loading || !file}
          style={{ width: '100%', padding: '14px', fontSize: 14 }}>
          {loading ? '⏳ Processing...' : (runMode === 'analyze' ? '🔬 Run Analysis' : '🚀 Run Detection')}
        </button>

        {(resultImage || resultVideo) && (
          <button className="btn btn-ghost" onClick={() => {
            setResultImage(null);
            setResultVideo(null);
            setMetrics(null);
            if (resultVideoUrl) {
              URL.revokeObjectURL(resultVideoUrl);
              setResultVideoUrl(null);
            }
            setInfo(null);
          }}
            style={{ width: '100%', marginTop: 8 }}>
            Clear Result
          </button>
        )}
      </div>
    </div>
  );
}
