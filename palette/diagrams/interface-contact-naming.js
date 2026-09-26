/** Edit one persistent contact name beside the clicked shape. */
function openInterfaceContactNameEditor(diagram, state, contactId, pointer) {
  const contact = state.contacts.find((item) => item.contactId === contactId);
  if (!contact) return;
  diagram.querySelector(".interface-contact-name-editor")?.remove();
  const editor = document.createElement("form");
  const label = document.createElement("label");
  const input = document.createElement("input");
  const save = document.createElement("button");
  const cancel = document.createElement("button");
  editor.className = "interface-contact-name-editor";
  editor.dataset.contactId = contactId;
  label.textContent = "Name / number";
  input.type = "text";
  input.maxLength = 80;
  input.value = contact.assignedName || "";
  input.placeholder = contact.name;
  input.setAttribute("aria-label", "Contact name / number");
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
    const name = input.value.trim();
    if (name === (contact.assignedName || "")) {
      editor.remove();
      return;
    }
    void send("set_interface_contact_name", {
      harnessId: state.harnessId,
      interfaceId: state.interfaceId,
      contactId, name,
    }).then(() => editor.remove()).catch((error) => appendNotice(String(error), true));
  });
  editor.append(label, input, save, cancel);
  diagram.append(editor);
  const bounds = diagram.getBoundingClientRect();
  editor.style.left = `${Math.max(8, Math.min(pointer.clientX - bounds.left + 10,
    bounds.width - 200))}px`;
  editor.style.top = `${Math.max(8, Math.min(pointer.clientY - bounds.top + 10,
    bounds.height - 75))}px`;
  input.focus();
  input.select();
}
