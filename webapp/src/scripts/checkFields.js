const checkbox = document.querySelectorAll(".checker");

checkbox.forEach((checkbox) => {
  checkbox.addEventListener("change", (e) => {
    const target = e.target;
    if (!target.checked) {
      target.parentElement.nextElementSibling.setAttribute("disabled", "");
    } else {
      target.parentElement.nextElementSibling.removeAttribute("disabled");
    }
  });
});
