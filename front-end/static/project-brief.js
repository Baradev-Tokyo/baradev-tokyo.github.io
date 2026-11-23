(() => {
  const storageKey = (slug) => `bara.project-brief.${document.documentElement.lang}.${slug}`;

  function readBrief(slug) {
    try {
      return JSON.parse(sessionStorage.getItem(storageKey(slug)));
    } catch {
      return null;
    }
  }

  for (const form of document.querySelectorAll("[data-project-brief]")) {
    const slug = form.dataset.package;
    const fields = Array.from(form.querySelectorAll("[data-brief-choice]"));
    const notes = form.querySelector("[data-brief-notes]");
    const brief = readBrief(slug);
    if (brief) {
      fields.forEach((field, index) => {
        if (field.type === "checkbox") {
          field.checked = brief.choices[index] === field.value;
        } else {
          field.value = brief.choices[index] || "";
        }
      });
      notes.value = brief.notes;
    }
    if (location.hash === `#${slug}`) {
      form.closest("details").open = true;
    }
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const choices = fields.map((field) => field.type === "checkbox" && !field.checked ? "" : field.value);
      try {
        sessionStorage.setItem(storageKey(slug), JSON.stringify({ choices, notes: notes.value.trim() }));
      } catch {
        // Booking remains available when browser storage is blocked.
      }
      location.assign(form.action);
    });
  }

  const summary = document.querySelector("[data-brief-summary]");
  if (summary) {
    const brief = readBrief(summary.dataset.package);
    const values = brief ? [...brief.choices, brief.notes].filter(Boolean) : [];
    if (values.length) {
      for (const value of values) {
        const item = document.createElement("li");
        item.textContent = value;
        summary.querySelector("[data-brief-values]").append(item);
      }
      const subject = document.documentElement.lang === "ja" ? "Baraへのプロジェクト相談" : "Project brief for Bara";
      summary.querySelector("[data-brief-email]").href =
        `mailto:baradev.tokyo@gmail.com?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(
          document.querySelector("h1").textContent + "\n\n" + values.join("\n")
        )}`;
      summary.hidden = false;
    }
  }

  const consultation = document.querySelector("#consultation");
  if (consultation && location.hash === "#consultation") {
    consultation.open = true;
  }
})();
