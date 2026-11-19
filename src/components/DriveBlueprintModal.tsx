import React, { useState } from 'react';
import {
  X,
  HardDrive,
  Search,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
  LogOut,
  RefreshCw,
  FileText,
} from 'lucide-react';
import { User } from 'firebase/auth';
import { DriveBlueprintItem } from '../types/trading';

interface DriveBlueprintModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: User | null;
  onSignIn: () => Promise<void>;
  onSignOut: () => Promise<void>;
  onSearch: (query: string) => Promise<void>;
  driveFiles: DriveBlueprintItem[];
  isLoading: boolean;
  error: string | null;
  onSelectFile: (file: DriveBlueprintItem) => void;
}

export const DriveBlueprintModal: React.FC<DriveBlueprintModalProps> = ({
  isOpen,
  onClose,
  user,
  onSignIn,
  onSignOut,
  onSearch,
  driveFiles,
  isLoading,
  error,
  onSelectFile,
}) => {
  const [searchQuery, setSearchQuery] = useState('OMEGA NIO');
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  if (!isOpen) return null;

  const handleLogin = async () => {
    setIsAuthenticating(true);
    try {
      await onSignIn();
    } catch (e) {
      console.error(e);
    } finally {
      setIsAuthenticating(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      onSearch(searchQuery.trim());
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="px-5 py-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <HardDrive className="w-5 h-5 text-blue-400" />
            <div>
              <h2 className="text-sm font-bold font-mono text-slate-100 uppercase tracking-tight">
                Google Drive Blueprint Sync
              </h2>
              <p className="text-[11px] text-slate-400">
                Connect and sync OMEGA NIO blueprints and Sigma Alpha specifications
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 space-y-4 overflow-y-auto">
          {/* Auth State Box */}
          <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
            {user ? (
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-blue-600/30 border border-blue-500/50 flex items-center justify-center font-bold text-blue-300 text-xs">
                    {user.email ? user.email[0].toUpperCase() : 'U'}
                  </div>
                  <div>
                    <span className="text-xs font-bold text-slate-200 block font-mono">
                      {user.displayName || user.email}
                    </span>
                    <span className="text-[10px] text-emerald-400 flex items-center gap-1 font-mono">
                      <CheckCircle2 className="w-3 h-3" />
                      Google Drive Read-Only Scope Active
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={handleLogin}
                    disabled={isAuthenticating}
                    className="flex items-center gap-1 text-xs font-mono text-blue-400 hover:text-blue-300 transition-colors px-2 py-1 rounded hover:bg-slate-900 border border-slate-800 cursor-pointer"
                    title="Re-authenticate or refresh Drive authorization"
                  >
                    <RefreshCw className={`w-3 h-3 ${isAuthenticating ? 'animate-spin' : ''}`} />
                    <span>Re-Authenticate</span>
                  </button>
                  <button
                    onClick={onSignOut}
                    className="flex items-center gap-1 text-xs font-mono text-slate-400 hover:text-rose-400 transition-colors px-2 py-1 rounded hover:bg-slate-900 border border-slate-800 cursor-pointer"
                  >
                    <LogOut className="w-3 h-3" />
                    <span>Sign Out</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h4 className="text-xs font-bold text-slate-200 font-mono">
                    Google Drive Authorization
                  </h4>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Sign in to allow the app to search for OMEGA NIO blueprint files.
                  </p>
                </div>

                {/* Official Material Google Sign-In Styled Button */}
                <button
                  onClick={handleLogin}
                  disabled={isAuthenticating}
                  className="px-4 py-2 bg-white text-slate-800 font-medium text-xs rounded shadow hover:bg-slate-100 flex items-center gap-2.5 transition-all whitespace-nowrap self-start sm:self-auto cursor-pointer"
                >
                  <svg className="w-4 h-4" viewBox="0 0 48 48">
                    <path
                      fill="#EA4335"
                      d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
                    />
                    <path
                      fill="#4285F4"
                      d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
                    />
                    <path
                      fill="#34A853"
                      d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
                    />
                  </svg>
                  <span>{isAuthenticating ? 'Connecting...' : 'Sign in with Google'}</span>
                </button>
              </div>
            )}
          </div>

          {/* Drive Search Form */}
          <form onSubmit={handleSearchSubmit} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search Google Drive for files (e.g. OMEGA NIO, blueprint)..."
                className="w-full bg-slate-950 border border-slate-800 pl-9 pr-3 py-2 text-xs font-mono rounded text-slate-100 placeholder:text-slate-500 focus:outline-hidden focus:border-blue-500"
              />
            </div>
            <button
              type="submit"
              disabled={isLoading || !user}
              className="px-4 py-2 bg-blue-600 text-white rounded text-xs font-mono font-semibold hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
            >
              {isLoading ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Search className="w-3.5 h-3.5" />
              )}
              <span>Search</span>
            </button>
          </form>

          {/* Error Banner */}
          {error && (
            <div className="p-3 rounded bg-rose-950/40 border border-rose-800/60 text-xs font-mono text-rose-300 flex items-start justify-between gap-3">
              <div className="flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
              <button
                type="button"
                onClick={handleLogin}
                disabled={isAuthenticating}
                className="shrink-0 px-2.5 py-1 bg-rose-900/60 hover:bg-rose-800 text-rose-100 rounded border border-rose-700/60 text-[11px] font-semibold transition-colors cursor-pointer"
              >
                Sign In with Google
              </button>
            </div>
          )}

          {/* File Results List */}
          <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
            <h4 className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
              Search Results ({driveFiles.length})
            </h4>

            {driveFiles.length === 0 ? (
              <div className="p-6 text-center text-xs font-mono text-slate-500 bg-slate-950/60 rounded border border-slate-800">
                {user
                  ? 'No matching files found. Try searching for "OMEGA", "NIO", or "Blueprint".'
                  : 'Please sign in with Google to query your Drive files.'}
              </div>
            ) : (
              driveFiles.map((file) => (
                <div
                  key={file.id}
                  className="p-3 bg-slate-950 rounded border border-slate-800 hover:border-slate-700 transition-colors flex items-center justify-between gap-3 text-xs font-mono"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <FileText className="w-4 h-4 text-slate-400 shrink-0" />
                      <span className="font-bold text-slate-200 truncate">{file.name}</span>
                      {file.isBlueprintMatch && (
                        <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 shrink-0">
                          BLUEPRINT MATCH
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] text-slate-500 block mt-0.5">
                      Modified {new Date(file.modifiedTime).toLocaleDateString()}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => {
                        onSelectFile(file);
                        onClose();
                      }}
                      className="px-2.5 py-1 rounded bg-slate-800 text-slate-200 hover:bg-slate-700 text-[11px] font-semibold transition-colors"
                    >
                      Inspect
                    </button>
                    {file.webViewLink && (
                      <a
                        href={file.webViewLink}
                        target="_blank"
                        rel="noreferrer"
                        className="p-1 rounded text-slate-400 hover:text-blue-400 transition-colors"
                        title="Open in Google Drive"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-5 py-3 bg-slate-950 border-t border-slate-800 flex items-center justify-between text-[11px] font-mono text-slate-400">
          <span>SCOPE: https://www.googleapis.com/auth/drive.readonly</span>
          <button
            onClick={onClose}
            className="px-3 py-1 rounded bg-slate-800 text-slate-200 hover:bg-slate-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
