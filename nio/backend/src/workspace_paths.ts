import { resolve } from 'path';
import { getWorkspaceRoot } from './cody_stats';

export function getLibraryRoot(): string {
  return resolve(getWorkspaceRoot(), '.nio', 'library');
}

export function getLibraryArchiveDir(): string {
  return resolve(getLibraryRoot(), 'archive');
}

export function getLibraryLedgerDir(): string {
  return resolve(getLibraryRoot(), 'ledger');
}

export function getCrossReviewDir(): string {
  return resolve(getLibraryRoot(), 'cross-review');
}

export function getTemplatesDir(): string {
  return resolve(process.cwd(), 'library', 'templates');
}
