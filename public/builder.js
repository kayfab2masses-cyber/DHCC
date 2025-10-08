
/* Daggerheart Character Builder – front-end only.
 * - No 'archetypes' anywhere.
 * - Per-level state with "Lock & Save".
 * - Reads domain_cards.json; falls back to a tiny default set if unavailable.
 * - Suggested class primary traits are informational.
 */

const CLASSES = {
  "Bard":      { suggestedTrait: "Presence", subclasses: ["Wordsmith", "Troubadour"] },
  "Druid":     { suggestedTrait: "Instinct", subclasses: ["Warden of Renewal", "Warden of the Elements"] },
  "Guardian":  { suggestedTrait: "Strength", subclasses: ["Stalwart", "Bulwark"] },
  "Rogue":     { suggestedTrait: "Agility", subclasses: ["Shadow", "Trickster"] },
  "Seraph":    { suggestedTrait: "Presence", subclasses: ["Divine Wielder", "Radiant Judge"] },
  "Warrior":   { suggestedTrait: "Strength", subclasses: ["Call of the Slayer", "Weapon Master"] },
  "Wayfinder": { suggestedTrait: "Knowledge", subclasses: ["Pathseeker", "Cartomancer"] }
};

const DEFAULT_CARDS = [
  {"name": "Nature’s Tongue", "domain": "Arcana", "level": 1, "type": "Spell", "recall_cost": 1, "description": "Speak to the plants and animals nearby."},
  {"name": "Vicious Entangle", "domain": "Arcana", "level": 1, "type": "Spell", "recall_cost": 1, "description": "Roots restrain a foe within Far range."},
  {"name": "Bare Bones", "domain": "Warfare", "level": 1, "type": "Stance", "recall_cost": 0, "description": "Base Armor Score 3 + STR; use thresholds 9/19/24/31/38."},
  {"name": "Get Back Up", "domain": "Warfare", "level": 1, "type": "Tactic", "recall_cost": 0, "description": "Reduce Severe damage by one threshold when you take it."},
  {"name": "Deft Deceiver", "domain": "Guile", "level": 1, "type": "Trick", "recall_cost": 0, "description": "Spend Hope to gain advantage on a deception roll."},
  {"name": "Inspirational Words", "domain": "Devotion", "level": 1, "type": "Prayer", "recall_cost": 0, "description": "Place tokens equal to Presence. Spend to grant benefits."}
];

const state = {
  meta: { name: "", level: 1 },
  build: {}, // per-level snapshot: build[level] = {...}
  current: levelTemplate(1),
  domainCards: [],
};

function levelTemplate(level) {
  return {
    level,
    class: "",
    subclass: "",
    traits: { Instinct: 0, Presence: 0, Knowledge: 0, Agility: 0, Finesse: 0, Strength: 0 },
    hp: 6,
    evasion: 10,
    heritage: { ancestry: "", community: "", features: "" },
    experiences: [],
    cards: []
  };
}

// UI elements
const el = (id) => document.getElementById(id);
const nameInput = el("charName");
const levelInput = el("level");
const levelLabel = el("levelLabel");
const classSelect = el("classSelect");
const subclassSelect = el("subclassSelect");
const suggestedTrait = el("suggestedTrait");

const tInputs = {
  Instinct: el("tInstinct"),
  Presence: el("tPresence"),
  Knowledge: el("tKnowledge"),
  Agility: el("tAgility"),
  Finesse: el("tFinesse"),
  Strength: el("tStrength")
};

const hpInput = el("hp");
const evasionInput = el("evasion");
const notesTraits = el("notesTraits");

const ancestryInput = el("ancestry");
const communityInput = el("community");
const heritageFeatures = el("heritageFeatures");

const exp1 = el("exp1");
const exp2 = el("exp2");

const domainFilter = el("domainFilter");
const cardSearch = el("cardSearch");
const cardsList = el("cardsList");
const selectedCards = el("selectedCards");
const summary = el("summary");

function saveLocal() {
  localStorage.setItem("dhcc_builder_state", JSON.stringify(state));
}

function loadLocal() {
  try {
    const raw = localStorage.getItem("dhcc_builder_state");
    if (!raw) return;
    const parsed = JSON.parse(raw);
    Object.assign(state, parsed);
  } catch (e) { /* ignore */ }
}

