export function getVisiblePages(currentPage, totalPages) {
  if (totalPages <= 0) return [];

  const current = Math.min(Math.max(currentPage, 1), totalPages);
  const visible = new Set([1, totalPages]);

  for (let page = Math.max(1, current - 2); page <= Math.min(totalPages, current + 2); page++) {
    visible.add(page);
  }

  const pages = [...visible].sort((a, b) => a - b);
  return pages.flatMap((page, index) => {
    const previous = pages[index - 1];
    return previous !== undefined && page - previous > 1 ? ["...", page] : [page];
  });
}
