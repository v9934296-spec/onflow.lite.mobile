# P.T.E. MANIFESTO

**The Progression Tracking Engine exists to tell skaters the truth about their skating.**
Every line of P.T.E. code answers to this document. If code and manifesto disagree, the code is wrong.

---

## The Seven Principles

**1. We never invent evidence.**
Every claim traces to something the system actually observed. If Pegasus didn't see it, P.T.E. doesn't say it. No inferred landings, no assumed rotations, no filled-in gaps. A blank is more honest than a guess.

**2. We never hide uncertainty.**
Every output carries its evidence class — `DETECTED`, `ESTIMATE`, or `NO EVIDENCE` — visible to the user, not buried in metadata. Confidence intervals are shown, not smoothed away. If we're not sure, the skater knows we're not sure.

**3. Every score must be traceable.**
A rating is a conclusion, and conclusions have receipts. Any number P.T.E. produces can be decomposed into the observations that built it — which frames, which components, which weights. If a score can't explain itself, it doesn't ship.

**4. Confidence is earned, not assumed.**
Model output starts untrusted. Confidence comes from validation runs, cross-checks, and measured accuracy — the 300-run test, not the vendor's marketing page. A new model, prompt, or pipeline change resets to untrusted until it proves itself empirically.

**5. Missing evidence is a valid result.**
Abstention is a first-class output, not an error state. "The landing isn't in frame" is a complete, correct, shippable answer. The refusal to rate is a feature — it's the reason the ratings we do give mean something.

**6. Deterministic measurements override generative opinions.**
Where we can measure — duration, frame counts, timestamps, pixel-space geometry — the measurement wins. Generative analysis fills in what math can't reach, never the reverse. When a model's prose contradicts a measured value, the measurement stands and the prose is discarded.

**7. Every improvement claim must be measurable over time.**
"You're getting better" is a data claim. P.T.E. only says it when the logged record shows it — same trick, comparable conditions, real trend. No motivational inflation. Flat progress gets reported flat; that honesty is what makes the up-days real.

---

## The Gate

Every future P.T.E. feature — every metric, badge, streak, comparison, coach line, or chart — must pass all seven before a line of code is written:

> *Does it invent? Does it hide? Can it trace? Did it earn? Can it abstain? Does math outrank prose? Can time verify it?*

**One "no" kills the feature.** No exceptions for engagement, retention, or revenue. The moment P.T.E. flatters a skater to keep them opening the app, it's worthless — to them and to us.

---

*User trust over short-term revenue. Honest labeling over impressive numbers. Since day one.*
