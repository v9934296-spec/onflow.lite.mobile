# OnFlow Lite Production Hardening QA

This checklist is the release gate for the production-hardening branch. Automated checks are necessary but do not replace a physical-device EAS build.

## Build prerequisites

- [ ] EAS `preview` and `production` environments contain `EXPO_PUBLIC_API_URL`.
- [ ] `EXPO_PUBLIC_LEGAL_BASE_URL` points to the deployed legal site, or the checked-in default is confirmed.
- [ ] The Apple Developer App ID for `com.onflow.lite` has Sign in with Apple enabled.
- [ ] EAS credentials and the provisioning profile are regenerated after enabling the capability.
- [ ] The backend environment used by the build is reachable from a physical iPhone.

## Automated gate

Run from the repository root:

```bash
npm ci
npm run typecheck
npm test
npm run bundle:ios
```

All commands must pass from a clean checkout.

## Physical iPhone test matrix

### 1. Authentication and secure sign-out

- [ ] Install a fresh EAS preview build, not Expo Go.
- [ ] Sign in with Apple succeeds.
- [ ] Relaunching the app restores the signed-in session.
- [ ] Sign out returns to the sign-in screen.
- [ ] Relaunching after sign-out does not restore the old session.
- [ ] Canceling Apple sign-in does not show a false failure or create a session.

### 2. Account isolation

Use two distinct accounts on the same device.

- [ ] Account A creates a session, logs attempts, completes the session, and creates history.
- [ ] Account A signs out.
- [ ] Account B signs in and sees none of Account A's attempts, clip log, active session, recap, or history.
- [ ] Account B signs out and Account A signs back in.
- [ ] Account A's own local data is restored.

### 3. Core milestone loop

- [ ] Open app.
- [ ] Start session.
- [ ] Choose a trick.
- [ ] Log Land and Miss.
- [ ] End session.
- [ ] View recap.
- [ ] Return home.
- [ ] Reopen the completed session from history.
- [ ] Rapidly tapping Land or Miss creates only one attempt per accepted action.

### 4. Session completion recovery

- [ ] Start a session and log attempts.
- [ ] End the session while briefly interrupting connectivity.
- [ ] Force-close and reopen the app.
- [ ] The app completes or retries finalization without losing the recap.
- [ ] The ended backend session is not shown as active.
- [ ] The recap appears exactly once in history.

### 5. Clip validation and upload

- [ ] A supported MP4 clip under 15 seconds and 75 MB uploads successfully.
- [ ] Upload progress visibly advances.
- [ ] A clip longer than 15 seconds is rejected before upload.
- [ ] A clip larger than 75 MB is rejected before upload.
- [ ] Canceling the image picker does not produce an error.
- [ ] Camera denial explains how to enable access in Settings.
- [ ] Poor connectivity produces a retryable error instead of an indefinite spinner.

### 6. Analysis recovery

- [ ] Upload a clip and wait until analysis polling begins.
- [ ] Force-close the app before analysis completes.
- [ ] Relaunch and confirm Home shows `Analysis in progress`.
- [ ] Tap `Resume analysis` and receive the completed result.
- [ ] A permanent missing/unauthorized job stops without repeated requests.
- [ ] A temporary network failure can be retried.
- [ ] A failed analysis clears the pending job and permits a new capture.

### 7. Honest result presentation

- [ ] Technique rating is displayed only when returned by the backend.
- [ ] Confidence displays only when the backend returns an explicit calibrated percentage.
- [ ] Otherwise the UI says `CONFIDENCE NOT PROVIDED`.
- [ ] Insufficient evidence produces `NO RATING` and an abstention reason.
- [ ] A malformed completed-job response produces an error, not invented feedback.

### 8. Feed, paywall, settings, and legal

- [ ] Feed loading, empty, refresh, pagination, and error states work.
- [ ] Paywall clearly states that purchases are not wired in Lite.
- [ ] No button implies that a purchase can be completed when it cannot.
- [ ] Notifications clearly state that push is not enabled in Lite.
- [ ] Terms, Privacy, and Delete Account Information links open successfully.

## Release decision

The build is eligible for external TestFlight only when:

1. CI passes from a clean checkout.
2. Every applicable physical-device item above passes.
3. Any intentionally unimplemented capability is labeled honestly in the UI and migration tracker.
4. No account-isolation, credential-storage, recap-loss, or analysis-recovery defect remains open.
