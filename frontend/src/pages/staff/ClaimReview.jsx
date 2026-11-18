
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Navbar from "../../components/Navbar";
import ClaimStatus from "../../components/ClaimStatus";
import StatusTimeline from "../../components/StatusTimeline";
import {
  addStaffNote,
  assignClaimToMe,
  downloadStaffDocument,
  getStaffClaim,
  getStaffDocumentOcr,
  recordDecision,
} from "../../services/claimService";

const CARD_CLASS = "bg-white border-2 border-secondary rounded-none p-6";

const BUTTON_CLASS =
  "bg-secondary hover:bg-secondary text-white font-body font-semibold text-sm rounded-none py-2.5 px-5 transition-colors disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer";

const ERROR_CLASS =
  "bg-accent border-l-2 border-secondary p-3 font-mono text-xs text-secondary";

const INPUT_CLASS =
  "w-full bg-white text-secondary font-body text-sm border-2 border-secondary rounded-none px-3 py-3 focus:outline-none focus:ring-2 focus:ring-secondary focus:ring-offset-2 disabled:opacity-60";

const LABEL_CLASS =
  "block font-mono text-xs uppercase tracking-wider font-medium text-secondary mb-2";

// What each decision needs from the officer
const DECISION_FORMS = {
  approve: {
    label: "Approve",
    reasonLabel: "Internal note (optional)",
    reasonRequired: false,
    showMessage: true,
    messageLabel: "Message to the customer (optional)",
    messageRequired: false,
  },
  reject: {
    label: "Reject",
    reasonLabel: "Internal reason",
    reasonRequired: true,
    showMessage: true,
    messageLabel: "Explanation for the customer",
    messageRequired: true,
  },
  request_info: {
    label: "Request information",
    reasonLabel: "Internal note (optional)",
    reasonRequired: false,
    showMessage: true,
    messageLabel: "What do you need from the customer?",
    messageRequired: true,
  },
  escalate: {
    label: "Escalate to specialist",
    reasonLabel: "Reason for escalation",
    reasonRequired: true,
    showMessage: false,
    messageLabel: "",
    messageRequired: false,
  },
};

const TASK_LABELS = {
  info_request: "Waiting for customer",
  specialist_escalation: "Specialist review",
};

function formatDate(isoString) {
  if (!isoString) {
    return "-";
  }

  return new Date(isoString).toLocaleDateString();
}

function formatDateTime(isoString) {
  if (!isoString) {
    return "-";
  }

  return new Date(isoString).toLocaleString();
}

function formatMoney(value) {
  if (value === null || value === undefined) {
    return "-";
  }

  return Number(value).toLocaleString("en-IN");
}

