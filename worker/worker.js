// Stopline sign-in + sync API. Static pages are served from ./dist by Cloudflare;
// only /api/* reaches this code.
const COOKIE = 'sl_sess';
const SESSION_DAYS = 30;
const MAX_DATA = 256 * 1024; // 256 KB per user
let jwksCache = { keys: null, exp: 0 };

const HSTS = 'max-age=31536000; includeSubDomains';
const json = (body, status = 200, headers = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store',
      'Strict-Transport-Security': HSTS,
      ...headers,
    },
  });

const b64urlToBytes = (s) => {
  s = s.replace(/-/g, '+').replace(/_/g, '/');
  while (s.length % 4) s += '=';
  return Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
};
const b64urlJSON = (s) => JSON.parse(new TextDecoder().decode(b64urlToBytes(s)));

async function googleKeys() {
  if (jwksCache.keys && Date.now() < jwksCache.exp) return jwksCache.keys;
  const r = await fetch('https://www.googleapis.com/oauth2/v3/certs');
  if (!r.ok) throw new Error('jwks fetch failed');
  const { keys } = await r.json();
  const m = /max-age=(\d+)/.exec(r.headers.get('Cache-Control') || '');
  jwksCache = { keys, exp: Date.now() + (m ? +m[1] : 3600) * 1000 };
  return keys;
}

// Verify a Google Identity Services ID token (RS256) without any libraries.
async function verifyGoogleToken(token, clientId) {
  const parts = String(token || '').split('.');
  if (parts.length !== 3) return null;
  const [h, p, sig] = parts;
  const header = b64urlJSON(h);
  if (header.alg !== 'RS256') return null;
  const jwk = (await googleKeys()).find((k) => k.kid === header.kid);
  if (!jwk) return null;
  const key = await crypto.subtle.importKey('jwk', jwk, { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify']);
  const ok = await crypto.subtle.verify('RSASSA-PKCS1-v1_5', key, b64urlToBytes(sig), new TextEncoder().encode(h + '.' + p));
  if (!ok) return null;
  const c = b64urlJSON(p);
  const now = Math.floor(Date.now() / 1000);
  if (c.aud !== clientId) return null;
  if (c.iss !== 'accounts.google.com' && c.iss !== 'https://accounts.google.com') return null;
  if (!c.exp || c.exp < now - 60) return null;
  if (!c.sub || !c.email || c.email_verified === false) return null;
  return c;
}

const getCookie = (req, name) => {
  const m = (req.headers.get('Cookie') || '').match(new RegExp('(?:^|;\\s*)' + name + '=([^;]+)'));
  return m ? m[1] : null;
};
const sessionCookie = (id, maxAge) =>
  `${COOKIE}=${id}; Path=/api; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`;

async function currentUser(req, env) {
  const id = getCookie(req, COOKIE);
  if (!id) return null;
  const row = await env.DB.prepare(
    'SELECT u.sub, u.email FROM sessions s JOIN users u ON u.sub = s.sub WHERE s.id = ? AND s.expires_at > ?'
  ).bind(id, Date.now()).first();
  return row ? { ...row, sid: id } : null;
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const path = url.pathname.replace(/^\/api\/?/, '');
    const method = req.method;

    try {
      if (path === 'config' && method === 'GET') {
        return json({ clientId: env.GOOGLE_CLIENT_ID || '' }, 200, { 'Cache-Control': 'public, max-age=300' });
      }
      if (!env.GOOGLE_CLIENT_ID || !env.DB) return json({ error: 'accounts disabled' }, 404);

      // Basic CSRF guard: writes must come from the site's own script, same origin.
      if (method !== 'GET') {
        const origin = req.headers.get('Origin');
        if (req.headers.get('X-Requested-With') !== 'sizeup' || (origin && origin !== url.origin)) {
          return json({ error: 'forbidden' }, 403);
        }
      }

      if (path === 'login' && method === 'POST') {
        const { credential } = await req.json().catch(() => ({}));
        const claims = await verifyGoogleToken(credential, env.GOOGLE_CLIENT_ID).catch(() => null);
        if (!claims) return json({ error: 'invalid token' }, 401);
        const now = Date.now();
        await env.DB.prepare(
          'INSERT INTO users (sub, email, data, created_at, updated_at) VALUES (?, ?, NULL, ?, ?) ' +
          'ON CONFLICT(sub) DO UPDATE SET email = excluded.email, updated_at = excluded.updated_at'
        ).bind(claims.sub, claims.email, now, now).run();
        const sid = crypto.randomUUID() + crypto.randomUUID().replace(/-/g, '');
        const maxAge = SESSION_DAYS * 86400;
        await env.DB.batch([
          env.DB.prepare('DELETE FROM sessions WHERE expires_at < ?').bind(now),
          env.DB.prepare('INSERT INTO sessions (id, sub, expires_at) VALUES (?, ?, ?)').bind(sid, claims.sub, now + maxAge * 1000),
        ]);
        return json({ email: claims.email }, 200, { 'Set-Cookie': sessionCookie(sid, maxAge) });
      }

      const user = await currentUser(req, env);
      if (path === 'me' && method === 'GET') return json({ email: user ? user.email : null });

      if (!user) return json({ error: 'not signed in' }, 401);

      if (path === 'logout' && method === 'POST') {
        await env.DB.prepare('DELETE FROM sessions WHERE id = ?').bind(user.sid).run();
        return json({ ok: true }, 200, { 'Set-Cookie': sessionCookie('', 0) });
      }

      if (path === 'data' && method === 'GET') {
        const row = await env.DB.prepare('SELECT data FROM users WHERE sub = ?').bind(user.sub).first();
        return json({ data: row && row.data ? JSON.parse(row.data) : null });
      }

      if (path === 'data' && method === 'PUT') {
        const text = await req.text();
        if (text.length > MAX_DATA) return json({ error: 'too large' }, 413);
        let body;
        try { body = JSON.parse(text); } catch { return json({ error: 'bad json' }, 400); }
        if (!body || typeof body.data !== 'object') return json({ error: 'bad data' }, 400);
        await env.DB.prepare('UPDATE users SET data = ?, updated_at = ? WHERE sub = ?')
          .bind(JSON.stringify(body.data), Date.now(), user.sub).run();
        return json({ ok: true });
      }

      if (path === 'account' && method === 'DELETE') {
        await env.DB.batch([
          env.DB.prepare('DELETE FROM sessions WHERE sub = ?').bind(user.sub),
          env.DB.prepare('DELETE FROM users WHERE sub = ?').bind(user.sub),
        ]);
        return json({ ok: true }, 200, { 'Set-Cookie': sessionCookie('', 0) });
      }

      return json({ error: 'not found' }, 404);
    } catch (e) {
      return json({ error: 'server error' }, 500);
    }
  },
};
