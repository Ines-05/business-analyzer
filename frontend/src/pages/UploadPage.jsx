import { useEffect, useRef, useState } from "react";

import { analyzeFile } from "../api";

const PIPELINE_STEPS = [
  "Import des données",
  "Nettoyage et validation",
  "Calcul des indicateurs",
  "Génération des graphiques",
  "Recommandations IA",
];

const IconUploadArrow = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </svg>
);

const IconDoc = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
  </svg>
);

const IconCheck = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const IconCheckLg = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const IconX = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const IconSync = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="1 4 1 10 7 10" />
    <path d="M3.51 15a9 9 0 1 0 .49-4.5" />
  </svg>
);

const IconDownload = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="7 10 12 15 17 10" />
    <line x1="12" y1="15" x2="12" y2="3" />
  </svg>
);

const IconBarChart = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />
  </svg>
);

function ProcessingView() {
  const [doneCount, setDoneCount] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    let count = 0;
    timerRef.current = setInterval(() => {
      count += 1;
      setDoneCount(count);
      if (count >= PIPELINE_STEPS.length) clearInterval(timerRef.current);
    }, 650);
    return () => clearInterval(timerRef.current);
  }, []);

  return (
    <div className="processing-view">
      <div className="processing-icon"><IconBarChart /></div>
      <h2 className="processing-title">Analyse en cours</h2>
      <p className="processing-sub">Nous traitons vos données…</p>
      <div className="pipeline-steps">
        {PIPELINE_STEPS.map((label, i) => {
          const done = i < doneCount;
          return (
            <div key={label} className={`pipeline-step ${done ? "done" : ""}`}>
              <span className="pipeline-check">{done && <IconCheckLg />}</span>
              <span className="pipeline-label">{label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function fileKey(file) {
  return `${file.name}-${file.size}-${file.lastModified}`;
}

function fileSizeLabel(size) {
  if (!size) return "0 KB";
  return `${(size / 1024).toFixed(1)} KB`;
}

export default function UploadPage({ onRefresh, onOpenDashboard }) {
  const [files, setFiles] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [dragging, setDragging] = useState(false);

  function mergeFiles(nextFiles) {
    const map = new Map(files.map((item) => [fileKey(item), item]));
    nextFiles.forEach((item) => map.set(fileKey(item), item));
    setFiles(Array.from(map.values()));
  }

  function onInputChange(event) {
    const picked = Array.from(event.target.files || []);
    mergeFiles(picked);
  }

  function onDrop(event) {
    event.preventDefault();
    setDragging(false);
    const dropped = Array.from(event.dataTransfer.files || []).filter((file) => {
      const lower = file.name.toLowerCase();
      return lower.endsWith(".csv") || lower.endsWith(".xlsx") || lower.endsWith(".xls");
    });
    mergeFiles(dropped);
  }

  function removeFile(targetKey) {
    if (submitting) return;
    setFiles((prev) => prev.filter((item) => fileKey(item) !== targetKey));
  }

  async function runBatch() {
    if (!files.length || submitting) return;
    setSubmitting(true);

    const batch = files.map((file, index) => ({
      id: `${fileKey(file)}-${index}`,
      fileRef: fileKey(file),
      name: file.name,
      status: "queued",
      analysisId: null,
    }));

    const results = [];
    for (const row of batch) {
      const file = files.find((item) => fileKey(item) === row.fileRef);
      if (!file) continue;
      try {
        const payload = await analyzeFile({ companyName: "", file });
        results.push(payload);
      } catch {
        // silently skip failed files
      }
    }

    await onRefresh();
    setSubmitting(false);
    setFiles([]);
    if (results.length) {
      onOpenDashboard(results[results.length - 1].analysis_id);
    }
  }

  if (submitting) {
    return (
      <main className="upload-page">
        <section className="upload-shell">
          <ProcessingView />
        </section>
      </main>
    );
  }

  return (
    <main className="upload-page">
      <section className="upload-shell">
        <h2>Importez vos données</h2>
        <p>Chargez un ou plusieurs fichiers CSV / XLSX pour démarrer l&apos;analyse.</p>

        <label
          className={`upload-dropzone ${dragging ? "active" : ""}`}
          onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <div className="dropzone-icon"><IconUploadArrow /></div>
          <h3>Glissez vos fichiers ici</h3>
          <p>ou cliquez pour sélectionner&nbsp;•&nbsp;CSV, XLSX</p>
          <input type="file" multiple accept=".csv,.xlsx,.xls" onChange={onInputChange} hidden />
        </label>

        {files.length > 0 && (
          <div className="picked-list">
            {files.map((file) => {
              const id = fileKey(file);
              return (
                <div className="picked-item" key={id}>
                  <div className="picked-file-icon"><IconDoc /></div>
                  <div className="picked-info">
                    <p className="picked-name">{file.name}</p>
                    <p className="picked-meta">{fileSizeLabel(file.size)}</p>
                  </div>
                  <div className="picked-check"><IconCheck /></div>
                  <button type="button" className="picked-remove" aria-label="Retirer" onClick={() => removeFile(id)}>
                    <IconX />
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {files.length > 0 && (
          <p className="mapping-line">
            <IconSync />
            Vérifier le mapping des colonnes
          </p>
        )}

        <div className="upload-footer">
          <button type="button" className="ghost-btn download-example-btn" disabled>
            <IconDownload /> Télécharger un fichier exemple
          </button>
          <button
            type="button"
            className="top-action-btn"
            disabled={!files.length}
            onClick={runBatch}
          >
            Commencer l&apos;analyse →
          </button>
        </div>
      </section>
    </main>
  );
}
