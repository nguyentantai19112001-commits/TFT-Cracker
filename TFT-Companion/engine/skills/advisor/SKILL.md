# SKILL: advisor — Haiku + tool-use narrator (Phase 6)

> Refactor `advisor.py` from Sonnet-4.6-freeform-JSON to Haiku-4.5-with-tool-use. The
> advisor no longer decides; it picks from top-3 and writes the verdict.

**Prerequisites:** Phases 0-5 complete.

## Purpose

The advisor becomes a narrator. By Phase 5, `recommender.top_k` already produced the
top-3 actions with numeric scores. The advisor's job is:

1. Pick the best of those 3 using qualitative context (scout info, comp cohesion, "feel")
2. Write a one-line verdict + 2-3 sentence reasoning
3. Optionally call tools (econ, comp_planner) to fetch extra context for the narration

Because the hard decision is already done, **Haiku is sufficient**. This saves ~5× on
advisor cost.

## Files you may edit

- `advisor.py` (full refactor)
- `tests/test_advisor.py` (extend existing)
- `tests/test_advisor_stream.py` (extend existing)
- `assistant_overlay.py` (PipelineWorker — wire recommender + comp_planner in before
  advisor call. This is the integration pass.)

## Public API

Keep the existing streaming contract. Callers (PipelineWorker) shouldn't change shape.

```python
# advisor.py
from anthropic import Anthropic
from schemas import (
    GameState, Fire, ActionCandidate, CompCandidate, AdvisorVerdict,
)

MODEL = "claude-haiku-4-5-20251001"
PROMPT_VERSION = "advisor_v2"

def advise_stream(
    state: GameState,
    fires: list[Fire],
    actions: list[ActionCandidate],    # top-3 from recommender
    comps: list[CompCandidate],         # top-3 from comp_planner
    client: Anthropic,
    capture_id: int | None = None,
) -> Iterator[tuple[str, object]]:
    """Streaming generator. Yields:
        ("one_liner", str)   — as soon as the first JSON string closes
        ("reasoning", str)   — as soon as reasoning closes
        ("final", {"verdict": AdvisorVerdict, "__meta__": {...}}) — terminal
    """
```

## System prompt (the contract)

```
You are a Challenger-level Teamfight Tactics coach. You will receive:
- Current game state
- Deterministic rule fires
- Top-3 candidate actions from the recommender, each with numeric scores
- Top-3 reachable comps from the comp planner

Your job:
1. Pick the best action from the provided top-3. Do NOT invent a new action.
2. Use qualitative context (scout reads, comp cohesion, "feel") to choose among
   near-equivalent options.
3. Write a one-line imperative verdict + 2-3 sentence reasoning that references the
   numeric scores and comp context.

You may call these tools if you need extra context:
- econ_p_hit: compute P(hit) for a specific champion
- comp_details: look up full archetype info for a reachable comp

You MUST NOT invent numbers. If a number isn't in the state or a tool result, don't
cite it.

Return a JSON object with keys in this order (streaming depends on order):
{
  "one_liner": "<imperative sentence, <=120 chars>",
  "confidence": "HIGH|MEDIUM|LOW",
  "tempo_read": "AHEAD|ON_PACE|BEHIND|CRITICAL",
  "primary_action": "<ActionType matching the chosen candidate>",
  "chosen_candidate_index": <0|1|2>,
  "reasoning": "<2-4 sentences referencing scores + comps>",
  "considerations": ["<secondary point>", ...],
  "warnings": ["<warning>", ...],
  "data_quality_note": "<null or note>"
}
```

## Tools the advisor can call

Keep the tool set minimal. Two tools cover every use case:

```python
TOOLS = [
    {
        "name": "econ_p_hit",
        "description": (
            "Compute probability of hitting a champion given current state. "
            "Use when you want to confirm or cite a specific P(hit) number."
        ),
        "input_schema": {
            "type": "object",
            "required": ["champion", "gold"],
            "properties": {
                "champion": {"type": "string"},
                "gold": {"type": "integer", "minimum": 0},
            },
        },
    },
    {
        "name": "comp_details",
        "description": (
            "Get full details of a reachable archetype — core units, items, playstyle. "
            "Use when you want to reference specific units in reasoning."
        ),
        "input_schema": {
            "type": "object",
            "required": ["archetype_id"],
            "properties": {"archetype_id": {"type": "string"}},
        },
    },
]
```

Tool call handlers:

```python
def _handle_tool_call(tool_name: str, tool_input: dict, state, pool, set_, archetypes) -> dict:
    if tool_name == "econ_p_hit":
        pool_state = pool.to_pool_state(tool_input["champion"])
        analysis = econ.analyze_roll(
            target=tool_input["champion"],
            level=state.level,
            gold=tool_input["gold"],
            pool=pool_state,
            set_=set_,
        )
        return {
            "p_hit_at_least_1": analysis.p_hit_at_least_1,
            "p_hit_at_least_2": analysis.p_hit_at_least_2,
            "expected_copies": analysis.expected_copies_seen,
        }
    if tool_name == "comp_details":
        arch = next((a for a in archetypes if a.archetype_id == tool_input["archetype_id"]), None)
        if not arch:
            return {"error": f"Unknown archetype: {tool_input['archetype_id']}"}
        return arch.model_dump()
    return {"error": f"Unknown tool: {tool_name}"}
```

