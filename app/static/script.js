document.getElementById("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const formData = new FormData();
  formData.append("pdf", document.getElementById("pdf").files[0]);
  formData.append("label", document.getElementById("label").value);
  formData.append("schema_json", document.getElementById("schema").value);

  const output = document.getElementById("output");
  output.textContent = "Processing...";

  const res = await fetch("/extract", { method: "POST", body: formData });
  const data = await res.json();

  if (data.success) {
    output.textContent = JSON.stringify(data, null, 2);
  } else {
    output.textContent = "Error: " + data.error;
  }
});
