// module style javascript entry point after the main GOV.UK Frontend script has been loaded

// on page load
document.addEventListener("DOMContentLoaded", function () {
  sectionCardHyperlinks();
});

function sectionCardHyperlinks() {
  const sectionCards = document.querySelectorAll(".section-card");
  sectionCards.forEach((card) => {
    const link = card.querySelector("a");
    if (link) {
      card.classList.add("section-card--clickable");
      card.addEventListener("click", () => {
        window.location.href = link.href;
      });
    }
  });
}
