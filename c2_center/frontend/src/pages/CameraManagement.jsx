import React, { useState, useEffect } from 'react';
import './CameraManagement.css';

export default function CameraManagement() {
  const [cameras, setCameras] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [mediaMtxConfig, setMediaMtxConfig] = useState('');
  const [mediaMtxBusy, setMediaMtxBusy] = useState(false);
  const [formData, setFormData] = useState({
    stream_id: '',
    rtsp_url: '',
    name: '',
    description: '',
    enabled: true,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Fetch cameras
  useEffect(() => {
    fetchCameras();
  }, []);

  const fetchCameras = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/cameras');
      const data = await res.json();
      setCameras(data.cameras || []);
      setError(null);
    } catch (err) {
      setError('Failed to fetch cameras: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      let url = '/api/cameras';
      let method = 'POST';
      let body = { ...formData };

      if (editingId) {
        url = `/api/cameras/${editingId}`;
        method = 'PUT';
        // Only send changed fields for updates
        delete body.stream_id;
      }

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to save camera');
      }

      setSuccess(`Camera ${editingId ? 'updated' : 'created'} successfully!`);
      setTimeout(() => setSuccess(null), 3000);
      
      setFormData({
        stream_id: '',
        rtsp_url: '',
        name: '',
        description: '',
        enabled: true,
      });
      setEditingId(null);
      setShowForm(false);
      fetchCameras();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleEdit = (camera) => {
    setFormData(camera);
    setEditingId(camera.stream_id);
    setShowForm(true);
  };

  const handleDelete = async (streamId) => {
    if (!confirm(`Delete camera "${streamId}"?`)) return;

    try {
      const res = await fetch(`/api/cameras/${streamId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete camera');
      
      setSuccess('Camera deleted successfully!');
      setTimeout(() => setSuccess(null), 3000);
      fetchCameras();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleToggleEnabled = async (camera) => {
    try {
      const res = await fetch(`/api/cameras/${camera.stream_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !camera.enabled }),
      });
      if (!res.ok) throw new Error('Failed to update camera');
      fetchCameras();
    } catch (err) {
      setError(err.message);
    }
  };

  const handlePreviewMediaMtx = async () => {
    try {
      setMediaMtxBusy(true);
      const res = await fetch('/api/mediamtx/preview');
      if (!res.ok) throw new Error('Failed to preview MediaMTX config');
      const data = await res.json();
      setMediaMtxConfig(data.config || '');
      setSuccess(`MediaMTX config previewed for ${data.count || 0} cameras.`);
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(err.message);
    } finally {
      setMediaMtxBusy(false);
    }
  };

  const handleDeployMediaMtx = async () => {
    try {
      setMediaMtxBusy(true);
      const res = await fetch('/api/mediamtx/deploy', { method: 'POST' });
      if (!res.ok) throw new Error('Failed to deploy MediaMTX config');
      const data = await res.json();
      setSuccess(`MediaMTX config deployed to ${data.path}`);
      setTimeout(() => setSuccess(null), 3000);
      fetchCameras();
    } catch (err) {
      setError(err.message);
    } finally {
      setMediaMtxBusy(false);
    }
  };

  const handleCancel = () => {
    setShowForm(false);
    setEditingId(null);
    setFormData({
      stream_id: '',
      rtsp_url: '',
      name: '',
      description: '',
      enabled: true,
    });
  };

  if (loading) {
    return <div className="camera-management"><p>Loading cameras...</p></div>;
  }

  return (
    <div className="camera-management">
      <div className="header">
        <h2>Camera Management</h2>
        <div className="header-actions">
          <button className="btn-secondary" onClick={handlePreviewMediaMtx} disabled={mediaMtxBusy}>
            Preview MediaMTX
          </button>
          <button className="btn-secondary" onClick={handleDeployMediaMtx} disabled={mediaMtxBusy}>
            Deploy MediaMTX
          </button>
          <button
            className="btn-primary"
            onClick={() => {
              setShowForm(!showForm);
              if (showForm) handleCancel();
            }}
          >
            {showForm ? '✕ Cancel' : '+ Add Camera'}
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {mediaMtxConfig && (
        <div className="media-mtx-preview">
          <div className="media-mtx-preview-header">
            <h3>MediaMTX Config Preview</h3>
            <button className="btn-secondary" onClick={() => setMediaMtxConfig('')}>
              Hide
            </button>
          </div>
          <pre>{mediaMtxConfig}</pre>
        </div>
      )}

      {showForm && (
        <div className="form-container">
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <label>
                Stream ID *
                <input
                  type="text"
                  name="stream_id"
                  value={formData.stream_id}
                  onChange={handleInputChange}
                  disabled={!!editingId}
                  placeholder="e.g., camera_parking"
                  required
                />
              </label>
              <label>
                RTSP URL *
                <input
                  type="text"
                  name="rtsp_url"
                  value={formData.rtsp_url}
                  onChange={handleInputChange}
                  placeholder="rtsp://192.168.1.100:554/stream"
                  required
                />
              </label>
            </div>

            <div className="form-row">
              <label>
                Name *
                <input
                  type="text"
                  name="name"
                  value={formData.name}
                  onChange={handleInputChange}
                  placeholder="e.g., Parking Lot"
                  required
                />
              </label>
              <label>
                Description
                <input
                  type="text"
                  name="description"
                  value={formData.description}
                  onChange={handleInputChange}
                  placeholder="Optional description"
                />
              </label>
            </div>

            <div className="form-row">
              <label className="checkbox">
                <input
                  type="checkbox"
                  name="enabled"
                  checked={formData.enabled}
                  onChange={handleInputChange}
                />
                <span>Enabled (starts streaming immediately)</span>
              </label>
            </div>

            <div className="form-actions">
              <button type="submit" className="btn-success">
                {editingId ? 'Update Camera' : 'Add Camera'}
              </button>
              <button type="button" className="btn-secondary" onClick={handleCancel}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="cameras-grid">
        <div className="stats">
          <div className="stat">
            <div className="stat-value">{cameras.length}</div>
            <div className="stat-label">Total Cameras</div>
          </div>
          <div className="stat">
            <div className="stat-value">{cameras.filter(c => c.enabled).length}</div>
            <div className="stat-label">Active</div>
          </div>
          <div className="stat">
            <div className="stat-value">{cameras.filter(c => !c.enabled).length}</div>
            <div className="stat-label">Disabled</div>
          </div>
        </div>

        {cameras.length === 0 ? (
          <div className="empty-state">
            <p>No cameras configured.</p>
            <p>Click "Add Camera" to create one.</p>
          </div>
        ) : (
          <div className="cameras-list">
            {cameras.map(camera => (
              <div key={camera.stream_id} className={`camera-card ${camera.enabled ? 'enabled' : 'disabled'}`}>
                <div className="card-header">
                  <div className="camera-info">
                    <h3>{camera.name}</h3>
                    <p className="stream-id">{camera.stream_id}</p>
                  </div>
                  <div className={`status-badge ${camera.enabled ? 'active' : 'inactive'}`}>
                    {camera.enabled ? '● Active' : '○ Inactive'}
                  </div>
                </div>

                <div className="card-body">
                  <div className="field">
                    <label>RTSP URL:</label>
                    <code>{camera.rtsp_url}</code>
                  </div>
                  {camera.description && (
                    <div className="field">
                      <label>Description:</label>
                      <p>{camera.description}</p>
                    </div>
                  )}
                  <div className="field timestamps">
                    <label>Created:</label>
                    <p>{new Date(camera.created_at).toLocaleString()}</p>
                  </div>
                </div>

                <div className="card-actions">
                  <button
                    className={`btn-toggle ${camera.enabled ? 'disable' : 'enable'}`}
                    onClick={() => handleToggleEnabled(camera)}
                    title={camera.enabled ? 'Disable camera' : 'Enable camera'}
                  >
                    {camera.enabled ? '⏸ Disable' : '▶ Enable'}
                  </button>
                  <button
                    className="btn-edit"
                    onClick={() => handleEdit(camera)}
                    title="Edit camera"
                  >
                    ✎ Edit
                  </button>
                  <button
                    className="btn-delete"
                    onClick={() => handleDelete(camera.stream_id)}
                    title="Delete camera"
                  >
                    🗑 Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
