const checkboxes = document.querySelectorAll(".checker");
const repeatedEvent = document.querySelector(".repeated");

checkboxes.forEach((checkbox) => {
  checkbox.addEventListener("change", (e) => {
    const target = e.target;
    if (!target.checked) {
      target.parentElement.nextElementSibling.setAttribute("disabled", "");
    } else {
      target.parentElement.nextElementSibling.removeAttribute("disabled");
    }
    if (
      !checkboxes[0].checked &&
      !checkboxes[1].checked &&
      !checkboxes[2].checked
    ) {
      repeatedEvent.setAttribute("disabled", "");
    } else {
      repeatedEvent.removeAttribute("disabled");
    }
  });
});
