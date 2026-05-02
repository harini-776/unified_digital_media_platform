import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const PREFIX = "/api/v1";

export const TOKEN_KEY = "tm_token";
export const USER_KEY = "tm_user";

// Custom event so the Navbar / route guards re-render after login/logout
// in the same tab. (The native `storage` event only fires in *other* tabs.)
export const AUTH_EVENT = "tm:auth-change";

export interface AuthUser {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

const isBrowser = () => typeof window !== "undefined";

function emitAuthChange() {
  if (isBrowser()) {
    window.dispatchEvent(new CustomEvent(AUTH_EVENT));
  }
}

export function getToken(): string | null {
  if (!isBrowser()) return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getUser(): AuthUser | null {
  if (!isBrowser()) return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function isAuthed(): boolean {
  return getToken() !== null;
}

function setSession(token: string, user: AuthUser) {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  emitAuthChange();
}

export function clearSession() {
  if (!isBrowser()) return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
  emitAuthChange();
}

// Bare axios instance for /auth endpoints — does NOT use the main client's
// interceptors (we don't want a 401 on login to redirect to /login again).
const authClient = axios.create({ baseURL: API_BASE });

export async function register(email: string, password: string): Promise<AuthUser> {
  const { data } = await authClient.post<AuthUser>(`${PREFIX}/auth/register`, {
    email,
    password,
  });
  return data;
}

export async function login(email: string, password: string): Promise<AuthUser> {
  // OAuth2PasswordRequestForm expects x-www-form-urlencoded with `username`,
  // not JSON. The API accepts an email in the username field — see auth.py.
  const form = new URLSearchParams();
  form.set("username", email);
  form.set("password", password);

  const { data: tokenResp } = await authClient.post<LoginResponse>(
    `${PREFIX}/auth/login`,
    form,
    { headers: { "Content-Type": "application/x-www-form-urlencoded" } },
  );

  // Fetch the user profile so we can cache it alongside the token.
  const { data: user } = await authClient.get<AuthUser>(`${PREFIX}/auth/me`, {
    headers: { Authorization: `Bearer ${tokenResp.access_token}` },
  });

  setSession(tokenResp.access_token, user);
  return user;
}

export function logout() {
  clearSession();
}
