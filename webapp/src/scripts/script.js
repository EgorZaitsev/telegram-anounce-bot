class AnounceForm {
  constructor(form) {
    if (!(form instanceof HTMLElement)) {
      throw new Error("Not a form");
    }

    this.form = form;

    this.titleInput = form.querySelector(".input__title");
    this.button = form.querySelector(".submit__button");
  }

  onClick(event) {
    const target = event.target;
    const anounceJSON = {
      name: this.titleInput.value,
    };
    return anounceJSON;
  }

  onSubmit(event) {
    const target = event.target;
  }
}
