class FormSend {
  constructor(form) {
    if (!(form instanceof HTMLElement)) {
      throw new Error("Not an element");
    }

    this.form = form;

    this.data = {};

    this.onSubmit = this.onSubmit.bind(this);
    this.checkValidity = this.checkValidity.bind(this);
    this.checkElement = this.checkElement.bind(this);

    this.form.addEventListener("submit", this.onSubmit);
  }

  onSubmit(e) {
    e.preventDefault();
    const target = e.target;
    for (let i = 0; i < target.elements.length; i++) {
      let element = target.elements[i];
      this.checkElement(element);
    }
    telegram.sendData(JSON.stringify(this.data));
    telegram.close();
  }

  checkElement(element) {
    if (element.tagName.toLowerCase() === "select") {
      this.data[element.id] = element.value;
      this.checkValidity(element);
    }
    if (
      element.tagName.toLowerCase() === "input" &&
      !element.classList.contains("checker")
    ) {
      this.data[element.id] = element.value;
      this.checkValidity(element);
    }
    if (element.tagName.toLowerCase() === "textarea") {
      this.data[element.id] = element.value;
      this.checkValidity(element);
    }
    if (element.type === "checkbox" && !element.classList.contains("checker")) {
      element.checked
        ? (this.data[element.id] = `${element.checked}`)
        : (this.data[element.id] = "false");
    }
  }

  checkValidity(element) {
    if (element.disabled) {
      this.data[element.id] = "none";
    }
    if (element.value === "") {
      this.data[element.id] = "none";
    }
  }
}
