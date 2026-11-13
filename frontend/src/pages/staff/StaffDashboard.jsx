import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import Navbar from "../../components/Navbar";
import { getStaffDashboard, listStaffClaims } from "../../services/claimService";

const TABS = [
  { value: "queue", label: "Queue" },
  { value: "waiting", label: "Waiting for customer" },
  { value: "escalated", label: "Escalated" },
  { value: "history", label: "History" },
];

const LINE_OPTIONS = [
  { value: "", label: "All lines" },
  { value: "health", label: "Health" },
  { value: "private_vehicle", label: "Private vehicle" },
  { value: "commercial", label: "Commercial" },
  { value: "home", label: "Home" },
];

const TASK_LABELS = {
  info_request: "Waiting for customer",
  specialist_escalation: "Specialist review",
};

const CARD_CLASS = "bg-white border-2 border-secondary rounded-none p-6";
const ERROR_CLASS = "bg-accent border-l-2 border-secondary p-3 font-mono text-xs text-black";
const INPUT_CLASS =
  "bg-white text-black font-body text-sm border-2 border-black rounded-none px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-secondary focus:ring-offset-2";

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

function StatCard({ label, value }) {
  return (
    <div className={CARD_CLASS}>
      <p className="font-mono text-xs uppercase text-secondary">{label}</p>
      <p className="font-display text-4xl text-secondary mt-2">{value}</p>
    </div>
  );
}

