from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["ui"])


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def program_ui() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TPM Cockpit</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #18212f;
      background: #f6f7f9;
    }
    body {
      margin: 0;
    }
    main {
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }
    header {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 20px;
      margin-bottom: 24px;
    }
    h1 {
      margin: 0;
      font-size: 30px;
      font-weight: 720;
    }
    a {
      color: #2364aa;
      text-decoration: none;
    }
    .layout {
      display: grid;
      grid-template-columns: minmax(280px, 360px) 1fr;
      gap: 20px;
      align-items: start;
    }
    section {
      background: #ffffff;
      border: 1px solid #d9dee7;
      border-radius: 8px;
      padding: 18px;
    }
    h2 {
      margin: 0 0 14px;
      font-size: 18px;
    }
    label {
      display: block;
      margin: 12px 0 6px;
      font-size: 13px;
      font-weight: 650;
    }
    input, textarea, select {
      width: 100%;
      box-sizing: border-box;
      border: 1px solid #c8d0dc;
      border-radius: 6px;
      padding: 9px 10px;
      font: inherit;
      background: #ffffff;
    }
    textarea {
      min-height: 92px;
      resize: vertical;
    }
    button {
      border: 0;
      border-radius: 6px;
      padding: 9px 12px;
      font: inherit;
      font-weight: 650;
      cursor: pointer;
      background: #2364aa;
      color: #ffffff;
    }
    button.secondary {
      background: #e7ebf1;
      color: #243043;
    }
    button.danger {
      background: #b42318;
    }
    .actions {
      display: flex;
      gap: 8px;
      margin-top: 14px;
      flex-wrap: wrap;
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th, td {
      padding: 10px;
      border-bottom: 1px solid #e2e7ef;
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }
    th {
      color: #526071;
      font-size: 12px;
      text-transform: uppercase;
    }
    .row-actions {
      display: flex;
      gap: 6px;
      justify-content: flex-end;
    }
    .muted {
      color: #667085;
    }
    #message {
      min-height: 20px;
      margin-top: 12px;
      color: #526071;
      font-size: 14px;
    }
    @media (max-width: 820px) {
      header, .layout {
        display: block;
      }
      section {
        margin-bottom: 18px;
      }
      th:nth-child(2), td:nth-child(2) {
        display: none;
      }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>TPM Cockpit</h1>
        <div class="muted">Programs</div>
      </div>
      <a href="/docs">API docs</a>
    </header>
    <div class="layout">
      <section>
        <h2 id="form-title">New Program</h2>
        <form id="program-form">
          <input type="hidden" id="program-id">
          <label for="name">Name</label>
          <input id="name" name="name" required maxlength="200">
          <label for="description">Description</label>
          <textarea id="description" name="description"></textarea>
          <label for="status">Status</label>
          <select id="status" name="status">
            <option value="active">Active</option>
            <option value="paused">Paused</option>
            <option value="completed">Completed</option>
            <option value="archived">Archived</option>
          </select>
          <div class="actions">
            <button type="submit">Save</button>
            <button class="secondary" type="button" id="reset-button">Clear</button>
          </div>
          <div id="message"></div>
        </form>
      </section>
      <section>
        <h2>Program List</h2>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Description</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody id="programs"></tbody>
        </table>
      </section>
    </div>
  </main>
  <script>
    const form = document.querySelector("#program-form");
    const idInput = document.querySelector("#program-id");
    const nameInput = document.querySelector("#name");
    const descriptionInput = document.querySelector("#description");
    const statusInput = document.querySelector("#status");
    const message = document.querySelector("#message");
    const tbody = document.querySelector("#programs");
    const formTitle = document.querySelector("#form-title");

    function payload() {
      return {
        name: nameInput.value,
        description: descriptionInput.value || null,
        status: statusInput.value
      };
    }

    function resetForm() {
      idInput.value = "";
      form.reset();
      statusInput.value = "active";
      formTitle.textContent = "New Program";
      message.textContent = "";
    }

    function editProgram(program) {
      idInput.value = program.id;
      nameInput.value = program.name;
      descriptionInput.value = program.description || "";
      statusInput.value = program.status;
      formTitle.textContent = "Edit Program";
      message.textContent = "";
      nameInput.focus();
    }

    async function loadPrograms() {
      const response = await fetch("/programs");
      const programs = await response.json();
      tbody.innerHTML = "";
      for (const program of programs) {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td></td>
          <td></td>
          <td></td>
          <td class="row-actions">
            <button class="secondary" type="button">Edit</button>
            <button class="danger" type="button">Delete</button>
          </td>
        `;
        row.children[0].textContent = program.name;
        row.children[1].textContent = program.description || "";
        row.children[2].textContent = program.status;
        row.querySelector(".secondary").addEventListener("click", () => editProgram(program));
        row.querySelector(".danger").addEventListener("click", async () => {
          await fetch(`/programs/${program.id}`, { method: "DELETE" });
          if (idInput.value === String(program.id)) resetForm();
          await loadPrograms();
        });
        tbody.appendChild(row);
      }
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const id = idInput.value;
      const response = await fetch(id ? `/programs/${id}` : "/programs", {
        method: id ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload())
      });
      if (!response.ok) {
        message.textContent = "Could not save program.";
        return;
      }
      resetForm();
      await loadPrograms();
    });

    document.querySelector("#reset-button").addEventListener("click", resetForm);
    loadPrograms();
  </script>
</body>
</html>
"""
