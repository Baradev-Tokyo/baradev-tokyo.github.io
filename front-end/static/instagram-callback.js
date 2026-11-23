(() => {
  const incoming = new URLSearchParams(location.search);
  history.replaceState(null, "", location.pathname);
  const state = incoming.get("state");
  const code = incoming.get("code");
  const denied = incoming.has("error");
  if (!state || !/^[A-Za-z0-9_-]{43}$/.test(state) || (!denied && (!code || code.length > 4096))) {
    document.querySelector("#status").textContent = "Start authorization again from Bara on this computer.";
    return;
  }
  const callback = new URL(document.body.dataset.callback);
  callback.searchParams.set("state", state);
  if (denied) {
    callback.searchParams.set("error", "access_denied");
  } else {
    callback.searchParams.set("code", code);
  }
  location.replace(callback.href);
})();
