const loader = document.getElementById("loader");
function showLoader() {
  if (loader) {
    loader.style.display = "block";
  }
}
function hideLoader() {
  if (loader) {
    loader.style.display = "none";
  }
}

const themeSwitcher = document.getElementById("theme-switcher");
const body = document.body;

if (themeSwitcher) {
  themeSwitcher.addEventListener("click", () => {
    body.classList.toggle("dark-mode");
    localStorage.setItem(
      "theme",
      body.classList.contains("dark-mode") ? "dark" : "light",
    );
  });
}

// Apply the saved theme on page load
document.addEventListener("DOMContentLoaded", () => {
  const savedTheme = localStorage.getItem("theme");
  if (savedTheme === "light") {
    body.classList.remove("dark-mode");
  } else {
    body.classList.add("dark-mode");
  }
});
