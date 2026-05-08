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
  const [models, setModels] = useState([]);
  const [activeModel, setActiveModel] = useState('');

  useEffect(() => {
    apiFetch('/api/models').then(data => {
      setModels(data.models || []);
      setActiveModel(data.active || '');
    }).catch(() => {});
  }, []);

  useEffect(() => {
    return () => {
      if (resultVideoUrl) {
        URL.revokeObjectURL(resultVideoUrl);
      }
    };
  }, [resultVideoUrl]);

  const handleDetect = async () => {
    if (!file) return;
    setLoading(true);
    setResultImage(null);
    setResultVideo(null);
    if (resultVideoUrl) {
      URL.revokeObjectURL(resultVideoUrl);
      setResultVideoUrl(null);
    }
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
      console.log('Playground response status:', res.status, res.statusText);
      if (!res.ok) {
        const errorText = await res.text();
        console.error('Playground response error:', errorText);
        setInfo(`Server error: ${res.status} ${errorText}`);
        setLoading(false);
        return;
      }
      
      const data = await res.json();
      console.log('Playground parsed response keys:', Object.keys(data), 'video length:', data.video?.length || 'none');
      
      if (data.video) {
        console.log('Processing video response, mime:', data.video_mime);
        const mime = data.video_mime || 'video/mp4';
        const blob = base64ToBlob(data.video, mime);
        console.log('Blob created directly from base64, size:', blob.size, 'type:', blob.type);
        
        const objectUrl = URL.createObjectURL(blob);
        setResultVideoUrl(objectUrl);
        setResultVideo(objectUrl);
        setInfo(
          `${data.frames_processed} frames processed — model: ${data.model} — iou: ${data.used_iou} — class: ${data.resolved_class_filter ?? 'all'}`
        );
      } else {
        setResultImage(`data:image/jpeg;base64,${data.image}`);
        setInfo(
          `${data.detections_count} detections — model: ${data.model} — iou: ${data.used_iou} — class: ${data.resolved_class_filter ?? 'all'}`
        );
      }
    } catch (e) {
      console.error('Playground detect error:', e);
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

        {(resultImage || resultVideo) && (
          <button className="btn btn-ghost" onClick={() => {
            setResultImage(null);
            setResultVideo(null);
            if (resultVideoUrl) {
              URL.revokeObjectURL(resultVideoUrl);
              setResultVideoUrl(null);
            }
            setInfo(null);
          }}
            style={{ width: '100%' }}>
            Clear Result
          </button>
        )}
      </div>
    </div>
  );
}
