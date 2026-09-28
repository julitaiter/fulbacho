(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.MatchRoster = api;
  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", api.init);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function normalizeMinimum(value) {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? Math.min(50, Math.max(1, parsed)) : 5;
  }

  function reconcileSlots(slots, minimum) {
    const result = slots.slice();
    const floor = normalizeMinimum(minimum);
    while (result.length > floor) {
      let removable = -1;
      for (let index = result.length - 1; index >= floor; index -= 1) {
        if (!result[index].filled) {
          removable = index;
          break;
        }
      }
      if (removable < 0) break;
      result.splice(removable, 1);
    }
    while (result.length < floor) result.push({filled: false});
    return result;
  }

  function participantKind(name, playerId, selectedName) {
    if (!String(name || "").trim()) return "empty";
    return playerId && name === selectedName ? "regular" : "casual";
  }

  function goalValuesAfterIdentityChange(previousIdentity, nextIdentity, values) {
    if (previousIdentity === undefined || previousIdentity === nextIdentity) return values;
    return {goals: "0", ownGoals: "0"};
  }

  function init() {
    const form = document.querySelector("[data-match-editor]");
    if (!form || form.dataset.rosterReady === "true") return;
    form.dataset.rosterReady = "true";

    const optionsNode = document.getElementById("match-player-options");
    const players = optionsNode ? JSON.parse(optionsNode.textContent) : [];
    const playerById = new Map(players.map((player) => [String(player.id), player]));
    const minimumInput = form.querySelector('[name="players_per_team"]');
    const errorNode = form.querySelector("[data-roster-error]");
    const nextIndex = {A: 0, B: 0};

    function slots(side) {
      return Array.from(form.querySelectorAll(`[data-slots="${side}"] .participant-slot`));
    }

    function fields(row) {
      return {
        name: row.querySelector("[data-participant-name]"),
        playerId: row.querySelector("[data-player-id]"),
        suggestions: row.querySelector("[data-suggestions]"),
        goals: row.querySelector("[data-goals-input]"),
        ownGoals: row.querySelector("[data-own-goals-input]"),
      };
    }

    function usedPlayerIds(exceptRow) {
      return new Set(
        Array.from(form.querySelectorAll("[data-player-id]"))
          .filter((input) => input.closest(".participant-slot") !== exceptRow && input.value)
          .map((input) => input.value)
      );
    }

    function setError(message) {
      errorNode.textContent = message || "";
      errorNode.classList.toggle("visible", Boolean(message));
    }

    function updateKind(row) {
      const field = fields(row);
      const kind = participantKind(
        field.name.value,
        field.playerId.value,
        row.dataset.selectedName || ""
      );
      syncGoal(row, kind);
      return kind;
    }

    function closeSuggestions(row) {
      const field = fields(row);
      field.suggestions.hidden = true;
      field.suggestions.replaceChildren();
      field.name.setAttribute("aria-expanded", "false");
      row.dataset.activeOption = "-1";
    }

    function choosePlayer(row, player) {
      const field = fields(row);
      if (usedPlayerIds(row).has(String(player.id))) {
        setError(`${player.name} ya está incluido en el partido.`);
        return;
      }
      field.name.value = player.name;
      field.playerId.value = String(player.id);
      row.dataset.selectedName = player.name;
      field.name.setCustomValidity("");
      setError("");
      closeSuggestions(row);
      updateKind(row);
    }

    function renderSuggestions(row) {
      const field = fields(row);
      const query = field.name.value.trim().toLocaleLowerCase("es");
      const used = usedPlayerIds(row);
      const matches = players
        .filter((player) => !used.has(String(player.id)))
        .filter((player) => !query || player.name.toLocaleLowerCase("es").includes(query))
        .slice(0, 8);
      field.suggestions.replaceChildren();
      for (const player of matches) {
        const option = document.createElement("button");
        option.type = "button";
        option.className = "autocomplete-option";
        option.setAttribute("role", "option");
        option.dataset.playerId = String(player.id);
        option.textContent = player.name;
        if (!player.active) {
          const suffix = document.createElement("small");
          suffix.textContent = " inactivo";
          option.appendChild(suffix);
        }
        option.addEventListener("mousedown", (event) => {
          event.preventDefault();
          choosePlayer(row, player);
        });
        field.suggestions.appendChild(option);
      }
      field.suggestions.hidden = matches.length === 0;
      field.name.setAttribute("aria-expanded", matches.length ? "true" : "false");
      row.dataset.activeOption = "-1";
    }

    function navigateSuggestions(row, event) {
      const field = fields(row);
      const options = Array.from(
        field.suggestions.querySelectorAll(".autocomplete-option")
      );
      if (
        !options.length ||
        !["ArrowDown", "ArrowUp", "Enter", "Escape"].includes(event.key)
      ) return;
      event.preventDefault();
      if (event.key === "Escape") {
        closeSuggestions(row);
        return;
      }
      let active = Number(row.dataset.activeOption || -1);
      if (event.key === "ArrowDown") active = Math.min(options.length - 1, active + 1);
      if (event.key === "ArrowUp") active = Math.max(0, active - 1);
      if (event.key === "Enter" && active >= 0) {
        const player = playerById.get(options[active].dataset.playerId);
        if (player) choosePlayer(row, player);
        return;
      }
      options.forEach((option, index) =>
        option.classList.toggle("active", index === active)
      );
      row.dataset.activeOption = String(active);
    }

    function syncGoal(row, kind) {
      const field = fields(row);
      const name = field.name.value.trim();
      const identity =
        kind === "regular" ? `p:${field.playerId.value}` : name ? `c:${name}` : "";
      const values = goalValuesAfterIdentityChange(
        row.dataset.goalIdentity,
        identity,
        {goals: field.goals.value, ownGoals: field.ownGoals.value}
      );
      row.dataset.goalIdentity = identity;
      row.dataset.goals = values.goals;
      row.dataset.ownGoals = values.ownGoals;
      field.goals.value = values.goals;
      field.ownGoals.value = values.ownGoals;
    }

    function bindRow(row) {
      const field = fields(row);
      nextIndex[row.dataset.side] = Math.max(
        nextIndex[row.dataset.side],
        Number(row.dataset.index) + 1
      );
      field.name.addEventListener("focus", () => renderSuggestions(row));
      field.name.addEventListener("input", () => {
        if (field.name.value !== row.dataset.selectedName) {
          field.playerId.value = "";
          row.dataset.selectedName = "";
        }
        field.name.setCustomValidity("");
        setError("");
        renderSuggestions(row);
        updateKind(row);
      });
      field.name.addEventListener("keydown", (event) =>
        navigateSuggestions(row, event)
      );
      field.name.addEventListener("blur", () =>
        window.setTimeout(() => closeSuggestions(row), 100)
      );
      row.querySelector("[data-remove-slot]").addEventListener("click", () => {
        const minimum = normalizeMinimum(minimumInput.value);
        const teamSlots = slots(row.dataset.side);
        if (teamSlots.indexOf(row) < minimum) return;
        row.remove();
        reconcileTeam(row.dataset.side);
      });
      updateKind(row);
    }

    function createSlot(side) {
      const index = nextIndex[side]++;
      const row = document.createElement("article");
      row.className = "participant-slot";
      row.dataset.side = side;
      row.dataset.index = String(index);
      row.dataset.selectedName = "";
      row.dataset.goals = "0";
      row.dataset.ownGoals = "0";
      row.innerHTML = '<div class="participant-combobox"><input type="hidden" data-player-id><input type="text" maxlength="100" placeholder="Jugador o buscar…" autocomplete="off" role="combobox" aria-label="Jugador" aria-autocomplete="list" aria-expanded="false" data-participant-name><div class="autocomplete-list" role="listbox" hidden data-suggestions></div></div><input class="participant-goals" type="number" min="0" value="0" aria-label="Goles a favor" data-goals-input><input class="participant-goals" type="number" min="0" value="0" aria-label="Goles en contra" data-own-goals-input><button type="button" class="slot-remove" aria-label="Eliminar jugador" title="Eliminar jugador" data-remove-slot>×</button>';
      row.querySelector("[data-player-id]").name =
        `participant_${side}_player_id_${index}`;
      row.querySelector("[data-participant-name]").name =
        `participant_${side}_name_${index}`;
      row.querySelector("[data-goals-input]").name =
        `participant_${side}_goals_${index}`;
      row.querySelector("[data-own-goals-input]").name =
        `participant_${side}_own_goals_${index}`;
      form.querySelector(`[data-slots="${side}"]`).appendChild(row);
      bindRow(row);
      return row;
    }

    function reconcileTeam(side, pruneEmptyExtras = true) {
      const minimum = normalizeMinimum(minimumInput.value);
      let teamSlots = slots(side);
      while (teamSlots.length < minimum) {
        createSlot(side);
        teamSlots = slots(side);
      }
      for (let index = teamSlots.length - 1; pruneEmptyExtras && index >= minimum; index -= 1) {
        const row = teamSlots[index];
        if (!fields(row).name.value.trim()) row.remove();
      }
      teamSlots = slots(side);
      teamSlots.forEach((row, index) => {
        const remove = row.querySelector("[data-remove-slot]");
        const removable = index >= minimum;
        row.classList.toggle("removable", removable);
        remove.hidden = !removable;
        remove.disabled = !removable;
        fields(row).name.required = !removable;
      });
    }

    for (const side of ["A", "B"]) {
      slots(side).forEach(bindRow);
      form.querySelector(`[data-add-player="${side}"]`).addEventListener(
        "click",
        () => {
          const row = createSlot(side);
          reconcileTeam(side, false);
          fields(row).name.focus();
        }
      );
      reconcileTeam(side);
    }

    minimumInput.addEventListener("input", () => {
      const minimum = normalizeMinimum(minimumInput.value);
      for (const side of ["A", "B"]) reconcileTeam(side);
    });
    minimumInput.dispatchEvent(new Event("input"));

    form.addEventListener("submit", (event) => {
      const seen = new Set();
      let duplicate = "";
      for (const row of form.querySelectorAll(".participant-slot")) {
        const field = fields(row);
        if (field.playerId.value && field.name.value !== row.dataset.selectedName) {
          field.playerId.value = "";
        }
        if (field.playerId.value && seen.has(field.playerId.value)) {
          duplicate = field.name.value;
        }
        if (field.playerId.value) seen.add(field.playerId.value);
      }
      if (duplicate) {
        event.preventDefault();
        setError(`${duplicate} no puede aparecer más de una vez en el partido.`);
      }
    });

  }

  return {
    goalValuesAfterIdentityChange,
    init,
    normalizeMinimum,
    participantKind,
    reconcileSlots,
  };
});
