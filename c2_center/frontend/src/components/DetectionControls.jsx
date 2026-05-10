export default function DetectionControls({ settings, onChange, runMode = 'detect' }) {
  const update = (key, value) => onChange({ ...settings, [key]: value });

  return (
    <div className="controls-panel">
      <div className="section-title"><span>⚙️</span> Detection Controls</div>

      <div className="control-group">
        <label className="control-label">Confidence {settings.confidence}%</label>
        <input type="range" className="control-slider" min={0} max={100}
          value={settings.confidence} onChange={e => update('confidence', +e.target.value)} />
      </div>

      <div className="control-group">
        <label className="control-label">Overlap {settings.overlap}%</label>
        <input type="range" className="control-slider" min={0} max={100}
          value={settings.overlap} onChange={e => update('overlap', +e.target.value)} />
      </div>

      {runMode === 'detect' && (
        <>
          <div className="control-group">
            <label className="control-label">Opacity {settings.opacity}%</label>
            <input type="range" className="control-slider" min={0} max={100}
              value={settings.opacity} onChange={e => update('opacity', +e.target.value)} />
          </div>

          <div className="control-group">
            <label className="control-label">Label Display</label>
            <select className="control-select" value={settings.labelFilter}
              onChange={e => update('labelFilter', e.target.value)}>
              <option value="all">All Classes</option>
              <option value="car">Car Only</option>
              <option value="motor">Motor Only</option>
              <option value="heavy_vehicle">Heavy Vehicle Only</option>
            </select>
          </div>

          <label className="control-checkbox">
            <input type="checkbox" checked={settings.drawConfidence}
              onChange={e => update('drawConfidence', e.target.checked)} />
            Draw Confidence
          </label>
          <label className="control-checkbox">
            <input type="checkbox" checked={settings.drawLabels}
              onChange={e => update('drawLabels', e.target.checked)} />
            Draw Labels
          </label>
          <label className="control-checkbox">
            <input type="checkbox" checked={settings.drawBoxes}
              onChange={e => update('drawBoxes', e.target.checked)} />
            Draw Boxes
          </label>
          <label className="control-checkbox">
            <input type="checkbox" checked={settings.censor}
              onChange={e => update('censor', e.target.checked)} />
            Censor Predictions
          </label>
        </>
      )}
      {runMode === 'analyze' && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
          Note: Visual rendering in Analytics mode is controlled by the chosen algorithm.
        </div>
      )}
    </div>
  );
}
