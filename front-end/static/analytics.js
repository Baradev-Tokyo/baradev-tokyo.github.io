(() => {
  const measurementId = document.currentScript.dataset.measurementId;
  const preferences = document.getElementById("analytics-preferences");
  const settingsButton = document.getElementById("open-analytics-preferences");
  const canonical = document.querySelector('link[rel="canonical"]').href;
  const storageKey = "bara.analytics";
  let choice;
  let initialized = false;

  function start() {
    if (initialized || choice !== "allow") return;
    initialized = true;
    const referrer = document.referrer ? new URL(document.referrer) : null;
    const campaign = new URLSearchParams(window.location.search);
    const attribution = {};
    for (const [query, field] of [
      ["utm_source", "campaign_source"], ["utm_medium", "campaign_medium"],
      ["utm_campaign", "campaign_name"],
    ]) {
      const value = campaign.get(query);
      if (value && /^[a-z0-9._-]{1,80}$/i.test(value)) attribution[field] = value;
    }
    window.dataLayer = window.dataLayer || [];
    // The Google tag expects an arguments object in its command queue.
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag("js", new Date());
    window.gtag("config", measurementId, {
      send_page_view: false,
      allow_google_signals: false,
      allow_ad_personalization_signals: false,
      page_location: canonical,
      page_referrer: referrer ? referrer.origin : "",
      ...attribution,
    });
    window.gtag("event", "page_view", { site_language: document.documentElement.lang });
    const script = document.createElement("script");
    script.async = true;
    script.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(measurementId);
    document.head.append(script);
  }

  function showChoice(value) {
    choice = value;
    for (const button of preferences.querySelectorAll("[data-analytics-choice]")) {
      button.setAttribute("aria-pressed", String(button.dataset.analyticsChoice === value));
    }
    window["ga-disable-" + measurementId] = value !== "allow";
    start();
  }

  try {
    showChoice(localStorage.getItem(storageKey));
  } catch {
    showChoice(null);
  }
  settingsButton.hidden = false;
  settingsButton.addEventListener("click", () => preferences.showModal());
  if (!choice && !preferences.hasAttribute("data-skip-prompt")) preferences.showModal();

  function saveChoice(value) {
    try {
      localStorage.setItem(storageKey, value);
    } catch {
      // Keep the choice for this page when browser storage is unavailable.
    }
    showChoice(value);
    preferences.close();
  }

  preferences.addEventListener("click", (event) => {
    const value = event.target.dataset.analyticsChoice;
    if (value) saveChoice(value);
  });

  preferences.addEventListener("cancel", (event) => {
    if (choice) return;
    event.preventDefault();
    saveChoice("deny");
  });

  document.addEventListener("click", (event) => {
    if (choice !== "allow") return;
    const link = event.target.closest("a[data-analytics-event]");
    if (!link) return;
    window.gtag("event", link.dataset.analyticsEvent, {
      site_language: document.documentElement.lang,
      ...(link.dataset.package ? { package_slug: link.dataset.package } : {}),
    });
  });
})();
