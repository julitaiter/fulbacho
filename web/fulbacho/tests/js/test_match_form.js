const test = require("node:test");
const assert = require("node:assert/strict");
const {
  goalValuesAfterIdentityChange,
  normalizeMinimum,
  participantKind,
  reconcileSlots,
} = require("../../static/js/match-form.js");

test("format increase adds the required minimum slots", () => {
  const result = reconcileSlots([{filled: true}, {filled: false}], 5);
  assert.equal(result.length, 5);
  assert.equal(result[0].filled, true);
});

test("format decrease removes only empty excess slots", () => {
  const slots = [
    {filled: true, id: "a"},
    {filled: true, id: "b"},
    {filled: false, id: "empty"},
    {filled: true, id: "extra"},
  ];
  const result = reconcileSlots(slots, 2);
  assert.deepEqual(result.map((slot) => slot.id), ["a", "b", "extra"]);
});

test("format decrease preserves all loaded extras", () => {
  const result = reconcileSlots(
    [{filled: true}, {filled: true}, {filled: true}],
    1
  );
  assert.equal(result.length, 3);
});

test("manual text changes invalidate a regular selection", () => {
  assert.equal(participantKind("Ana", "player-1", "Ana"), "regular");
  assert.equal(participantKind("Ana editada", "", ""), "casual");
  assert.equal(participantKind("", "", ""), "empty");
});

test("minimum is constrained to the supported form range", () => {
  assert.equal(normalizeMinimum("0"), 1);
  assert.equal(normalizeMinimum("8"), 8);
  assert.equal(normalizeMinimum("80"), 50);
  assert.equal(normalizeMinimum("invalid"), 5);
});

test("goals follow the slot identity and reset when its participant changes", () => {
  const values = {goals: "2", ownGoals: "1"};
  assert.equal(
    goalValuesAfterIdentityChange("p:1", "p:1", values),
    values
  );
  assert.deepEqual(
    goalValuesAfterIdentityChange("p:1", "c:Nuevo", values),
    {goals: "0", ownGoals: "0"}
  );
});