export default function StaffDashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [dashError, setDashError] = useState("");

  const [view, setView] = useState("queue");
  const [line, setLine] = useState("");
  const [searchText, setSearchText] = useState("");
  const [search, setSearch] = useState("");

  const [claims, setClaims] = useState([]);
  const [claimsLoading, setClaimsLoading] = useState(true);
  const [claimsError, setClaimsError] = useState("");

  // Used to ignore answers from older requests
  const requestIdRef = useRef(0);

  async function loadDashboard() {
    setDashError("");

    try {
      const data = await getStaffDashboard();
      setDashboard(data);
    } catch (error) {
      setDashError(error.message);
    }
  }

  async function loadClaims() {
    requestIdRef.current += 1;
    const myRequestId = requestIdRef.current;

    setClaimsLoading(true);
    setClaimsError("");

    try {
      const data = await listStaffClaims(view, line, search);

      // A newer request was started, so this answer is out of date
      if (myRequestId !== requestIdRef.current) {
        return;
      }

      setClaims(data);
    } catch (error) {
      if (myRequestId !== requestIdRef.current) {
        return;
      }
      setClaimsError(error.message);
    } finally {
      if (myRequestId === requestIdRef.current) {
        setClaimsLoading(false);
      }
    }
  }

  useEffect(() => {
    loadDashboard();
  }, []);

  // Wait a little after typing before searching
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchText.trim());
    }, 400);

    return () => {
      clearTimeout(timer);
    };
  }, [searchText]);

  useEffect(() => {
    loadClaims();
  }, [view, line, search]);

  function tabClass(tabValue) {
    const base = "font-body text-sm text-secondary px-4 py-2 border-2 border-secondary cursor-pointer";
    if (tabValue === view) {
      return `${base} bg-accent font-semibold`;
    }
    return `${base} bg-white`;
  }

  return (
    <div className="min-h-screen w-full bg-accent/30">
      <Navbar />

      <main className="max-w-6xl mx-auto px-6 py-10 space-y-8">
        <h1 className="font-display text-4xl uppercase text-secondary">Staff dashboard</h1>

        {dashError && (
          <div className={ERROR_CLASS}>
            <p>{dashError}</p>
            <button onClick={loadDashboard} className="underline mt-2 cursor-pointer">
              Retry
            </button>
          </div>
        )}

        {dashboard && (
          <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="In queue" value={dashboard.queue_count} />
            <StatCard label="Waiting for customer" value={dashboard.waiting_count} />
            <StatCard label="Escalated" value={dashboard.escalated_count} />
            <StatCard label="Decided" value={dashboard.decided_count} />
          </section>
        )}

        <section className={CARD_CLASS}>
          <div className="flex flex-wrap gap-2 mb-6">
            {TABS.map((tab) => (
              <button key={tab.value} onClick={() => setView(tab.value)} className={tabClass(tab.value)}>
                {tab.label}
              </button>
            ))}
          </div>

          <div className="flex flex-col sm:flex-row gap-3 mb-6">
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Search claim number, customer or policy"
              className={`${INPUT_CLASS} flex-1`}
            />
            <select value={line} onChange={(e) => setLine(e.target.value)} className={INPUT_CLASS}>
              {LINE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {claimsLoading && <p className="font-body text-sm text-secondary">Loading...</p>}

          {claimsError && (
            <div className={ERROR_CLASS}>
              <p>{claimsError}</p>
              <button onClick={loadClaims} className="underline mt-2 cursor-pointer">
                Retry
              </button>
            </div>
          )}

          {!claimsLoading && !claimsError && claims.length === 0 && (
            <p className="font-body text-sm text-secondary">No claims here.</p>
          )}

          {!claimsLoading && !claimsError && claims.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left font-body text-sm text-secondary">
                <thead>
                  <tr className="border-b-2 border-secondary font-mono text-xs uppercase">
                    <th className="py-2 pr-4">Claim</th>
                    <th className="py-2 pr-4">Customer</th>
                    <th className="py-2 pr-4">Policy</th>
                    <th className="py-2 pr-4">Amount</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Submitted</th>
                    <th className="py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {claims.map((claim) => (
                    <tr key={claim.id} className="border-b border-secondary/30">
                      <td className="py-3 pr-4 font-semibold">{claim.claim_number}</td>
                      <td className="py-3 pr-4">{claim.customer_name}</td>
                      <td className="py-3 pr-4">{claim.policy_number}</td>
                      <td className="py-3 pr-4">{formatMoney(claim.claimed_amount)}</td>
                      <td className="py-3 pr-4">
                        <span className="inline-block bg-primary border-2 border-secondary px-2 py-0.5 font-mono text-xs uppercase">
                          {claim.status_label}
                        </span>
                      </td>
                      <td className="py-3 pr-4">{formatDate(claim.submitted_at)}</td>
                      <td className="py-3">
                        <Link to={`/staff/claims/${claim.id}`} className="underline underline-offset-4">
                          Review
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {dashboard && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <section className={CARD_CLASS}>
              <h2 className="font-display text-xl uppercase text-secondary mb-4">Open tasks</h2>
              {dashboard.open_tasks.length === 0 ? (
                <p className="font-body text-sm text-secondary">No open tasks.</p>
              ) : (
                <ul className="space-y-3">
                  {dashboard.open_tasks.map((task) => (
                    <li key={task.id} className="border-2 border-secondary p-3">
                      <p className="font-mono text-xs uppercase text-secondary">
                        {TASK_LABELS[task.task_type] || task.task_type}
                      </p>
                      <Link
                        to={`/staff/claims/${task.claim_id}`}
                        className="font-body text-sm font-semibold text-secondary underline underline-offset-4"
                      >
                        {task.claim_number}
                      </Link>
                      <p className="font-mono text-xs text-secondary mt-1">{formatDateTime(task.created_at)}</p>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className={CARD_CLASS}>
              <h2 className="font-display text-xl uppercase text-secondary mb-4">Recent status changes</h2>
              {dashboard.recent_activity.length === 0 ? (
                <p className="font-body text-sm text-secondary">Nothing yet.</p>
              ) : (
                <ul className="space-y-3">
                  {dashboard.recent_activity.map((item) => (
                    <li key={item.id} className="border-2 border-secondary p-3">
                      <Link
                        to={`/staff/claims/${item.claim_id}`}
                        className="font-body text-sm font-semibold text-secondary underline underline-offset-4"
                      >
                        {item.claim_number}
                      </Link>
                      <p className="font-body text-sm text-secondary">{item.label}</p>
                      <p className="font-mono text-xs text-secondary mt-1">{formatDateTime(item.created_at)}</p>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}