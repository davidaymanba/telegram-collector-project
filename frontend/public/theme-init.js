// Applied before first paint to avoid a light/dark or LTR/RTL flash. (External file: CSP forbids inline scripts.)
(function () {
  try {
    var t = localStorage.getItem("tuc.theme") || "system";
    var dark = t === "dark" || (t === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", dark);
    var l = localStorage.getItem("tuc.lang") || "ar";
    document.documentElement.lang = l;
    document.documentElement.dir = l === "ar" ? "rtl" : "ltr";
  } catch (e) {}
})();
