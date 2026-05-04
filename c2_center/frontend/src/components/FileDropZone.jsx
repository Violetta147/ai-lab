import { useCallback, useState, useRef } from 'react';

export default function FileDropZone({ onFile }) {
  const [dragover, setDragover] = useState(false);
  const [fileName, setFileName] = useState(null);
  const inputRef = useRef(null);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragover(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      setFileName(file.name);
      onFile?.(file);
    }
  }, [onFile]);

  const handleClick = () => inputRef.current?.click();

  const handleChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setFileName(file.name);
      onFile?.(file);
    }
  };

  return (
    <div
      className={`file-drop-zone ${dragover ? 'dragover' : ''}`}
      onDragOver={e => { e.preventDefault(); setDragover(true); }}
      onDragLeave={() => setDragover(false)}
      onDrop={handleDrop}
      onClick={handleClick}
    >
      <input ref={inputRef} type="file" accept="image/*,video/*" hidden onChange={handleChange} />
      <div className="file-drop-zone-icon">📁</div>
      <p style={{ fontWeight: 600, fontSize: 14 }}>
        {fileName || 'Drop image or video here'}
      </p>
      <p style={{ fontSize: 12, marginTop: 4 }}>or click to browse</p>
    </div>
  );
}
