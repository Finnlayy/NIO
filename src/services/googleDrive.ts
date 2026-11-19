import { DriveBlueprintItem } from '../types/trading';

const DRIVE_API_BASE = 'https://www.googleapis.com/drive/v3';

export async function searchDriveFiles(
  accessToken: string,
  searchQuery: string = 'OMEGA'
): Promise<DriveBlueprintItem[]> {
  if (!accessToken) {
    throw new Error('Access token is required to query Google Drive');
  }

  // Construct query: matches filename using Drive readonly scope
  // Note: 'fullText contains' requires broader write scope (https://www.googleapis.com/auth/drive),
  // whereas 'name contains' works seamlessly with https://www.googleapis.com/auth/drive.readonly.
  const trimmed = (searchQuery || '').trim();
  let q = 'trashed = false';
  if (trimmed) {
    const words = trimmed.split(/\s+/).filter(Boolean);
    if (words.length === 1) {
      const safeWord = words[0].replace(/'/g, "\\'");
      q = `trashed = false and name contains '${safeWord}'`;
    } else if (words.length > 1) {
      const nameClauses = words
        .map((w) => `name contains '${w.replace(/'/g, "\\'")}'`)
        .join(' or ');
      q = `trashed = false and (${nameClauses})`;
    }
  }

  const url = new URL(`${DRIVE_API_BASE}/files`);
  url.searchParams.append('q', q);
  url.searchParams.append(
    'fields',
    'files(id, name, mimeType, modifiedTime, size, description, webViewLink)'
  );
  url.searchParams.append('pageSize', '30');
  url.searchParams.append('orderBy', 'modifiedTime desc');

  const response = await fetch(url.toString(), {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    if (response.status === 401) {
      throw new Error('Google Drive session expired or invalid. Please sign out and sign in with Google again.');
    }
    if (response.status === 403) {
      if (
        errData.error?.message?.toLowerCase().includes('insufficient') ||
        errData.error?.status === 'PERMISSION_DENIED'
      ) {
        throw new Error(
          'Google Drive access scope requires re-authorization. Please sign in with Google to grant drive access.'
        );
      }
    }
    throw new Error(
      errData.error?.message || `Google Drive API error: ${response.status} ${response.statusText}`
    );
  }

  const data = await response.json();
  const files: DriveBlueprintItem[] = (data.files || []).map((file: any) => ({
    id: file.id,
    name: file.name,
    mimeType: file.mimeType,
    modifiedTime: file.modifiedTime,
    size: file.size,
    description: file.description,
    webViewLink: file.webViewLink,
    isBlueprintMatch:
      file.name.toLowerCase().includes('omega') ||
      file.name.toLowerCase().includes('nio') ||
      file.name.toLowerCase().includes('blueprint') ||
      file.name.toLowerCase().includes('sigma') ||
      file.name.toLowerCase().includes('alpha'),
  }));

  return files;
}

export async function fetchFileContent(
  accessToken: string,
  fileId: string,
  mimeType: string
): Promise<string> {
  if (!accessToken) {
    throw new Error('Access token is required');
  }

  // If it's a Google Doc, export as plain text
  if (mimeType === 'application/vnd.google-apps.document') {
    const exportUrl = `${DRIVE_API_BASE}/files/${fileId}/export?mimeType=text/plain`;
    const res = await fetch(exportUrl, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) {
      if (res.status === 401 || res.status === 403) {
        throw new Error('Google Drive access unauthorized. Please sign out and sign in again to grant permissions.');
      }
      throw new Error(`Failed to export Google Doc: ${res.statusText}`);
    }
    return await res.text();
  }

  // Otherwise fetch standard content
  const contentUrl = `${DRIVE_API_BASE}/files/${fileId}?alt=media`;
  const res = await fetch(contentUrl, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!res.ok) {
    if (res.status === 401 || res.status === 403) {
      throw new Error('Google Drive access unauthorized. Please sign out and sign in again to grant permissions.');
    }
    throw new Error(`Failed to fetch file content: ${res.statusText}`);
  }

  return await res.text();
}