// populate class/subclass/suggested
function populateClassUI() {
  const meta = CLASSES[state.current.class] || null;
  // subclasses
  subclassSelect.innerHTML = "<option value=''>— Any —</option>";
  if (meta) {
    meta.subclasses.forEach(sc => {
      const opt = document.createElement("option");
      opt.value = sc;
      opt.textContent = sc;
      subclassSelect.appendChild(opt);
    });
    suggestedTrait.textContent = meta.suggestedTrait || "—";
  } else {
    suggestedTrait.textContent = "—";
  }
}

function renderSelectedCards() {
  selectedCards.innerHTML = "";
  state.current.cards.forEach((nm) => {
    const li = document.createElement("li");
    li.textContent = nm;
    selectedCards.appendChild(li);
  });
}

function renderCardsList() {
  const q = (cardSearch.value || "").toLowerCase();
  const dom = domainFilter.value;
  cardsList.innerHTML = "";

  const items = state.domainCards.filter(c => {
    const okDomain = !dom || c.domain === dom;
    const okQ = !q || c.name.toLowerCase().includes(q);
    return okDomain && okQ && (c.level || 1) <= state.current.level;
  });

  if (items.length === 0) {
    cardsList.innerHTML = "<div class='muted'>No cards match your filters.</div>";
    return;
  }

  items.forEach(c => {
    const card = document.createElement("div");
    card.className = "card";
    card.onclick = () => toggleCard(c.name);
    card.innerHTML = `
      <div class="title">${c.name}</div>
      <div class="meta">${c.domain} • Level ${c.level || 1} • ${c.type || ""}${c.recall_cost!==undefined? " • Recall "+c.recall_cost: ""}</div>
      <div class="desc">${c.description || ""}</div>
    `;
    cardsList.appendChild(card);
  });
}

function toggleCard(name) {
  const idx = state.current.cards.indexOf(name);
  if (idx >= 0) state.current.cards.splice(idx, 1);
  else state.current.cards.push(name);
  renderSelectedCards();
}

function recompute() {
  // Update labels
  levelLabel.textContent = String(state.current.level);
  // force inputs to reflect state
  nameInput.value = state.meta.name || "";
  levelInput.value = String(state.meta.level);

  classSelect.value = state.current.class || "";
  populateClassUI();
  if (state.current.subclass) subclassSelect.value = state.current.subclass;

  for (const k of Object.keys(tInputs)) tInputs[k].value = state.current.traits[k] ?? 0;
  hpInput.value = state.current.hp ?? 6;
  evasionInput.value = state.current.evasion ?? 10;
  ancestryInput.value = state.current.heritage.ancestry || "";
  communityInput.value = state.current.heritage.community || "";
  heritageFeatures.value = state.current.heritage.features || "";
  exp1.value = state.current.experiences[0] || "";
  exp2.value = state.current.experiences[1] || "";

  renderSelectedCards();
  renderCardsList();
  renderSummary();
}

function renderSummary() {
  const out = {
    meta: state.meta,
    build: state.build
  };
  summary.textContent = JSON.stringify(out, null, 2);
}

// events
nameInput.addEventListener("input", (e) => { state.meta.name = e.target.value; saveLocal(); renderSummary(); });
levelInput.addEventListener("input", (e) => { 
  let v = parseInt(e.target.value || "1", 10);
  if (isNaN(v)) v = 1;
  v = Math.max(1, Math.min(10, v));
  state.meta.level = v;
  state.current.level = v;
  saveLocal(); recompute();
});
document.getElementById("incLevel").onclick = () => { levelInput.value = Math.min(10, parseInt(levelInput.value||"1",10)+1); levelInput.dispatchEvent(new Event('input')); };
document.getElementById("decLevel").onclick = () => { levelInput.value = Math.max(1, parseInt(levelInput.value||"1",10)-1); levelInput.dispatchEvent(new Event('input')); };

classSelect.addEventListener("change", (e) => {
  state.current.class = e.target.value;
  populateClassUI();
  saveLocal(); recompute();
});
subclassSelect.addEventListener("change", (e) => {
  state.current.subclass = e.target.value;
  saveLocal(); recompute();
});

