/** Edit one contact's display value and pin beside the clicked shape. */
function openInterfaceContactEditor(diagram, state, contactId, pointer) {
  const contact = state.contacts.find((item) => item.contactId === contactId);
  if (!contact) return;
  diagram.querySelector(".interface-contact-details-editor")?.remove();
  const editor = document.createElement("form");
  const valueLabel = document.createElement("label");
  const valueInput = document.createElement("input");
  const pinLabel = document.createElement("label");
  const pinInput = document.createElement("input");
  const save = document.createElement("button");
  const cancel = document.createElement("button");
  editor.className = "interface-contact-details-editor";
  editor.dataset.contactId = contactId;
  valueLabel.textContent = "Value";
  valueInput.type = "text";
  valueInput.maxLength = 80;
  valueInput.value = contact.assignedName || "";
  valueInput.placeholder = contact.name;
  valueLabel.append(valueInput);
  pinLabel.textContent = "Pin";
  pinInput.type = "text";
  pinInput.maxLength = 80;
  pinInput.value = contact.pin || "";
  pinLabel.append(pinInput);
  save.type = "submit";
  save.className = "button compact";
  save.textContent = "Save";
  cancel.type = "button";
  cancel.className = "button compact";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => editor.remove());
  editor.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    editor.remove();
  });
  editor.addEventListener("submit", (event) => {
    event.preventDefault();
    const value = valueInput.value.trim();
    const pin = pinInput.value.trim();
    if (value === (contact.assignedName || "") && pin === (contact.pin || "")) {
      editor.remove();
      return;
    }
    void send("set_interface_contact_details", {
      harnessId: state.harnessId,
      interfaceId: state.interfaceId,
      contactId, value, pin,
    }).then(() => editor.remove()).catch((error) => appendNotice(String(error), true));
  });
  editor.append(valueLabel, pinLabel, save, cancel);
  diagram.append(editor);
  const bounds = diagram.getBoundingClientRect();
  editor.style.left = `${Math.max(8, Math.min(pointer.clientX - bounds.left + 10,
    bounds.width - 220))}px`;
  editor.style.top = `${Math.max(8, Math.min(pointer.clientY - bounds.top + 10,
    bounds.height - 145))}px`;
  valueInput.focus();
  valueInput.select();
}
