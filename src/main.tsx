import React, { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import './index.css';

// Additional runtime defense against browser extension errors (e.g. MetaMask inpage.js)
if (typeof window !== 'undefined') {
  const isExtensionError = (err: unknown, source?: string) => {
    const errorObj = err as { message?: string; filename?: string; stack?: string } | null;
    const msg = errorObj?.message || (typeof err === 'string' ? err : '');
    const src = source || errorObj?.filename || errorObj?.stack || '';
    return (
      msg.includes('MetaMask') ||
      msg.includes('Failed to connect to MetaMask') ||
      src.includes('chrome-extension://') ||
      src.includes('moz-extension://') ||
      src.includes('safari-extension://') ||
      src.includes('inpage.js')
    );
  };

  window.addEventListener(
    'error',
    (event) => {
      if (isExtensionError(event.error, event.filename)) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    },
    true
  );

  window.addEventListener(
    'unhandledrejection',
    (event) => {
      if (isExtensionError(event.reason)) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    },
    true
  );
}

// Resilient Root Error Boundary
class RootErrorBoundary extends (React.Component as new (...args: any[]) => any) {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.warn('[RootErrorBoundary caught error]', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#07090E] text-[#E2E8F0] p-6 flex flex-col items-center justify-center font-mono">
          <div className="max-w-md w-full bg-[#0C1017] border border-[#1B2230] p-5 rounded space-y-3">
            <h2 className="text-sm font-bold text-[#F23645] uppercase">Terminal Error Detected</h2>
            <p className="text-xs text-[#8B95A5]">
              {this.state.error?.message || 'An unexpected rendering error occurred.'}
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="px-3 py-1.5 bg-[#00E5FF]/20 text-[#00E5FF] hover:bg-[#00E5FF]/30 border border-[#00E5FF]/40 text-xs font-semibold rounded"
            >
              Reload Terminal
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RootErrorBoundary>
      <App />
    </RootErrorBoundary>
  </StrictMode>
);
