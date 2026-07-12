// Mermaid init — re-renders on Material's instant navigation.
// Material 9.7+ no longer auto-bootstraps mermaid; load it manually.

(function () {
  function init() {
    if (typeof mermaid === "undefined") return;
    var scheme = document.body.getAttribute("data-md-color-scheme") || "default";
    mermaid.initialize({
      startOnLoad: false,
      theme: scheme === "slate" ? "dark" : "default",
      flowchart: { curve: "basis", htmlLabels: true },
      themeVariables: {
        primaryColor: "#009485",
        primaryTextColor: "#ffffff",
        primaryBorderColor: "#00675b",
        lineColor: "#00b89c",
        secondaryColor: "#ff6e40",
        tertiaryColor: "#fafbfc",
      },
    });
    document.querySelectorAll("pre.mermaid").forEach(function (el) {
      if (el.dataset.processed === "true") return;
      var code = el.querySelector("code");
      if (code) el.textContent = code.textContent;
      el.dataset.processed = "true";
    });
    mermaid.run({ querySelector: "pre.mermaid" });
  }

  // Run at first load
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Re-run on Material instant navigation (route changes without reload)
  if (typeof document$ !== "undefined" && document$.subscribe) {
    document$.subscribe(init);
  }
})();
