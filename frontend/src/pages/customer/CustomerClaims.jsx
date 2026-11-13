import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Navbar from "../../components/Navbar";
import ClaimStatus from "../../components/ClaimStatus";
import StatusTimeline from "../../components/StatusTimeline";
import DocumentUpload from "../../components/DocumentUpload";
import {getClaimConfig,listClaims,listDocuments,listHistory,listMessages,listPolicies,postMessage,respondToInfoRequest,} from "../../services/claimService";

const CARD_CLASS = "bg-white border-2 border-secondary rounded-none p-6";
const BUTTON_CLASS =
  "bg-secondary hover:bg-black text-white font-body font-semibold text-sm rounded-none py-2.5 px-5 transition-colors disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer";
const ERROR_CLASS = "bg-accent border-l-2 border-secondary p-3 font-mono text-xs text-black";

function ClaimDetail({ claim, policy, config, onClaimChanged }) {
  const [history, setHistory] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [messageText, setMessageText] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState("");
  const [responding, setResponding] = useState(false);
  const [respondError, setRespondError] = useState("");

  const lineConfig = config.lines[claim.line];
  const fields = lineConfig ? lineConfig.fields : [];
  const documentTypes = lineConfig ? lineConfig.document_types : [];

  async function loadDetail() {
    setLoading(true);
    setLoadError("");

    try {
      const [historyData, documentData, messageData] = await Promise.all([
        listHistory(claim.id),
        listDocuments(claim.id),
        listMessages(claim.id),
      ]);
      setHistory(historyData);
      setDocuments(documentData);
      setMessages(messageData);
    } catch (error) {
      setLoadError(error.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDetail();
  }, [claim.id]);

  async function handleSend() {
    const text = messageText.trim();
    if (!text) {
      return;
    }

    setSending(true);
    setSendError("");

    try {
      const created = await postMessage(claim.id, text);
      setMessages((previous) => [...previous, created]);
      setMessageText("");
    } catch (error) {
      setSendError(error.message);
    } finally {
      setSending(false);
    }
  }

  async function handleRespond() {
    setResponding(true);
    setRespondError("");

    try {
      // Tell the claims team we are done, then show the new status
      const updatedClaim = await respondToInfoRequest(claim.id);
      onClaimChanged(updatedClaim);
      await loadDetail();
    } catch (error) {
      setRespondError(error.message);
    } finally {
      setResponding(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className={CARD_CLASS}>
        <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
          <div>
            <h2 className="font-display text-2xl uppercase text-secondary">{claim.claim_number}</h2>
            <p className="font-mono text-xs text-secondary mt-1">
              {lineConfig ? lineConfig.label : claim.line}
              {policy ? ` · ${policy.policy_number}` : ""}
            </p>
          </div>
          <ClaimStatus
            status={claim.status}
            label={claim.status_label}
            description={claim.status_description}
          />
        </div>

        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 font-body text-sm text-secondary">
          <div>
            <dt className="font-mono text-xs uppercase">Date of loss</dt>
            <dd>{claim.loss_date ? new Date(claim.loss_date).toLocaleDateString() : "-"}</dd>
          </div>
          <div>
            <dt className="font-mono text-xs uppercase">Claimed amount</dt>
            <dd>{claim.claimed_amount !== null ? claim.claimed_amount.toLocaleString("en-IN") : "-"}</dd>
          </div>
          {fields.map((field) => (
            <div key={field.name}>
              <dt className="font-mono text-xs uppercase">{field.label}</dt>
              <dd>{(claim.details[field.name] || "-").replace(/_/g, " ")}</dd>
            </div>
          ))}
          <div className="sm:col-span-2">
            <dt className="font-mono text-xs uppercase">What happened</dt>
            <dd>{claim.description || "-"}</dd>
          </div>
        </dl>
      </section>

      {claim.status === "info_required" && (
        <section className="bg-accent border-2 border-secondary rounded-none p-6">
          <h3 className="font-display text-xl uppercase text-secondary mb-2">We need more information</h3>
          <p className="font-body text-sm text-secondary mb-4">
            Read the latest message from the claims team below. Upload any documents they asked for, then click the
            button so we know you are done.
          </p>
          {respondError && <div className={`${ERROR_CLASS} mb-4 bg-white`}>{respondError}</div>}
          <button onClick={handleRespond} disabled={responding} className={BUTTON_CLASS}>
            {responding ? "Sending..." : "I have sent everything"}
          </button>
        </section>
      )}

      {loading && <p className="font-body text-sm text-secondary">Loading details...</p>}

      {loadError && (
        <div className={ERROR_CLASS}>
          <p>{loadError}</p>
          <button onClick={loadDetail} className="underline mt-2 cursor-pointer">
            Retry
          </button>
        </div>
      )}

      {!loading && !loadError && (
        <>
          <section className={CARD_CLASS}>
            <h3 className="font-display text-xl uppercase text-secondary mb-6">Progress</h3>
            <StatusTimeline entries={history} />
          </section>

          <section className={CARD_CLASS}>
            <h3 className="font-display text-xl uppercase text-secondary mb-6">Documents</h3>
            <DocumentUpload
              claimId={claim.id}
              documentTypes={documentTypes}
              documents={documents}
              onUploaded={(doc) => setDocuments((previous) => [doc, ...previous])}
              disabled={claim.status !== "info_required"}
            />
          </section>

          <section className={CARD_CLASS}>
            <h3 className="font-display text-xl uppercase text-secondary mb-6">Messages</h3>

            {messages.length === 0 ? (
              <p className="font-body text-sm text-secondary mb-4">No messages yet.</p>
            ) : (
              <ul className="space-y-3 mb-4">
                {messages.map((message) => (
                  <li key={message.id} className="border-2 border-secondary p-3">
                    <p className="font-mono text-xs uppercase text-secondary">
                      {message.sender_role === "customer" ? "You" : "Claims team"} ·{" "}
                      {new Date(message.created_at).toLocaleString()}
                    </p>
                    <p className="font-body text-sm text-secondary mt-1 whitespace-pre-wrap">{message.body}</p>
                  </li>
                ))}
              </ul>
            )}

            <textarea
              rows={3}
              maxLength={2000}
              value={messageText}
              onChange={(e) => setMessageText(e.target.value)}
              disabled={sending}
              placeholder="Write a message to the claims team"
              className="w-full bg-white text-black font-body text-sm border-2 border-black rounded-none px-3 py-3 placeholder:text-secondary focus:outline-none focus:ring-2 focus:ring-secondary focus:ring-offset-2"
            />
            {sendError && <div className={`${ERROR_CLASS} mt-3`}>{sendError}</div>}
            <button onClick={handleSend} disabled={sending || !messageText.trim()} className={`${BUTTON_CLASS} mt-3`}>
              {sending ? "Sending..." : "Send message"}
            </button>
          </section>
        </>
      )}
    </div>
  );
}

export default function CustomerClaims() {
  const [config, setConfig] = useState(null);
  const [policies, setPolicies] = useState([]);
  const [claims, setClaims] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [selectedId, setSelectedId] = useState(null);

  async function loadAll() {
    setLoading(true);
    setLoadError("");

    try {
      const [configData, policyData, claimData] = await Promise.all([
        getClaimConfig(),
        listPolicies(),
        listClaims(),
      ]);
      const submitted = claimData.filter((claim) => claim.status !== "draft");
      setConfig(configData);
      setPolicies(policyData);
      setClaims(submitted);
      if (submitted.length > 0) {
        setSelectedId((current) => current || submitted[0].id);
      }
    } catch (error) {
      setLoadError(error.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  // Replace one claim in the list after its status changed
  function handleClaimChanged(updatedClaim) {
    setClaims((previous) => {
      const newList = [];
      for (const claim of previous) {
        if (claim.id === updatedClaim.id) {
          newList.push(updatedClaim);
        } else {
          newList.push(claim);
        }
      }
      return newList;
    });
  }

  const selected = claims.find((claim) => claim.id === selectedId);
  const selectedPolicy = selected ? policies.find((policy) => policy.id === selected.policy_id) : null;

  return (
    <div className="min-h-screen w-full bg-primary">
      <Navbar />

      <main className="max-w-5xl mx-auto px-6 py-10">
        <h1 className="font-display text-4xl uppercase text-secondary mb-8">My claims</h1>

        {loading && <p className="font-body text-sm text-secondary">Loading...</p>}

        {loadError && (
          <div className={ERROR_CLASS}>
            <p>{loadError}</p>
            <button onClick={loadAll} className="underline mt-2 cursor-pointer">
              Retry
            </button>
          </div>
        )}

        {!loading && !loadError && claims.length === 0 && (
          <div className={CARD_CLASS}>
            <p className="font-body text-sm text-secondary">
              You have not submitted any claims yet.{" "}
              <Link to="/customer" className="underline underline-offset-4">
                Start one from the dashboard.
              </Link>
            </p>
          </div>
        )}

        {!loading && !loadError && claims.length > 0 && config && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <ul className="md:col-span-1 space-y-3 self-start">
              {claims.map((claim) => (
                <li key={claim.id}>
                  <button
                    onClick={() => setSelectedId(claim.id)}
                    className={`w-full text-left border-2 border-secondary rounded-none p-4 cursor-pointer ${
                      claim.id === selectedId ? "bg-accent" : "bg-white"
                    }`}
                  >
                    <p className="font-body text-sm font-semibold text-secondary">{claim.claim_number}</p>
                    <p className="font-mono text-xs text-secondary mt-1">{claim.status_label}</p>
                  </button>
                </li>
              ))}
            </ul>

            <div className="md:col-span-2">
              {selected && (
                <ClaimDetail
                  key={selected.id}
                  claim={selected}
                  policy={selectedPolicy}
                  config={config}
                  onClaimChanged={handleClaimChanged}
                />
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}