import { useState } from 'react';
import './index.css';
import ModelPlayground from './pages/ModelPlayground';
import GridView from './pages/GridView';
import DeepAnalysis from './pages/DeepAnalysis';
import CameraManagement from './pages/CameraManagement';

const TABS = [
  { id: 'cameras', label: '📷 Cameras', icon: '📷' },
  { id: 'playground', label: '🧪 Playground', icon: '🧪' },
  { id: 'grid', label: '📹 Grid View', icon: '📹' },
  { id: 'analysis', label: '📊 Deep Analysis', icon: '📊' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('cameras');

  return (
    <div className="app-layout">
      {/* Navigation Bar */}
      <nav className="nav-bar">
        <div className="nav-logo">
          <div className="nav-logo-icon">C2</div>
          Surveillance Center
        </div>

        <div className="nav-tabs">
          {TABS.map(tab => (
            <button
              key={tab.id}
              className={`nav-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="nav-status">
          <div className="status-dot" />
          System Online
        </div>
      </nav>

      {/* Page Content */}
      <main className="page-container">
        {activeTab === 'cameras' && <CameraManagement />}
        {activeTab === 'playground' && <ModelPlayground />}
        {activeTab === 'grid' && <GridView />}
        {activeTab === 'analysis' && <DeepAnalysis />}
      </main>
    </div>
  );
}
