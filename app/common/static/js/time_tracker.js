/**
 * TimeTracker
 * Tracks time spent on a page and sends updates to the server on unload.
 * Also updates hidden form inputs if present.
 */
class TimeTracker {
  constructor(config) {
    this.updateUrl = config.updateUrl;
    this.topicName = config.topicName;
    // Optional: extra data to send
    this.extraData = config.extraData || {};

    this.startTime = Date.now();
    this.csrfToken =
      document
        .querySelector('meta[name="csrf-token"]')
        ?.getAttribute("content") ||
      document.querySelector('input[name="csrf_token"]')?.value;

    this.init();
  }

  init() {
    // Handle page unload / visibility change
    window.addEventListener("beforeunload", () => this.sendUpdate());
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden") {
        this.sendUpdate();
      } else {
        // Reset start time to avoid double counting if user comes back?
        // Actually, simple "beacon" model: send accumulated time, then reset.
        this.resetTimer();
      }
    });

    // Hook into forms if present to inject time_spent
    // This acts as a backup or for explicit submissions (like quiz)
    document.querySelectorAll("form").forEach((form) => {
      form.addEventListener("submit", () => {
        this.updateFormInput(form);
      });
    });
  }

  getDuration() {
    const now = Date.now();
    const duration = Math.round((now - this.startTime) / 1000); // seconds
    return duration;
  }

  resetTimer() {
    this.startTime = Date.now();
  }

  updateFormInput(form) {
    let input = form.querySelector('input[name="time_spent"]');
    if (!input) {
      input = document.createElement("input");
      input.type = "hidden";
      input.name = "time_spent";
      form.appendChild(input);
    }
    // Add current duration to whatever might be there (though usually 0)
    // Ideally, we just set the value of the current session duration
    input.value = this.getDuration();
  }

  sendUpdate() {
    const duration = this.getDuration();
    if (duration <= 0) return;

    // Use sendBeacon for reliable delivery on unload
    const data = new FormData();
    data.append("time_spent", duration);
    data.append("csrf_token", this.csrfToken);

    // Add extra data
    for (const [key, value] of Object.entries(this.extraData)) {
      data.append(key, value);
    }

    if (navigator.sendBeacon) {
      // sendBeacon requires blob or form data.
      // Note: sendBeacon sends POST.
      // Some backends check CSRF. We added it to FormData.
      const url = this.updateUrl;
      navigator.sendBeacon(url, data);
    } else {
      // Fallback
      fetch(this.updateUrl, {
        method: "POST",
        body: data,
        keepalive: true,
      }).catch((err) => console.error("Time tracking failed", err));
    }

    // Reset timer so we don't double count if the page stays open (visibility toggle)
    this.resetTimer();
  }
}

// Expose globally
window.TimeTracker = TimeTracker;
