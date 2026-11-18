import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../../components/Navbar";
import ClaimForm from "../../components/ClaimForm";
import DocumentUpload from "../../components/DocumentUpload";
import {
  createDraft,
  getClaim,
  getClaimConfig,
  listClaims,
  listDocuments,
  listPolicies,
  saveDraft,
  submitClaim,
} from "../../services/claimService";

const AUTOSAVE_DELAY_MS = 1000;
const IN_PROGRESS = [
  "submitted",
  "documents_review",
  "info_required",
  "policy_verification",
  "assessment",
  "approval_review",
];
const DECIDED = ["approved", "rejected", "settled", "closed"];

const CARD_CLASS = "bg-white border-2 border-secondary rounded-none p-6";
const BUTTON_CLASS =
  "bg-secondary hover:bg-secondary text-white font-body font-semibold text-sm rounded-none py-2.5 px-5 transition-colors disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer";
const ERROR_CLASS = "bg-accent border-l-2 border-secondary p-3 font-mono text-xs text-secondary";

function wait(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function claimToForm(claim) {
  return {
    loss_date: claim.loss_date ? claim.loss_date.slice(0, 10) : "",
    claimed_amount: claim.claimed_amount === null ? "" : String(claim.claimed_amount),
    description: claim.description || "",
    details: claim.details || {},
  };
}

function buildPayload(values, version) {
  return {
    version,
    loss_date: values.loss_date || null,
    claimed_amount: values.claimed_amount === "" ? null : Number(values.claimed_amount),
    description: values.description,
    details: values.details,
  };
}

const SAVE_LABELS = {
  unsaved: "Unsaved changes",
  saving: "Saving...",
  saved: "Saved",
  failed: "Save failed",
};

export default function CustomerDashboard() {
  const navigate = useNavigate();

  const [config, setConfig] = useState(null);
  const [policies, setPolicies] = useState([]);
  const [claims, setClaims] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [newPolicyId, setNewPolicyId] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const [activeClaim, setActiveClaim] = useState(null);
  const [form, setForm] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [docsError, setDocsError] = useState("");
  const [saveState, setSaveState] = useState("saved");
  const [saveError, setSaveError] = useState("");
  const [conflict, setConflict] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const formRef = useRef(null);
  const versionRef = useRef(1);
  const claimIdRef = useRef(null);
  const timerRef = useRef(null);
  const savingRef = useRef(false);
  const dirtyRef = useRef(false);
  const conflictRef = useRef(false);

  async function loadAll() {
    setLoading(true);
    setLoadError("");

    try {
      const [configData, policyData, claimData] = await Promise.all([
        getClaimConfig(),
        listPolicies(),
        listClaims(),
      ]);
      setConfig(configData);
      setPolicies(policyData);
      setClaims(claimData);
    } catch (error) {
      setLoadError(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function persist() {
    if (savingRef.current) {
      return;
    }
    if (!dirtyRef.current) {
      return;
    }
    if (!claimIdRef.current) {
      return;
    }
    if (conflictRef.current) {
      return;
    }

    savingRef.current = true;
    dirtyRef.current = false;
    setSaveState("saving");
    setSaveError("");

    try {
      const payload = buildPayload(formRef.current, versionRef.current);
      const updated = await saveDraft(claimIdRef.current, payload);
      versionRef.current = updated.version;
      savingRef.current = false;

      if (dirtyRef.current) {
        setSaveState("unsaved");
        clearTimeout(timerRef.current);
        timerRef.current = setTimeout(persist, 300);
      } else {
        setSaveState("saved");
      }
    } catch (error) {
      savingRef.current = false;
      dirtyRef.current = true;

      if (error.status === 409) {
        conflictRef.current = true;
        setConflict(true);
      }

      setSaveState("failed");
      setSaveError(error.message);
    }
  }

  async function flushSave() {
    clearTimeout(timerRef.current);

    while (savingRef.current) {
      await wait(100);
    }

    if (dirtyRef.current) {
      await persist();
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  useEffect(() => {
    function warnBeforeLeaving(event) {
      if (dirtyRef.current || savingRef.current) {
        event.preventDefault();
        event.returnValue = "";
      }
    }

    window.addEventListener("beforeunload", warnBeforeLeaving);

    return () => {
      window.removeEventListener("beforeunload", warnBeforeLeaving);
      clearTimeout(timerRef.current);
      if (dirtyRef.current && !conflictRef.current) {
        persist();
      }
    };
  }, []);

  function handleFormChange(newValues) {
    setForm(newValues);
    formRef.current = newValues;
    dirtyRef.current = true;
    setSaveState("unsaved");

    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(persist, AUTOSAVE_DELAY_MS);
  }

  async function loadDocuments(claimId) {
    setDocsError("");

    try {
      const docs = await listDocuments(claimId);
      setDocuments(docs);
    } catch (error) {
      setDocsError(error.message);
    }
  }

  function openDraft(claim) {
    const initialForm = claimToForm(claim);

    claimIdRef.current = claim.id;
    versionRef.current = claim.version;
    dirtyRef.current = false;
    conflictRef.current = false;
    formRef.current = initialForm;

    setForm(initialForm);
    setActiveClaim(claim);
    setConflict(false);
    setSaveState("saved");
    setSaveError("");
    setSubmitError("");
    setDocuments([]);
    loadDocuments(claim.id);
  }

  function resetEditor() {
    claimIdRef.current = null;
    dirtyRef.current = false;
    conflictRef.current = false;
    formRef.current = null;
    setActiveClaim(null);
    setForm(null);
    setConflict(false);
  }

  async function handleCreateDraft() {
    if (!newPolicyId) {
      setCreateError("Choose a policy first.");
      return;
    }

    setCreating(true);
    setCreateError("");

    try {
      const draft = await createDraft(newPolicyId);
      setClaims((previous) => [draft, ...previous]);
      openDraft(draft);
    } catch (error) {
      setCreateError(error.message);
    } finally {
      setCreating(false);
    }
  }

  async function handleClose() {
    await flushSave();

    if (dirtyRef.current) {
      const leave = window.confirm("Your latest changes could not be saved. Leave anyway?");
      if (!leave) {
        return;
      }
    }

    resetEditor();
    loadAll();
  }

  async function handleReload() {
    try {
      const fresh = await getClaim(activeClaim.id);
      if (fresh.status === "draft") {
        openDraft(fresh);
      } else {
        resetEditor();
        loadAll();
      }
    } catch (error) {
      setSaveError(error.message);
    }
  }

  async function handleSubmit() {
    setSubmitError("");
    setSubmitting(true);

    try {
      await flushSave();

      if (dirtyRef.current) {
        setSubmitError("Your latest changes could not be saved. Fix the save problem and try again.");
        return;
      }

      await submitClaim(claimIdRef.current);
      resetEditor();
      navigate("/customer/claims");
    } catch (error) {
      setSubmitError(error.message);
    } finally {
      setSubmitting(false);
    }
  }

  function lineLabel(line) {
    if (config && config.lines[line]) {
      return config.lines[line].label;
    }
    return line;
  }

  function policyFor(policyId) {
    return policies.find((policy) => policy.id === policyId);
  }

  const drafts = claims.filter((claim) => claim.status === "draft");
  const inProgressCount = claims.filter((claim) => IN_PROGRESS.includes(claim.status)).length;
  const decidedCount = claims.filter((claim) => DECIDED.includes(claim.status)).length;

  return (
    <div className="min-h-screen w-full bg-primary">
      <Navbar />

      <main className="max-w-5xl mx-auto px-6 py-10 space-y-8">
        {loading && <p className="font-body text-sm text-secondary">Loading...</p>}

        {loadError && (
          <div className={ERROR_CLASS}>
            <p>{loadError}</p>
            <button onClick={loadAll} className="underline mt-2 cursor-pointer">
              Retry
            </button>
          </div>
        )}

        {!loading && !loadError && !activeClaim && (
          <>
            <section className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className={CARD_CLASS}>
                <p className="font-mono text-xs uppercase text-secondary">Drafts</p>
                <p className="font-display text-4xl text-secondary mt-2">{drafts.length}</p>
              </div>
              <div className={CARD_CLASS}>
                <p className="font-mono text-xs uppercase text-secondary">In progress</p>
                <p className="font-display text-4xl text-secondary mt-2">{inProgressCount}</p>
              </div>
              <div className={CARD_CLASS}>
                <p className="font-mono text-xs uppercase text-secondary">Decided</p>
                <p className="font-display text-4xl text-secondary mt-2">{decidedCount}</p>
              </div>
            </section>

            <section className={CARD_CLASS}>
              <h2 className="font-display text-2xl uppercase text-secondary mb-4">Start a claim</h2>

              {policies.length === 0 ? (
                <p className="font-body text-sm text-secondary">
                  You have no policies on file yet, so you cannot start a claim.
                </p>
              ) : (
                <div className="flex flex-col sm:flex-row gap-3">
                  <select
                    value={newPolicyId}
                    onChange={(e) => setNewPolicyId(e.target.value)}
                    disabled={creating}
                    className="flex-1 bg-white text-secondary font-body text-sm border-2 border-secondary rounded-none px-3 py-2.5"
                  >
                    <option value="">Choose a policy</option>
                    {policies.map((policy) => (
                      <option key={policy.id} value={policy.id}>
                        {lineLabel(policy.line)} · {policy.policy_number} · {policy.product}
                      </option>
                    ))}
                  </select>
                  <button onClick={handleCreateDraft} disabled={creating} className={BUTTON_CLASS}>
                    {creating ? "Creating..." : "Start claim"}
                  </button>
                </div>
              )}

              {createError && <div className={`${ERROR_CLASS} mt-4`}>{createError}</div>}
            </section>

            <section className={CARD_CLASS}>
              <h2 className="font-display text-2xl uppercase text-secondary mb-4">Your drafts</h2>

              {drafts.length === 0 ? (
                <p className="font-body text-sm text-secondary">No drafts. Start a claim above.</p>
              ) : (
                <ul className="divide-y-2 divide-secondary border-2 border-secondary">
                  {drafts.map((draft) => {
                    const policy = policyFor(draft.policy_id);
                    return (
                      <li key={draft.id} className="flex flex-wrap items-center justify-between gap-3 p-3">
                        <div>
                          <p className="font-body text-sm font-semibold text-secondary">
                            {lineLabel(draft.line)} claim
                            {policy ? ` · ${policy.policy_number}` : ""}
                          </p>
                          <p className="font-mono text-xs text-secondary">
                            Last edited {new Date(draft.updated_at).toLocaleString()}
                          </p>
                        </div>
                        <button onClick={() => openDraft(draft)} className={BUTTON_CLASS}>
                          Continue
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          </>
        )}

        {activeClaim && form && config && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <h2 className="font-display text-3xl uppercase text-secondary">
                {lineLabel(activeClaim.line)} claim
              </h2>
              <div className="flex items-center gap-4">
                <span className="font-mono text-xs uppercase text-secondary">{SAVE_LABELS[saveState]}</span>
                <button onClick={handleClose} className={BUTTON_CLASS}>
                  Back to dashboard
                </button>
              </div>
            </div>

            {conflict && (
              <div className={ERROR_CLASS}>
                <p>{saveError}</p>
                <button onClick={handleReload} className="underline mt-2 cursor-pointer">
                  Reload draft
                </button>
              </div>
            )}

            {!conflict && saveState === "failed" && (
              <div className={ERROR_CLASS}>
                <p>{saveError}</p>
                <button onClick={persist} className="underline mt-2 cursor-pointer">
                  Retry save
                </button>
              </div>
            )}

            <section className={CARD_CLASS}>
              <h3 className="font-display text-xl uppercase text-secondary mb-6">Claim details</h3>
              <ClaimForm
                fields={config.lines[activeClaim.line].fields}
                values={form}
                onChange={handleFormChange}
                disabled={conflict}
              />
            </section>

            <section className={CARD_CLASS}>
              <h3 className="font-display text-xl uppercase text-secondary mb-6">Documents</h3>
              {docsError && (
                <div className={`${ERROR_CLASS} mb-4`}>
                  <p>{docsError}</p>
                  <button onClick={() => loadDocuments(activeClaim.id)} className="underline mt-2 cursor-pointer">
                    Retry
                  </button>
                </div>
              )}
              <DocumentUpload
                key={activeClaim.id}
                claimId={activeClaim.id}
                documentTypes={config.lines[activeClaim.line].document_types}
                documents={documents}
                onUploaded={(doc) => setDocuments((previous) => [doc, ...previous])}
                disabled={conflict}
              />
            </section>

            {submitError && <div className={ERROR_CLASS}>{submitError}</div>}

            <button onClick={handleSubmit} disabled={submitting || conflict} className={BUTTON_CLASS}>
              {submitting ? "Submitting..." : "Submit claim"}
            </button>
          </>
        )}
      </main>
    </div>
  );
}