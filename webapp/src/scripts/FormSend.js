class FormSend {
  constructor(form) {
    if (!(form instanceof HTMLElement)) {
      throw new Error("Not an element");
    }

    this.form = form;

    this.data = {};

    this.onSubmit = this.onSubmit.bind(this);

    this.form.addEventListener("submit", this.onSubmit);
  }

  onSubmit(e) {
    const target = e.target;
    for (let i = 0; i < target.elements.length; i++) {
      let element = target.elements[i];
      if (element.tagName.toLowerCase() === "input") {
        this.data[element.id] = element.value;
      }
    }

    telegram.sendData(JSON.stringify(this.data));
    telegram.close();
  }
}
