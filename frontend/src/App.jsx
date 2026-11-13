import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import CustomerLogin from "./pages/customer/CustomerLogin";
import CustomerDashboard from "./pages/customer/CustomerDashboard";
import CustomerClaims from "./pages/customer/CustomerClaims";
import StaffLogin from "./pages/staff/StaffLogin";
import StaffDashboard from "./pages/staff/StaffDashboard";
import ClaimReview from "./pages/staff/ClaimReview";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/customer/login" replace />} />
          <Route path="/customer/login" element={<CustomerLogin />} />
          <Route path="/staff/login" element={<StaffLogin />} />
          <Route
            path="/customer"
            element={
              <ProtectedRoute area="customer">
                <CustomerDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/customer/claims"
            element={
              <ProtectedRoute area="customer">
                <CustomerClaims />
              </ProtectedRoute>
            }
          />
          <Route
            path="/staff"
            element={
              <ProtectedRoute area="staff">
                <StaffDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/staff/claims/:claimId"
            element={
              <ProtectedRoute area="staff">
                <ClaimReview />
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}