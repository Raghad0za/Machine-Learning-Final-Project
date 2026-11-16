// Small wrapper around the FastAPI endpoints (served under /api on the same domain).
const BASE = import.meta.env.VITE_API_BASE || "/api";

async function call(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  try {
    const res = await fetch(BASE + path, {
      ...options,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    if (!res.ok) {
      const error = new Error(`HTTP ${res.status}`);
      error.status = res.status;
      throw error;
    }
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

const post = (path, body) => call(path, { method: "POST", body: JSON.stringify(body) });

function cleanFilters(filters) {
  const price = parseFloat(filters.max_price_sar);
  return {
    max_price_sar: Number.isFinite(price) && price > 0 ? price : null,
    brew_method: filters.brew_method || null,
    exclude_infused: !!filters.exclude_infused,
  };
}

export const api = {
  recommend: (query, lang, filters, top_k = 5) =>
    post("/recommend", { query, lang, top_k, filters: cleanFilters(filters) }),
  similar: (coffee_id, focus, lang, filters, top_k = 5) =>
    post("/similar", { coffee_id, focus, lang, top_k, filters: cleanFilters(filters) }),
  byProfile: (profile_id, lang, filters, top_k = 5) =>
    post("/recommend/profile", { profile_id, lang, top_k, filters: cleanFilters(filters) }),
  coffees: (q, limit = 8) => call(`/coffees?q=${encodeURIComponent(q)}&limit=${limit}`),
  profiles: (lang) => call(`/profiles?lang=${lang}`),
  health: () => call("/health"),
};
