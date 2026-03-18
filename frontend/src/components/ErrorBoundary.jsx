import React from 'react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <main className="paint-bg flex min-h-screen items-center justify-center p-6">
        <div className="max-w-md rounded-xl border-2 border-[#7f1d1d] bg-[#fee2e2] p-6 text-center shadow-lg">
          <h1 className="mb-2 text-lg font-bold text-[#7f1d1d]">
            Algo salió mal
          </h1>
          <p className="mb-4 text-sm text-[#7f1d1d]/80">
            {this.state.error?.message || 'Error inesperado'}
          </p>
          <button
            className="rounded-lg bg-[#7f1d1d] px-4 py-2 text-sm font-semibold text-white hover:bg-[#991b1b]"
            onClick={() => window.location.reload()}
          >
            Recargar página
          </button>
        </div>
      </main>
    );
  }
}