for (const k of Object.keys(tInputs)) {
  tInputs[k].addEventListener("input", (e) => {
    state.current.traits[k] = parseInt(e.target.value || "0", 10) || 0;
    saveLocal(); renderSummary();
  });
}
hpInput.addEventListener("input", (e) => { state.current.hp = parseInt(e.target.value||"6",10)||6; saveLocal(); renderSummary(); });
evasionInput.addEventListener("input", (e) => { state.current.evasion = parseInt(e.target.value||"10",10)||10; saveLocal(); renderSummary(); });
heritageFeatures.addEventListener("input", (e) => { state.current.heritage.features = e.target.value; saveLocal(); renderSummary(); });
ancestryInput.addEventListener("input", (e) => { state.current.heritage.ancestry = e.target.value; saveLocal(); renderSummary(); });
communityInput.addEventListener("input", (e) => { state.current.heritage.community = e.target.value; saveLocal(); renderSummary(); });
exp1.addEventListener("input", (e) => { state.current.experiences[0] = e.target.value; saveLocal(); renderSummary(); });
exp2.addEventListener("input", (e) => { state.current.experiences[1] = e.target.value; saveLocal(); renderSummary(); });

domainFilter.addEventListener("change", renderCardsList);
cardSearch.addEventListener("input", renderCardsList);

document.getElementById("nextLevel").onclick = () => {
  state.meta.level = Math.min(10, (state.meta.level||1)+1);
  state.current = state.build[state.meta.level] || levelTemplate(state.meta.level);
  saveLocal(); recompute();
};

document.getElementById("prevLevel").onclick = () => {
  state.meta.level = Math.max(1, (state.meta.level||1)-1);
  state.current = state.build[state.meta.level] || levelTemplate(state.meta.level);
  saveLocal(); recompute();
};

function lockThisLevel() {
  // snapshot current
  state.build[state.current.level] = JSON.parse(JSON.stringify(state.current));
  saveLocal(); renderSummary();
  // lightweight toast
  alert(`Level ${state.current.level} locked!`);
}
document.getElementById("lockLevelBtn").onclick = lockThisLevel;
document.getElementById("lockLevelBtn2").onclick = lockThisLevel;

document.getElementById("resetBtn").onclick = () => {
  if (!confirm("This will clear the builder (local only). Continue?")) return;
  localStorage.removeItem("dhcc_builder_state");
  state.meta = { name: "", level: 1 };
  state.build = {};
  state.current = levelTemplate(1);
  saveLocal(); recompute();
};

document.getElementById("exportBtn").onclick = () => {
  const out = {
    name: state.meta.name || "Unnamed Character",
    final_level: Math.max(...Object.keys(state.build).map(k=>parseInt(k)).concat([state.meta.level])),
    levels: state.build
  };
  const blob = new Blob([JSON.stringify(out, null, 2)], {type: "application/json"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = (state.meta.name || "character") + ".daggerheart.json";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
};

async function loadCards() {
  const fallback = DEFAULT_CARDS;
  try {
    const res = await fetch("./domain_cards.json", {cache:"no-store"});
    if (res.ok) {
      const data = await res.json();
      // Normalize minimal fields
      state.domainCards = (Array.isArray(data)? data: (data.cards||data)) .map(c => ({
        name: c.name, domain: c.domain || c.Domain || "Unknown", level: c.level || c.Level || 1, type: c.type || c.Type || "", recall_cost: c.recall_cost ?? c.recallCost ?? null, description: c.description || c.text || ""
      }));
    } else {
      state.domainCards = fallback;
    }
  } catch (e) {
    state.domainCards = fallback;
  }

  // Fill domain filter
  const domains = Array.from(new Set(state.domainCards.map(c => c.domain))).sort();
  domainFilter.innerHTML = "<option value=''>— All —</option>" + domains.map(d => `<option>${d}</option>`).join("");
  renderCardsList();
}

function initFromLocal() {
  loadLocal();
  if (!state.current || typeof state.current !== "object") state.current = levelTemplate(state.meta.level || 1);
  recompute();
}

window.addEventListener("DOMContentLoaded", async () => {
  initFromLocal();
  await loadCards();
});