function Section({ title, children }) {
  return (
    <section className={CARD_CLASS}>
      <h3 className="font-display text-xl uppercase text-secondary mb-6">
        {title}
      </h3>
      {children}
    </section>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <dt className="font-mono text-xs uppercase">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

const OCR_STATUS_LABELS = {
  pending: "Text not read yet",
  processing: "Reading text now",
  done: "Text extracted",
  low_quality: "Low quality, check the original",
  failed: "Could not be read",
};

function OcrPanel({ claimId, documentId, ocrStatus }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  async function loadOcr() {
    setLoading(true);
    setError("");

    try {
      const data = await getStaffDocumentOcr(claimId, documentId);
      setResult(data);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleToggle() {
    if (open) {
      setOpen(false);
      return;
    }

    setOpen(true);
    await loadOcr();
  }

  return (
    <div className="mt-3">
      <button
        onClick={handleToggle}
        className="font-body text-xs text-secondary underline underline-offset-4 cursor-pointer"
      >
        {open ? "Hide extracted text" : "Show extracted text"}
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          {loading && (
            <p className="font-body text-sm text-secondary">Loading...</p>
          )}

          {error && (
            <div className={ERROR_CLASS}>
              <p>{error}</p>
              <button
                onClick={loadOcr}
                className="underline mt-2 cursor-pointer"
              >
                Retry
              </button>
            </div>
          )}

          {result && (
            <>
              <p className="font-mono text-xs text-secondary">
                {OCR_STATUS_LABELS[result.ocr_status] || result.ocr_status}
                {result.overall_confidence !== null
                  ? ` · average confidence ${result.overall_confidence}%`
                  : ""}
              </p>

              {result.error && (
                <div className={ERROR_CLASS}>{result.error}</div>
              )}

              {result.truncated && (
                <p className="font-body text-sm text-secondary">
                  This file has {result.page_count} pages. Only the first{" "}
                  {result.pages.length} were read.
                </p>
              )}

              <p className="font-body text-xs text-secondary">
                This text was read by a machine and may contain mistakes.
                Always check the original file.
              </p>

              {result.pages.map((page) => (
                <div
                  key={page.page}
                  className="border-2 border-secondary p-3"
                >
                  <p className="font-mono text-xs uppercase text-secondary">
                    Page {page.page} ·{" "}
                    {page.method === "ocr" ? "scanned" : "text in file"} ·
                    confidence {page.confidence}%
                  </p>

                  {page.low_confidence && (
                    <p className="font-body text-sm font-semibold text-secondary mt-1">
                      Low confidence. Check this page in the original file.
                    </p>
                  )}

                  <pre className="font-mono text-xs text-secondary mt-2 whitespace-pre-wrap">
                    {page.text || "(no text found)"}
                  </pre>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function ClaimReview() {
  const { claimId } = useParams();

  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");

  const [assigning, setAssigning] = useState(false);

  const [analysisRefreshing, setAnalysisRefreshing] = useState(false);
  const [lastAnalysisRefresh, setLastAnalysisRefresh] = useState(null);

  const [noteText, setNoteText] = useState("");
  const [noteBusy, setNoteBusy] = useState(false);

  const [decision, setDecision] = useState("");
  const [reason, setReason] = useState("");
  const [customerMessage, setCustomerMessage] = useState("");
  const [deciding, setDeciding] = useState(false);

  async function loadDetail() {
    setLoadError("");

    try {
      const data = await getStaffClaim(claimId);
      setDetail(data);
    } catch (error) {
      setLoadError(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function refreshAnalysis() {
    setAnalysisRefreshing(true);

    try {
      const data = await getStaffClaim(claimId);
      setDetail(data);
      setLastAnalysisRefresh(new Date());
      setLoadError("");
      setActionError("");
    } catch (error) {
      setActionError(
        `Could not refresh agent analysis: ${error.message}`
      );
    } finally {
      setAnalysisRefreshing(false);
    }
  }

  useEffect(() => {
    loadDetail();
  }, [claimId]);

  useEffect(() => {
    if (!detail?.claim) return;

    const completedStatuses = [
      "approval_review",
      "approved",
      "rejected",
      "settled",
      "closed",
      "info_required",
    ];

    if (completedStatuses.includes(detail.claim.status)) {
      return;
    }

    const intervalId = window.setInterval(async () => {
      try {
        const data = await getStaffClaim(claimId);
        setDetail(data);
        setLastAnalysisRefresh(new Date());
      } catch (error) {
        console.error(
          "Automatic agent-analysis refresh failed:",
          error
        );
      }
    }, 5000);

    return () => window.clearInterval(intervalId);
  }, [claimId, detail?.claim?.status]);

  async function handleAssign() {
    setAssigning(true);
    setActionError("");

    try {
      await assignClaimToMe(claimId);
      await loadDetail();
    } catch (error) {
      setActionError(error.message);
    } finally {
      setAssigning(false);
    }
  }

  async function handleAddNote() {
    const text = noteText.trim();

    if (!text) {
      return;
    }

    setNoteBusy(true);
    setActionError("");

    try {
      await addStaffNote(claimId, text);
      setNoteText("");
      await loadDetail();
    } catch (error) {
      setActionError(error.message);
    } finally {
      setNoteBusy(false);
    }
  }

  async function handleViewDocument(documentId) {
    setActionError("");

    // Open the tab first so the browser does not block it as a popup.
    const newTab = window.open("", "_blank");

    try {
      const blob = await downloadStaffDocument(claimId, documentId);
      const url = URL.createObjectURL(blob);

      if (newTab) {
        newTab.location.href = url;
      }
    } catch (error) {
      if (newTab) {
        newTab.close();
      }

      setActionError(error.message);
    }
  }

  function chooseDecision(key) {
    setDecision(key);
    setReason("");
    setCustomerMessage("");
    setActionError("");
  }

  async function handleDecision() {
    const form = DECISION_FORMS[decision];

    if (form.reasonRequired && !reason.trim()) {
      setActionError(`${form.reasonLabel} is required.`);
      return;
    }

    if (form.messageRequired && !customerMessage.trim()) {
      setActionError(`${form.messageLabel} is required.`);
      return;
    }

    // Approve and reject are final, so ask once more.
    if (decision === "approve" || decision === "reject") {
      const sure = window.confirm(
        `Are you sure you want to ${form.label.toLowerCase()} this claim? This cannot be undone.`
      );

      if (!sure) {
        return;
      }
    }

    setDeciding(true);
    setActionError("");

    try {
      let messageToSend = "";

      if (form.showMessage) {
        messageToSend = customerMessage;
      }

      await recordDecision(
        claimId,
        decision,
        reason,
        messageToSend
      );

      setDecision("");
      setReason("");
      setCustomerMessage("");

      await loadDetail();
    } catch (error) {
      setActionError(error.message);

      // The claim may have changed, so show the latest version.
      if (error.status === 409) {
        await loadDetail();
      }
    } finally {
      setDeciding(false);
    }
  }

  function decisionButtonClass(key) {
    const base =
      "font-body text-sm text-secondary px-4 py-2 border-2 border-secondary cursor-pointer";

    if (key === decision) {
      return `${base} bg-accent font-semibold`;
    }

    return `${base} bg-white`;
  }

  return (
    <div className="min-h-screen w-full bg-accent/30">
      <Navbar />

      <main className="max-w-5xl mx-auto px-6 py-10 space-y-6">
        <Link
          to="/staff"
          className="font-body text-sm text-secondary underline underline-offset-4"
        >
          ← Back to dashboard
        </Link>

        {loading && (
          <p className="font-body text-sm text-secondary">
            Loading...
          </p>
        )}

        {loadError && (
          <div className={ERROR_CLASS}>
            <p>{loadError}</p>
            <button
              onClick={loadDetail}
              className="underline mt-2 cursor-pointer"
            >
              Retry
            </button>
          </div>
        )}

        {detail && (
          <ReviewBody
            detail={detail}
            actionError={actionError}
            assigning={assigning}
            onAssign={handleAssign}
            noteText={noteText}
            setNoteText={setNoteText}
            noteBusy={noteBusy}
            onAddNote={handleAddNote}
            onViewDocument={handleViewDocument}
            decision={decision}
            chooseDecision={chooseDecision}
            reason={reason}
            setReason={setReason}
            customerMessage={customerMessage}
            setCustomerMessage={setCustomerMessage}
            deciding={deciding}
            onDecide={handleDecision}
            decisionButtonClass={decisionButtonClass}
            lastAnalysisRefresh={lastAnalysisRefresh}
            analysisRefreshing={analysisRefreshing}
            onRefreshAnalysis={refreshAnalysis}
          />
        )}
      </main>
    </div>
  );
}

function ReviewBody(props) {
  const { detail } = props;
  const claim = detail.claim;
  const policy = detail.policy;

  const form = props.decision
    ? DECISION_FORMS[props.decision]
    : null;

  // Explain why there are no decision buttons.
  let noDecisionText = "";

  if (detail.allowed_decisions.length === 0) {
    if (claim.status === "info_required") {
      noDecisionText =
        "Waiting for the customer to respond to the information request.";
    } else {
      noDecisionText = `No decision can be recorded while this claim is "${claim.status_label}".`;
    }
  }

  return (
    <>
      <section className={CARD_CLASS}>
        <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
          <div>
            <h1 className="font-display text-3xl uppercase text-secondary">
              {claim.claim_number}
            </h1>

            <p className="font-mono text-xs text-secondary mt-1">
              {detail.line_label} · {policy.policy_number}
            </p>
          </div>

          <ClaimStatus
            status={claim.status}
            label={claim.status_label}
            description=""
          />
        </div>

        <div className="flex flex-wrap items-center gap-4">
          {detail.assignee ? (
            <p className="font-body text-sm text-secondary">
              Assigned to{" "}
              <strong>{detail.assignee.staff_name}</strong>
            </p>
          ) : (
            <p className="font-body text-sm text-secondary">
              Not assigned yet.
            </p>
          )}

          <button
            onClick={props.onAssign}
            disabled={props.assigning}
            className={BUTTON_CLASS}
          >
            {props.assigning ? "Assigning..." : "Assign to me"}
          </button>
        </div>
      </section>

      {props.actionError && (
        <div className={ERROR_CLASS}>{props.actionError}</div>
      )}

      <Section title="Claim details">
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 font-body text-sm text-secondary">
          <Field label="Customer">{claim.customer_name}</Field>
          <Field label="Email">{claim.customer_email}</Field>
          <Field label="Date of loss">{formatDate(claim.loss_date)}</Field>
          <Field label="Claimed amount">
            {formatMoney(claim.claimed_amount)}
          </Field>

          {detail.form_fields.map((field) => (
            <Field key={field.name} label={field.label}>
              {(claim.details[field.name] || "-").replace(/_/g, " ")}
            </Field>
          ))}

          <div className="sm:col-span-2">
            <Field label="What happened">
              {claim.description || "-"}
            </Field>
          </div>
        </dl>
      </Section>

      <Section title="Policy">
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 font-body text-sm text-secondary">
          <Field label="Product">{policy.product}</Field>
          <Field label="Sum insured">
            {formatMoney(policy.sum_insured)}
          </Field>
          <Field label="Deductible">
            {formatMoney(policy.deductible)}
          </Field>
          <Field label="Co-payment">
            {policy.copay_percent}%
          </Field>
          <Field label="Policy period">
            {formatDate(policy.start_date)} to{" "}
            {formatDate(policy.end_date)}
          </Field>
        </dl>
      </Section>

      <Section title="Documents">
        {detail.documents.length === 0 ? (
          <p className="font-body text-sm text-secondary">
            No documents uploaded.
          </p>
        ) : (
          <ul className="divide-y-2 divide-secondary border-2 border-secondary">
            {detail.documents.map((doc) => (
              <li key={doc.id} className="p-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-body text-sm font-semibold text-secondary">
                      {detail.doc_type_labels[doc.doc_type] ||
                        doc.doc_type}
                    </p>

                    <p className="font-mono text-xs text-secondary">
                      {Math.round(doc.size_bytes / 1024)} KB · uploaded{" "}
                      {formatDateTime(doc.uploaded_at)}
                      {doc.retake ? " · photo may be blurry" : ""}
                    </p>

                    <p className="font-mono text-xs text-secondary">
                      {OCR_STATUS_LABELS[doc.ocr_status] ||
                        doc.ocr_status}
                    </p>
                  </div>

                  <button
                    onClick={() => props.onViewDocument(doc.id)}
                    className="font-body text-xs text-secondary underline underline-offset-4 cursor-pointer"
                  >
                    View
                  </button>
                </div>

                <OcrPanel
                  claimId={detail.claim.id}
                  documentId={doc.id}
                  ocrStatus={doc.ocr_status}
                />
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Automated analysis">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
          <div>
            <p className="font-mono text-xs uppercase text-secondary">
              Workflow status
            </p>

            <p className="font-body text-sm font-semibold text-secondary mt-1">
              {claim.status === "approval_review"
                ? "Agent processing completed — awaiting Claims Officer review"
                : claim.status === "info_required"
                  ? "Workflow paused — waiting for customer information"
                  : ["approved", "rejected", "settled", "closed"].includes(
                      claim.status
                    )
                    ? "Claim decision recorded"
                    : "Workflow processing"}
            </p>

            {props.lastAnalysisRefresh && (
              <p className="font-mono text-xs text-secondary mt-1">
                Last refreshed:{" "}
                {props.lastAnalysisRefresh.toLocaleTimeString()}
              </p>
            )}
          </div>

          <button
            type="button"
            onClick={props.onRefreshAnalysis}
            disabled={props.analysisRefreshing}
            className={BUTTON_CLASS}
          >
            {props.analysisRefreshing
              ? "Refreshing..."
              : "Refresh analysis"}
          </button>
        </div>

        {!Array.isArray(detail.agent_runs) ||
        detail.agent_runs.length === 0 ? (
          <div className="border-2 border-secondary p-4">
            <p className="font-body text-sm text-secondary">
              No agent execution results have been recorded yet.
            </p>

            <p className="font-body text-xs text-secondary mt-2">
              Results will appear here when the backend records agent
              executions. Refresh this section to check for updates.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {detail.agent_runs.map((run, index) => {
              const agentName = (run.agent_name || "Unknown agent")
                .replaceAll("_", " ");

              const status = (run.status || "unknown").toLowerCase();

              return (
                <details
                  key={`${run.agent_name || "agent"}-${index}`}
                  className="border-2 border-secondary p-4"
                  open={index === detail.agent_runs.length - 1}
                >
                  <summary className="cursor-pointer list-none">
                    <div className="flex flex-wrap justify-between items-center gap-3">
                      <div>
                        <p className="font-mono text-sm uppercase font-semibold text-secondary">
                          {agentName}
                        </p>

                        <p className="font-mono text-xs text-secondary mt-1">
                          {status.toUpperCase()}
                          {run.duration_ms != null
                            ? ` · ${run.duration_ms} ms`
                            : ""}
                        </p>
                      </div>

                      <span
                        className={`font-mono text-xs uppercase border-2 px-3 py-1 ${
                          status === "success"
                            ? "border-secondary text-secondary"
                            : status === "failed"
                              ? "border-secondary text-secondary"
                              : "border-secondary text-secondary"
                        }`}
                      >
                        {status}
                      </span>
                    </div>
                  </summary>

                  <div className="border-t-2 border-secondary mt-4 pt-4 space-y-3">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <p className="font-mono text-xs uppercase text-secondary">
                          Agent version
                        </p>

                        <p className="font-body text-sm text-secondary">
                          {run.agent_version || "Not provided"}
                        </p>
                      </div>

                      <div>
                        <p className="font-mono text-xs uppercase text-secondary">
                          Execution time
                        </p>

                        <p className="font-body text-sm text-secondary">
                          {formatDateTime(run.created_at)}
                        </p>
                      </div>
                    </div>

                    {run.error && (
                      <div className="border-l-4 border-secondary bg-primary/30 p-3">
                        <p className="font-mono text-xs uppercase text-secondary">
                          Execution error
                        </p>

                        <p className="font-body text-sm text-secondary mt-2 whitespace-pre-wrap break-words">
                          {run.error}
                        </p>
                      </div>
                    )}

                    {run.output !== null &&
                      run.output !== undefined && (
                        <div>
                          <p className="font-mono text-xs uppercase text-secondary mb-2">
                            Agent output
                          </p>

                          <pre className="font-mono text-xs whitespace-pre-wrap break-words overflow-x-auto bg-primary/30 border border-secondary p-3">
                            {typeof run.output === "string"
                              ? run.output
                              : JSON.stringify(run.output, null, 2)}
                          </pre>
                        </div>
                      )}

                    {!run.output && !run.error && (
                      <p className="font-body text-xs text-secondary">
                        No output or error was recorded for this execution.
                      </p>
                    )}
                  </div>
                </details>
              );
            })}
          </div>
        )}
      </Section>

      <Section title="Customer messages">
        {detail.messages.length === 0 ? (
          <p className="font-body text-sm text-secondary">
            No messages.
          </p>
        ) : (
          <ul className="space-y-3">
            {detail.messages.map((message) => (
              <li
                key={message.id}
                className="border-2 border-secondary p-3"
              >
                <p className="font-mono text-xs uppercase text-secondary">
                  {message.sender_role === "customer"
                    ? "Customer"
                    : "Claims team"}{" "}
                  · {formatDateTime(message.created_at)}
                </p>

                <p className="font-body text-sm text-secondary mt-1 whitespace-pre-wrap">
                  {message.body}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Private staff notes">
        <p className="font-body text-sm text-secondary mb-4">
          Only staff can see these notes.
        </p>

        {detail.notes.length > 0 && (
          <ul className="space-y-3 mb-4">
            {detail.notes.map((note) => (
              <li
                key={note.id}
                className="border-2 border-secondary p-3"
              >
                <p className="font-mono text-xs uppercase text-secondary">
                  {note.staff_name} · {formatDateTime(note.created_at)}
                </p>

                <p className="font-body text-sm text-secondary mt-1 whitespace-pre-wrap">
                  {note.note}
                </p>
              </li>
            ))}
          </ul>
        )}

        <textarea
          rows={3}
          maxLength={2000}
          value={props.noteText}
          onChange={(e) => props.setNoteText(e.target.value)}
          disabled={props.noteBusy}
          placeholder="Write a private note"
          className={INPUT_CLASS}
        />

        <button
          onClick={props.onAddNote}
          disabled={props.noteBusy || !props.noteText.trim()}
          className={`${BUTTON_CLASS} mt-3`}
        >
          {props.noteBusy ? "Saving..." : "Add note"}
        </button>
      </Section>

      <Section title="Tasks">
        {detail.tasks.length === 0 ? (
          <p className="font-body text-sm text-secondary">
            No tasks.
          </p>
        ) : (
          <ul className="space-y-3">
            {detail.tasks.map((task) => (
              <li
                key={task.id}
                className="border-2 border-secondary p-3"
              >
                <p className="font-mono text-xs uppercase text-secondary">
                  {TASK_LABELS[task.task_type] || task.task_type} ·{" "}
                  {task.status}
                </p>

                <p className="font-body text-sm text-secondary mt-1 whitespace-pre-wrap">
                  {task.details}
                </p>

                <p className="font-mono text-xs text-secondary mt-1">
                  {formatDateTime(task.created_at)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="What the customer sees">
        <StatusTimeline entries={detail.history} />
      </Section>

      <Section title="Decision history">
        {detail.decisions.length === 0 ? (
          <p className="font-body text-sm text-secondary">
            No decisions yet.
          </p>
        ) : (
          <ul className="space-y-3">
            {detail.decisions.map((item) => (
              <li
                key={item.id}
                className="border-2 border-secondary p-3"
              >
                <p className="font-body text-sm font-semibold text-secondary">
                  {DECISION_FORMS[item.decision].label}:{" "}
                  {item.prior_status_label} → {item.new_status_label}
                </p>

                <p className="font-mono text-xs text-secondary">
                  {item.staff_name} · {formatDateTime(item.created_at)}
                </p>

                {item.reason && (
                  <p className="font-body text-sm text-secondary mt-2 whitespace-pre-wrap">
                    Internal reason: {item.reason}
                  </p>
                )}

                {item.customer_message && (
                  <p className="font-body text-sm text-secondary mt-2 whitespace-pre-wrap">
                    Sent to customer: {item.customer_message}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Decision">
        {detail.allowed_decisions.length === 0 ? (
          <p className="font-body text-sm text-secondary">
            {noDecisionText}
          </p>
        ) : (
          <div className="space-y-6">
            <div className="flex flex-wrap gap-2">
              {detail.allowed_decisions.map((key) => (
                <button
                  key={key}
                  onClick={() => props.chooseDecision(key)}
                  className={props.decisionButtonClass(key)}
                >
                  {DECISION_FORMS[key].label}
                </button>
              ))}
            </div>

            {form && (
              <div className="space-y-6">
                <div>
                  <label
                    htmlFor="decision-reason"
                    className={LABEL_CLASS}
                  >
                    {form.reasonLabel}
                    {form.reasonRequired ? " *" : ""}
                  </label>

                  <textarea
                    id="decision-reason"
                    rows={3}
                    maxLength={2000}
                    value={props.reason}
                    onChange={(e) =>
                      props.setReason(e.target.value)
                    }
                    disabled={props.deciding}
                    className={INPUT_CLASS}
                  />

                  <p className="font-mono text-xs text-secondary mt-1">
                    Only staff can see this.
                  </p>
                </div>

                {form.showMessage && (
                  <div>
                    <label
                      htmlFor="decision-message"
                      className={LABEL_CLASS}
                    >
                      {form.messageLabel}
                      {form.messageRequired ? " *" : ""}
                    </label>

                    <textarea
                      id="decision-message"
                      rows={3}
                      maxLength={2000}
                      value={props.customerMessage}
                      onChange={(e) =>
                        props.setCustomerMessage(e.target.value)
                      }
                      disabled={props.deciding}
                      className={INPUT_CLASS}
                    />

                    <p className="font-mono text-xs text-secondary mt-1">
                      The customer will see this.
                    </p>
                  </div>
                )}

                <button
                  onClick={props.onDecide}
                  disabled={props.deciding}
                  className={BUTTON_CLASS}
                >
                  {props.deciding
                    ? "Saving..."
                    : `Record: ${form.label}`}
                </button>
              </div>
            )}
          </div>
        )}
      </Section>
    </>
  );
}
