import { supabase } from '../supabaseClient';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? '';

export async function authFetch(path, body) {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token ?? '';
  return fetch(`${BACKEND_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
}
