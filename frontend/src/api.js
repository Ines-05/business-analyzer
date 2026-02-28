export async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload?.detail || payload?.message || "Request failed.";
    throw new Error(detail);
  }
  return payload;
}

export function getAnalyses(limit = 20) {
  return fetchJson(`/api/analyses?limit=${limit}`);
}

export function getAnalysisResult(analysisId) {
  return fetchJson(`/api/analyses/${analysisId}/result`);
}

export function analyzeFile({ companyName, file }) {
  const formData = new FormData();
  formData.append("company_name", companyName || "");
  formData.append("file", file);
  return fetchJson("/api/analyze", { method: "POST", body: formData });
}

export function getRawRows(analysisId) {
  return fetchJson(`/api/analyses/${analysisId}/raw`);
}

export function getAnalysisSteps() {
  return fetchJson("/api/analysis-steps");
}
