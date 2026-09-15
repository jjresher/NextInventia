const PATENT_PATH_PATTERN = /^\/patentes\/([1-9]\d*)$/;
const ESPACENET_HOSTS = new Set(["worldwide.espacenet.com"]);

export function getSafePatentPath(value) {
  if (typeof value !== "string") return null;
  return PATENT_PATH_PATTERN.test(value) ? value : null;
}

export function getSafeHttpsUrl(value) {
  if (typeof value !== "string") return null;

  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password) return null;
    return url;
  } catch {
    return null;
  }
}

export function getSafeEspacenetUrl(value) {
  const url = getSafeHttpsUrl(value);
  return url && ESPACENET_HOSTS.has(url.hostname) ? url.href : null;
}
