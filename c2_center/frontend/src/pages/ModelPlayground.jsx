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

export default function ModelPlayground() {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [file, setFile] = useState(null);
  const [resultImage, setResultImage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [info, setInfo] = useState(null);
  const [models, setModels] = useState([]);
  const [activeModel, setActiveModel] = useState('');

  useEffect(() => {
    apiFetch('/api/models').then(data => {
      setModels(data.models || []);
      setActiveModel(data.active || '');
    }).catch(() => {});
  }, []);

  const handleDetect = async () => {
    if (!file) return;
    setLoading(true);
    setResultImage(null);
    setInfo(null);
    try {
      const payload = {
        confidence: settings.confidence / 100,
        overlap: settings.overlap / 100,
        opacity: settings.opacity / 100,
        class_filter: settings.labelFilter,
        draw_confidence: settings.drawConfidence,
        draw_labels: settings.drawLabels,
        draw_boxes: settings.drawBoxes,
        censor: settings.censor,
      };
      console.log('Playground payload', payload);

      const form = new FormData();
      form.append('file', file);
      form.append('confidence', payload.confidence);
      form.append('overlap', payload.overlap);
      form.append('opacity', payload.opacity);
      form.append('class_filter', payload.class_filter);
      form.append('draw_confidence', payload.draw_confidence);
      form.append('draw_labels', payload.draw_labels);
      form.append('draw_boxes', payload.draw_boxes);
      form.append('censor', payload.censor);

      const res = await fetch(`${API_BASE}/api/playground/detect`, { method: 'POST', body: form });
      const data = await res.json();
      setResultImage(`data:image/jpeg;base64,${data.image}`);
      setInfo(
        `${data.detections_count} detections — model: ${data.model} — iou: ${data.used_iou} — class: ${data.resolved_class_filter ?? 'all'}`
      );
    } catch (e) {
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
          {resultImage ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
              <img src={resultImage} alt="Detection result" style={{ maxWidth: '100%', maxHeight: '100%', borderRadius: 'var(--radius-md)' }} />
            </div>
          ) : (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
              <FileDropZone onFile={setFile} />
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
        {/* Model selector */}
        <div className="glass-card controls-panel">
          <div className="section-title"><span>🧠</span> Model</div>
          <select className="control-select" value={activeModel} onChange={e => switchModel(e.target.value)}>
            {models.map(m => (
              <option key={m.name} value={m.name}>{m.name} ({m.num_classes} classes)</option>
            ))}
          </select>
        </div>

        {/* Detection controls */}
        <div className="glass-card">
          <DetectionControls settings={settings} onChange={setSettings} />
        </div>

        {/* Run button */}
        <button className="btn btn-primary" onClick={handleDetect} disabled={loading || !file}
          style={{ width: '100%', padding: '14px', fontSize: 14 }}>
          {loading ? '⏳ Processing...' : '🚀 Run Detection'}
        </button>

        {resultImage && (
          <button className="btn btn-ghost" onClick={() => { setResultImage(null); setInfo(null); }}
            style={{ width: '100%' }}>
            Clear Result
          </button>
        )}
      </div>
    </div>
  );
}
