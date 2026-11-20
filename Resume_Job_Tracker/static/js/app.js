let draggedCard = null;
function dragCard(event) { draggedCard = event.currentTarget; event.dataTransfer.setData("text/plain", draggedCard.dataset.id); }
function allowDrop(event) { event.preventDefault(); event.currentTarget.classList.add("drag-over"); }
document.addEventListener("dragleave", e => { if(e.target.classList && e.target.classList.contains("drop-zone")) e.target.classList.remove("drag-over"); });
async function dropCard(event, status) {
  event.preventDefault(); const zone = event.currentTarget; zone.classList.remove("drag-over");
  const id = event.dataTransfer.getData("text/plain"); if (!id) return;
  const response = await fetch(`/api/applications/${id}/status`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({status})});
  if(response.ok) location.reload(); else alert("Could not update application status.");
}
function filterCards() {
  const q = document.getElementById("boardSearch").value.toLowerCase();
  document.querySelectorAll(".job-card").forEach(card => card.style.display = card.dataset.search.includes(q) ? "" : "none");
}
