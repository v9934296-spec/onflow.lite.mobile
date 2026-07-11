# P.T.E. MANIFESTO

**The Progression Tracking Engine exists to tell skaters the truth about their skating.**
Every line of P.T.E. code answers to this document. If code and manifesto disagree, the code is wrong.

---

## Principle Zero

**P.T.E. exists to measure progression, not to maximize engagement.**
Every principle below is this one wearing work clothes. Any feature whose real job is opening the app more often — not measuring skating better — doesn't belong in the engine.

## The Eight Principles

**1. We never invent evidence.**
Every claim traces to something the system actually observed. If Pegasus didn't see it, P.T.E. doesn't say it. No inferred landings, no assumed rotations, no filled-in gaps. A blank is more honest than a guess.

**2. We never hide uncertainty.**
Every output carries its evidence class — `DETECTED`, `ESTIMATE`, or `NO EVIDENCE` — visible to the user, not buried in metadata. If we're not sure, the skater knows we're not sure.

**3. Every score must be reproducible.**
Traceable says why; reproducible says the same clip, run through the same engine version, yields the same result — six months later, by a different engineer. Where an underlying model is stochastic, the recorded result is canonical and any re-run is labeled as a re-run. A score that can't be reproduced or decomposed into its observations doesn't ship.

**4. Confidence is earned, not assumed.**
Model output starts untrusted. Confidence comes from validation runs and measured accuracy — the 300-run test, not the vendor's marketing page. **Every engine version maintains its own validation benchmark.** No version inherits its predecessor's reputation; a new model, prompt, or pipeline change resets to untrusted until it proves itself empirically.

**5. Missing evidence is a valid result.**
Abstention is a first-class output, not an error state. "The landing isn't in frame" is a complete, correct, shippable answer. The refusal to rate is the reason the ratings we do give mean something.

**6. Deterministic measurements override generative opinions.**
Where we can measure — duration, frame counts, timestamps, pixel-space geometry — the measurement wins. Generative analysis fills in what math can't reach, never the reverse. When a model's prose contradicts a measured value, the measurement stands and the prose is discarded.

**7. Every improvement claim must survive statistical scrutiny.**
"You're getting better" is a statistical claim, and three lucky makes aren't a trend. Improvement is declared only when the logged record clears defined thresholds — sample size, comparable conditions, significance — and those thresholds live in versioned code, not in vibes. Flat progress gets reported flat; that honesty is what makes the up-days real.

**8. The engine must age gracefully.**
No improvement to P.T.E. may silently rewrite a skater's history. Every stored analysis is stamped with its engine version; a better engine never overwrites an old score — it offers a labeled re-analysis alongside it. Yesterday's 8.4 never quietly becomes today's 7.6.

---

## The Gate

Every future P.T.E. feature — every metric, badge, streak, comparison, coach line, or chart — must pass all of these before a line of code is written:

> *Does it measure or does it engage? Does it invent? Does it hide? Can it reproduce? Did it earn? Can it abstain? Does math outrank prose? Would it survive statistics? Does it respect history?*

**One "no" kills the feature.** No exceptions for engagement, retention, or revenue.

---

*User trust over short-term revenue. Honest labeling over impressive numbers. Since day one.*

**The moment P.T.E. flatters a skater to keep them opening the app, it's worthless.**
