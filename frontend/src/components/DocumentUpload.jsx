import { useState } from "react";
import { downloadDocument, uploadDocument } from "../services/claimService";

const ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png", "pdf"];
const MAX_UPLOAD_MB = 10;
const BUTTON_CLASS =
  "bg-secondary hover:bg-black text-white font-body font-semibold text-sm rounded-none py-2.5 px-5 transition-colors disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer";

function checkFile(file) {
  const extension = file.name.split(".").pop().toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return "Only JPG, PNG and PDF files are allowed.";
  }
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    return `File is larger than ${MAX_UPLOAD_MB} MB.`;
  }
  return "";
}

export default function DocumentUpload({ claimId, documentTypes, documents, onUploaded, disabled }) {
  const firstType = documentTypes.length > 0 ? documentTypes[0].value : "";
  const [docType, setDocType] = useState(firstType);
  const [file, setFile] = useState(null);
  const [inputKey, setInputKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function labelFor(value) {
    const match = documentTypes.find((type) => type.value === value);
    return match ? match.label : value;
  }

  function hasDocument(value) {
    return documents.some((doc) => doc.doc_type === value);
  }

  function handleFileChange(event) {
    const chosen = event.target.files[0] || null;
    setError("");

    if (chosen) {
      const problem = checkFile(chosen);
      if (problem) {
        setError(problem);
        setFile(null);
        setInputKey((key) => key + 1);
        return;
      }
    }

    setFile(chosen);
  }

  async function handleUpload() {
    if (!file) {
      setError("Choose a file first.");
      return;
    }

    setBusy(true);
    setError("");

    try {
      const doc = await uploadDocument(claimId, docType, file);
      onUploaded(doc);
      setFile(null);
      setInputKey((key) => key + 1);
    } catch (uploadError) {
      setError(uploadError.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleView(documentId) {
    setError("");
    const newTab = window.open("", "_blank");

    try {
      const blob = await downloadDocument(claimId, documentId);
      const url = URL.createObjectURL(blob);
      if (newTab) {
        newTab.location.href = url;
      }
    } catch (viewError) {
      if (newTab) {
        newTab.close();
      }
      setError(viewError.message);
    }
  }

  const requiredTypes = documentTypes.filter((type) => type.required);

  return (
    <div className="space-y-6">
      {requiredTypes.length > 0 && (
        <div>
          <p className="font-mono text-xs uppercase tracking-wider text-black mb-2">
            Required documents
          </p>
          <ul className="space-y-1">
            {requiredTypes.map((type) => (
              <li key={type.value} className="font-body text-sm text-secondary">
                {hasDocument(type.value) ? "✓ " : "○ "}
                {type.label}
              </li>
            ))}
          </ul>
        </div>
      )}

      {!disabled && (
        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row gap-3">
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              disabled={busy}
              className="bg-white text-black font-body text-sm border-2 border-black rounded-none px-3 py-2.5"
            >
              {documentTypes.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
            <input
              key={inputKey}
              type="file"
              accept=".jpg,.jpeg,.png,.pdf"
              onChange={handleFileChange}
              disabled={busy}
              className="font-body text-sm text-black"
            />
            <button onClick={handleUpload} disabled={busy || !file} className={BUTTON_CLASS}>
              {busy ? "Uploading..." : "Upload"}
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-accent border-l-2 border-secondary p-3 font-mono text-xs text-black">
          {error}
        </div>
      )}

      {documents.length === 0 ? (
        <p className="font-body text-sm text-secondary">No documents uploaded yet.</p>
      ) : (
        <ul className="divide-y-2 divide-secondary border-2 border-secondary">
          {documents.map((doc) => (
            <li key={doc.id} className="flex flex-wrap items-center justify-between gap-3 p-3 bg-white">
              <div>
                <p className="font-body text-sm text-secondary font-semibold">{labelFor(doc.doc_type)}</p>
                <p className="font-mono text-xs text-secondary">
                  {Math.round(doc.size_bytes / 1024)} KB
                  {doc.retake ? " · this photo may be blurry, consider retaking it" : ""}
                </p>
              </div>
              <button
                onClick={() => handleView(doc.id)}
                className="font-body text-xs text-secondary underline underline-offset-4 cursor-pointer"
              >
                View
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}