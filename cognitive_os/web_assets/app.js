const token = document.querySelector('meta[name="decision-token"]').content;
const loading = document.getElementById("loading");
const decisionView = document.getElementById("decision-view");
const outcomeView = document.getElementById("outcome-view");
const errorBox = document.getElementById("error-box");
let currentState = null;

function text(id, value) {
  document.getElementById(id).textContent = value;
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function make(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}

function setProgress(mode) {
  document.querySelectorAll(".step").forEach((node, index) => {
    node.classList.toggle("active", mode === "awaiting_decision" ? index < 2 : index === 2);
    node.classList.toggle("complete", mode === "decided" && index < 2);
  });
}

function renderPreview(preview) {
  const projects = document.getElementById("project-grid");
  clear(projects);
  preview.project_scopes.forEach((project) => {
    const card = make("article", "project-card");
    const identity = make("div", "project-id");
    identity.append(make("span", "project-letter", project.label[0]));
    identity.append(make("span", "opted-in", "✓ Explicitly selected"));
    card.append(identity, make("h3", "", project.label));
    const strongest = project.intents.find((intent) => intent.kind === "actionable") || project.intents[0];
    card.append(make("p", "", strongest.statement));
    card.append(make("span", "intent-count", `${project.intents.length} local intent signals · ${project.owned_paths[0]}`));
    projects.append(card);
  });

  const proposal = preview.relationship_proposal;
  text("confidence", `${proposal.confidence.band} confidence · ${Math.round(proposal.confidence.score_millis / 10)}%`);
  text("notice-copy", preview.notice.plain_language);
  text("relationship-detail", `${preview.notice.source_statement} ${preview.notice.target_statement}`);
  const evidence = document.getElementById("evidence-list");
  clear(evidence);
  proposal.evidence.forEach((item) => evidence.append(make("div", "evidence-item", item.rationale)));
}

function renderOutcome(state) {
  const report = state.report;
  const approved = report.relationship_proposal.status === "accepted";
  text("outcome-icon", approved ? "✓" : "×");
  document.getElementById("outcome-icon").style.background = approved ? "var(--green)" : "var(--orange)";
  text("outcome-kicker", approved ? "Relationship approved" : "Relationship rejected");
  text("outcome-heading", approved ? "One coherent next move is ready for review." : "The boundary held. No plan was created.");
  text("outcome-summary", approved ? "Your decision produced a real local plan and evidence record—without executing anything." : "Your decision was recorded locally, and the two projects remain independent.");

  const planList = document.getElementById("plan-list");
  const noPlan = document.getElementById("no-plan");
  clear(planList);
  if (approved) {
    text("plan-title", report.plan.title);
    report.plan.selected_atom_ids.forEach((atomId) => {
      const item = state.preview.project_scopes.flatMap((project) => project.intents).find((intent) => intent.atom_id === atomId);
      planList.append(make("li", "", item ? item.statement : atomId));
    });
    noPlan.classList.add("hidden");
  } else {
    text("plan-title", "Stopped before planning");
    noPlan.textContent = report.verification.blocker;
    noPlan.classList.remove("hidden");
  }

  const route = report.bounded_route_simulation;
  const routeText = route
    ? `ROUTE  ${route.selected_route}\nSCOPE  ${route.scoped_project_ids.join(" + ")}\nPERMISSION  ${route.permission_class}\nEFFECTS  none`
    : "ROUTE  not created\nSCOPE  unchanged\nPERMISSION  none\nEFFECTS  none";
  text("route-receipt", routeText);

  const verified = report.verification.observed_result === "verified_in_test_double";
  text("verification-badge", verified ? "✓ Evidence complete" : approved ? "Blocked" : "✓ Decision recorded");
  const evidenceList = document.getElementById("verification-list");
  clear(evidenceList);
  const records = report.verification.evidence.length
    ? report.verification.evidence
    : [{ evidence_id: "human_decision", description: "The exact rejection and human authority were persisted locally.", passed: true }];
  records.forEach((record) => {
    const card = make("div", "verification-item");
    card.append(make("b", "", `${record.passed ? "✓" : "!"} ${record.evidence_id.replaceAll("_", " ")}`));
    card.append(make("p", "", record.description));
    evidenceList.append(card);
  });
  document.getElementById("next-decision").replaceChildren(
    make("strong", "", "Next decision · "),
    document.createTextNode(report.verification.next_decision)
  );

  const timeline = document.getElementById("timeline");
  clear(timeline);
  const momentWord = report.timeline.length === 1 ? "moment" : "moments";
  text("timeline-heading", `${report.timeline.length} ${momentWord}. Complete local trace.`);
  report.timeline.forEach((event, index) => {
    const item = make("div", "timeline-item");
    item.append(make("b", "", `${String(index + 1).padStart(2, "0")} · ${event.event.split(".")[1].replaceAll("_", " ")}`));
    item.append(make("p", "", event.summary));
    timeline.append(item);
  });
  text("store-path", state.persistence.store_path);
}

function render(state) {
  currentState = state;
  loading.classList.add("hidden");
  errorBox.classList.add("hidden");
  renderPreview(state.preview);
  setProgress(state.mode);
  if (state.mode === "decided") {
    decisionView.classList.add("hidden");
    outcomeView.classList.remove("hidden");
    renderOutcome(state);
  } else {
    outcomeView.classList.add("hidden");
    decisionView.classList.remove("hidden");
  }
}

function showError(message) {
  errorBox.textContent = `The local decision could not advance: ${message}`;
  errorBox.classList.remove("hidden");
}

async function loadState() {
  const response = await fetch("/api/state", { cache: "no-store" });
  if (!response.ok) throw new Error("local state is unavailable");
  render(await response.json());
}

async function decide(decision) {
  const buttons = [document.getElementById("approve-button"), document.getElementById("reject-button")];
  buttons.forEach((button) => { button.disabled = true; });
  try {
    const response = await fetch("/api/decide", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Decision-Token": token },
      body: JSON.stringify({
        decision,
        proposal_id: currentState.preview.relationship_proposal.proposal_id,
      }),
    });
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || "decision rejected");
    render(value);
    window.scrollTo({ top: document.querySelector(".steps").offsetTop - 20, behavior: "smooth" });
  } catch (error) {
    showError(error.message);
    buttons.forEach((button) => { button.disabled = false; });
  }
}

document.getElementById("approve-button").addEventListener("click", () => decide("accept"));
document.getElementById("reject-button").addEventListener("click", () => decide("reject"));
loadState().catch((error) => {
  loading.classList.add("hidden");
  showError(error.message);
});