## Streaming implementation

Keep the existing streaming pattern (emit `one_liner` as soon as that JSON string
closes, then `reasoning`, then `final`). The existing helper
`_extract_complete_string_field(buf, key)` from v1 advisor works as-is.

Tool-use makes streaming slightly more complex. Pattern:
1. Call `client.messages.stream(...)` with tools.
2. If the model emits a `tool_use` block, stop the stream, execute the tool, continue
   with `tool_result`. (Use Anthropic's `stream` context manager; see SDK docs.)
3. Emit partial `one_liner` / `reasoning` from the final text response.

If streaming-with-tools gets hairy, fall back to non-streaming for tool-use turns and
only stream when there are no tool calls. Haiku is fast enough that non-streaming is
still ~2-3s.

## Integration step — `assistant_overlay.py` PipelineWorker

Update the `run()` method:

```python
def run(self) -> None:
    try:
        self.extractingStarted.emit()
        t0 = time.time()
        png = capture_screen()
        game_id = session.current_game_id()

        state = build_state(png, self.client, game_id=game_id, trigger="hotkey")
        if not state.sources.vision_ok:
            self.errorOccurred.emit(f"Vision failed: {state.sources.vision_error}")
            return
        self.stateExtracted.emit(state.model_dump())

        # NEW: pool tracker is already updated inside build_state
        from state_builder import get_tracker
        pool = get_tracker(knowledge.load_set(state.set_id))

        # NEW: planner + recommender run BEFORE advisor
        set_ = knowledge.load_set(state.set_id)
        core = knowledge.load_core()
        archetypes = comp_planner.load_archetypes()

        fires = rules.evaluate(state, econ, pool, knowledge)
        comps = comp_planner.top_k_comps(state, pool, archetypes, set_, k=3)
        actions = recommender.top_k(state, fires, comps, pool, set_, core, k=3)

        # Advisor streams over the results
        for evt, payload in advisor.advise_stream(
            state=state, fires=fires, actions=actions, comps=comps,
            client=self.client, capture_id=state.capture_id,
        ):
            if evt == "one_liner":   self.verdictReady.emit(payload)
            elif evt == "reasoning": self.reasoningReady.emit(payload)
            elif evt == "final":
                recommendation = payload.get("verdict")
                meta = payload.get("__meta__")
                break
        ...
```

## Acceptance tests

```python
def test_advisor_model_is_haiku():
    from advisor import MODEL
    assert "haiku" in MODEL.lower()

def test_advisor_picks_from_top_k(mock_client):
    state, fires, actions, comps = _mock_inputs()
    events = list(advise_stream(state, fires, actions, comps, mock_client))
    final = next((e for e in events if e[0] == "final"), None)
    assert final is not None
    verdict = final[1]["verdict"]
    assert verdict.chosen_candidate in actions  # not invented

def test_advisor_does_not_invent_numbers(live_client_or_recorded):
    """On a fixture scenario, every number in reasoning string must appear in state or
    in a tool result we served."""
    state, fires, actions, comps = _fixture("uncontested_jinx_roll")
    events = list(advise_stream(state, fires, actions, comps, live_client_or_recorded))
    reasoning = next((e[1] for e in events if e[0] == "reasoning"), "")
    numbers_in_reasoning = re.findall(r"\b\d+(?:\.\d+)?%?\b", reasoning)
    # every number must be traceable to state or tool calls
    for num in numbers_in_reasoning:
        assert _number_is_traceable(num, state, _captured_tool_results)

def test_cost_under_005(record_with_live_api):
    """One advisor call on a fixture must cost less than $0.005."""
    ...
    assert meta["cost_usd"] < 0.005

def test_streaming_emits_one_liner_first():
    events = list(advise_stream(...))
    event_types = [e[0] for e in events]
    assert event_types.index("one_liner") < event_types.index("reasoning") < event_types.index("final")
```

## STATE.md entry

```
## Phase 6 — DONE YYYY-MM-DD
- edited: advisor.py (full refactor, 300 LOC diff)
- edited: assistant_overlay.py (PipelineWorker wiring for recommender + comp_planner)
- tests: 4/4 advisor tests passing including 1 live API cost test
- measured: $0.0035 avg advisor cost (Haiku), 2.1s first token, 4.8s total
- total pipeline cost per F9: $0.018 (was $0.02 in v1)
```

## Anti-patterns to avoid

- Do not let the advisor output an action that isn't in the top-3 provided. If it does,
  overlay shows an error; fix the prompt.
- Do not give the advisor all 15-25 candidates from enumeration. Top-3 only. Narration
  quality degrades fast with too many options.
- Do not add memory / history across F9 presses at this layer. That's a future concern.
- Do not make the advisor re-compute numbers by calling tools for every claim. Trust
  the provided state + action scores. Tools are for "I want to *confirm* this specific
  number for the narration."
- Do not switch back to Sonnet if output quality dips. First, check that the recommender
  is actually giving a meaningfully-ordered top-3. Bad narrator output usually traces
  back to bad recommender output.
