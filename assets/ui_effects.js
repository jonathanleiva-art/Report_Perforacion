(function () {
  try {
    var doc = window.parent && window.parent.document;
    if (!doc || !doc.body) {
      return;
    }

    doc.body.classList.add("rp-ui-ready");

    var existing = doc.getElementById("rp-ui-ready-flag");
    if (!existing) {
      var flag = doc.createElement("div");
      flag.id = "rp-ui-ready-flag";
      flag.style.display = "none";
      doc.body.appendChild(flag);
    }
  } catch (error) {
    try {
      console.debug("rp-ui-effects fallback", error);
    } catch (_ignore) {}
  }
})();
