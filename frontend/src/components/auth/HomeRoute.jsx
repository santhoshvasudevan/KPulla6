import { Navigate } from 'react-router-dom';
import { useAuth } from '../../authContext';
import { LoadingState } from '../ui';
import Landing from '../../pages/Landing';

export function HomeRoute() {
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

  return <Landing />;
}
