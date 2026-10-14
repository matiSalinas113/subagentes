"use strict";

const loginPanel = document.querySelector("#login-panel");
const accountPanel = document.querySelector("#account-panel");
const form = document.querySelector("#login-form");
const username = document.querySelector("#username");
const password = document.querySelector("#password");
const usernameError = document.querySelector("#username-error");
const passwordError = document.querySelector("#password-error");
const formStatus = document.querySelector("#form-status");
const loginButton = document.querySelector("#login-button");
const accountUsername = document.querySelector("#account-username");
const accountStatus = document.querySelector("#account-status");
const logoutButton = document.querySelector("#logout-button");

function setFieldError(input, errorElement, message) {
  input.setAttribute("aria-invalid", String(Boolean(message)));
  errorElement.textContent = message;
}

function clearErrors() {
  setFieldError(username, usernameError, "");
  setFieldError(password, passwordError, "");
}

function setStatus(element, message, state = "") {
  element.textContent = message;
  element.dataset.state = state;
}

function showLogin() {
  accountPanel.hidden = true;
  loginPanel.hidden = false;
  username.focus();
}

function showAccount(name) {
  accountUsername.textContent = name;
  loginPanel.hidden = true;
  accountPanel.hidden = false;
  setStatus(accountStatus, "Sesión iniciada correctamente.", "success");
  logoutButton.focus();
}

async function request(path, options = {}) {
  return fetch(path, { credentials: "same-origin", ...options });
}

async function checkSession() {
  try {
    const response = await request("/api/auth/me");
    if (!response.ok) return;
    const user = await response.json();
    if (typeof user.username === "string") showAccount(user.username);
  } catch {
    // The login form remains available if the server cannot be reached.
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (loginButton.disabled) return;

  clearErrors();
  setStatus(formStatus, "", "");
  let firstInvalid = null;
  if (!username.value.trim()) {
    setFieldError(username, usernameError, "Introduce tu nombre de usuario.");
    firstInvalid = username;
  }
  if (!password.value) {
    setFieldError(password, passwordError, "Introduce tu contraseña.");
    firstInvalid ||= password;
  }
  if (firstInvalid) {
    setStatus(formStatus, "Revisa los campos indicados.", "error");
    firstInvalid.focus();
    return;
  }

  loginButton.disabled = true;
  loginButton.textContent = "Iniciando sesión…";
  setStatus(formStatus, "Comprobando tus datos…", "");
  try {
    const response = await request("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username.value.trim(), password: password.value }),
    });
    if (!response.ok) {
      setStatus(formStatus, "No se pudo iniciar sesión. Revisa tus datos e inténtalo de nuevo.", "error");
      password.focus();
      return;
    }
    form.reset();
    const session = await request("/api/auth/me");
    if (!session.ok) throw new Error("session unavailable");
    const user = await session.json();
    if (typeof user.username !== "string") throw new Error("invalid session response");
    showAccount(user.username);
  } catch {
    setStatus(formStatus, "No se pudo iniciar sesión. Inténtalo de nuevo más tarde.", "error");
  } finally {
    loginButton.disabled = false;
    loginButton.textContent = "Iniciar sesión";
  }
});

logoutButton.addEventListener("click", async () => {
  if (logoutButton.disabled) return;
  logoutButton.disabled = true;
  setStatus(accountStatus, "Cerrando sesión…", "");
  try {
    const response = await request("/api/auth/logout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (!response.ok) throw new Error("logout failed");
    showLogin();
    setStatus(formStatus, "Sesión cerrada correctamente.", "success");
  } catch {
    setStatus(accountStatus, "No se pudo cerrar la sesión. Inténtalo de nuevo.", "error");
  } finally {
    logoutButton.disabled = false;
  }
});

checkSession();
