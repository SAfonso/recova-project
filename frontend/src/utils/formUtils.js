/**
 * Extrae el form_id de una URL de Google Forms o devuelve el string tal cual
 * si ya es un ID directo.
 *
 * Ejemplos:
 *   https://docs.google.com/forms/d/1BxEfoo123/viewform  → "1BxEfoo123"
 *   https://docs.google.com/forms/d/1BxEfoo123/edit      → "1BxEfoo123"
 *   1BxEfoo123                                           → "1BxEfoo123"
 */
export function extractFormId(urlOrId) {
  if (!urlOrId) return '';
  const match = urlOrId.match(/\/forms\/d\/([a-zA-Z0-9_-]+)/);
  return match ? match[1] : urlOrId.trim();
}
