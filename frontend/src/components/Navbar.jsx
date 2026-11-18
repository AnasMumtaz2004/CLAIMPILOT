import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const CUSTOMER_LINKS = [
  { to: "/customer", label: "Dashboard", end: true },
  { to: "/customer/claims", label: "My claims", end: false },
];

const STAFF_LINKS = [
  { to: "/staff", label: "Dashboard", end: true },
];

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  if (!user) {
    return null;
  }

  const isStaff = user.role !== "customer";
  const links = isStaff ? STAFF_LINKS : CUSTOMER_LINKS;

  function handleLogout() {
    logout();
    navigate(isStaff ? "/staff/login" : "/customer/login");
  }

  function linkClass({ isActive }) {
    const base = "font-body text-sm text-secondary pb-1 border-b-2";
    if (isActive) {
      return `${base} border-accent font-semibold`;
    }
    return `${base} border-transparent`;
  }

  return (
    <header className="w-full bg-white border-b-2 border-secondary">
      <div className="max-w-5xl mx-auto px-6 py-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-8">
          <span className="font-display text-xl uppercase tracking-tight text-secondary">
            CLAIMPILOT
          </span>
          <nav className="flex gap-6">
            {links.map((link) => (
              <NavLink key={link.to} to={link.to} end={link.end} className={linkClass}>
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-4">
          <span className="font-mono text-xs text-secondary">{user.full_name}</span>
          <button
            onClick={handleLogout}
            className="bg-secondary hover:bg-secondary text-white font-body font-semibold text-xs rounded-none py-2 px-4 transition-colors cursor-pointer"
          >
            Log out
          </button>
        </div>
      </div>
    </header>
  );
}