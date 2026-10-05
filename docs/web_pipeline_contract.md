# Web pipeline state contract

The web service uses the production `execute_layer` guards and finalizer. UI
integration changes do not add model calls, semantic retries, candidate search
or age calls. A web request still asks for only its selected age.

## Events and terminal states

`start` supplies display tokens. `layer_start` says the service is checking a
stage and its prerequisites; it does not claim that a skipped layer ran.
L0-pre, L1–L8 and L0-post completion events carry their actual trace status,
reason, duration and available provider metadata. Dependency skips stay
`SKIPPED`; missing results do not become an invented genre, successful lookup
or model assessment. L3 events expose the complete original shortlist.

Every 15 seconds while a layer remains pending, `waiting` reports that same
layer. It also keeps the SSE connection alive. The UI does not rotate through
imaginary steps or assume which provider is running.

Candidate highlights have their own presentation timeline: after a successful
L3 shortlist arrives, matching source words appear in reading order, 1.5 seconds
apart. This can continue across later layers;
the separate stage label and trace still show the actual backend state.
Highlights are possible wordplay sites, not confirmed meanings. The current-word
message does not display a reveal count or candidate total. A detection
failure/unknown, interrupted stream or final response cancels pending reveals.
The final response does not wait for the animation queue. Reduced-motion
preferences show the shortlist without stagger or glow. No model calls are
added for animation.

The editor remains in the layout during scanning. Its text area, status and
controls retain their measured space, and the input section keeps its starting
position as trace entries appear. The stage label occupies the gap between
the title and the scanner card, so the input has no empty status row above it
inside the card. The original 300 ms word-spacing transition,
expanded candidate boxes, scanner beam, punchline halo and desktop flight are
preserved. On desktop, ordinary tokens use 2 px side margins and 4 px padding;
candidate tokens use 8 px side margins, 10 px horizontal padding, 6/8 px
vertical padding and a 2 px dashed border, as in `0c674f0`. Word spacing can
change while the card stays anchored. Compact screens wrap these tokens;
desktop scales the line as its width animates. A viewport resize releases the
old measurements so the compact layout can adapt.

The desktop flight keeps its 850 ms glide. Scanner and report tokens share the
same final typography and spacing, with each container's scale measured
independently before flight. Text scales uniformly, and the report becomes
visible only when the flight actually finishes; there is no timer-based swap
to differently sized text. A viewport resize during flight removes the proxy
and shows the report in its current layout. Age and appropriateness badges
stay on one line; their heading rows wrap when space is limited.

| Final state | UI behavior |
|---|---|
| `PUN` | Display validated readings and exact source anchors. A/B order is neutral; the resolving reading comes from `resolving_sense`. |
| `NON_PUN` | Display the explicit rejection; hide proposed dual meanings and wordplay-age panels. |
| `INSUFFICIENT_EVIDENCE` | Request context/review; do not display a negative verdict or fabricated punchline. |
| `EXECUTION_FAILED` | Display execution failure and retry/review action, with the trace opened. Setup and payload-construction failures use the same failure envelope. |
| `OUT_OF_SCOPE` | Display the mechanism boundary and review action. |
| Missing, contradictory or malformed detection response | Close the stream and return to the preserved input with an inline error. No detection decision is fabricated. |
| Connection ends before `complete` | Preserve text and received stage states; ask for an explicit retry. The client closes EventSource and does not automatically reconnect or resubmit. |

GET streaming and POST analysis enforce the same 1–1000-character request
length and 4–18 age bounds. Local input validation still runs in L0-pre.

## Age and recovery visibility

Each displayed age separately carries comprehension and appropriateness
execution states: `ASSESSED`, `UNKNOWN`, `EXECUTION_FAILED`, `SKIPPED`, or
`NOT_REQUESTED`. A comprehension barrier followed by an L8 dependency skip is
a partial age assessment, not a pending request. Failed/unknown age evidence
does not revoke a confirmed detection result or imply suitability. A malformed
age display payload is isolated from a structurally valid detection result.
Appropriateness axes are tied to the selected age; empty issue lists do not
make missing axes pass.

The trace exposes L4 attempts, L5 result metadata and, for new executions,
L6's separately persisted provider metadata. A visible recovery notice lists
recorded application backoff retries/model fallback. Counters describe application
backoff recovery, not total HTTP requests; SDK retries, request-option
compatibility retries and Gemini L5's separate rate-limit retry are excluded. Metadata arrives after a layer returns, not during each retry.
A provider exception can prevent counters from being returned. Unavailable
metadata stays explicit, rather than being displayed as zero retries.

## Verification

`tests/test_web_contract.py` exercises both API paths with the production
registry and offline provider responses: exceptions in each detection stage,
unknowns, assessed rejections, age-only failures, recovery metadata, setup and
projection failure envelopes, waiting events, resolving-sense order and request
bounds. These tests verify integration behavior, not model accuracy.

```bash
pytest -q tests/test_web_contract.py tests/test_reliability.py -m 'not live'
```
