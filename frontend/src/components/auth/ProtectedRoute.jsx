import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../../authContext';
import { LoadingState } from '../ui';

export function ProtectedRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="auth-page">
        <LoadingState message="Checking session…" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

export function PublicOnlyRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="auth-page">
        <LoadingState message="Loading…" />
      </div>
    );
  }

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}
