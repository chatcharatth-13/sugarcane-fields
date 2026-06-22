# Cloud setup — shared autosave (Firebase)

The app works **offline by default** (saves in each browser). To let a team share
one live dataset that **autosaves to the cloud**, connect Firebase. One-time setup,
~10 minutes, free.

## 1. Create a Firebase project
1. Go to <https://console.firebase.google.com> → **Add project** (any name) → create.
   You can disable Google Analytics.

## 2. Enable Firestore
1. Left menu → **Build → Firestore Database → Create database**.
2. Start in **production mode**, pick a location (e.g. `asia-southeast1`).
3. Open the **Rules** tab, paste this **Firestore-backed allowlist** rule, and **Publish**:
   ```
   rules_version = '2';
   service cloud.firestore {
     match /databases/{database}/documents {
       function authed() {
         return request.auth != null
           && request.auth.token.email_verified == true
           && request.auth.token.firebase.sign_in_provider == 'google.com';
       }
       function em() { return request.auth.token.email.lower(); }
       // OWNER: hardcoded super-admin. Keep in sync with OWNER_EMAIL in
       // app/field_manager.html and app/manage_access.html.
       function isOwner()   { return authed() && em() == 'chatcharat.13@gmail.com'; }
       // ALLOWED: the owner, or any email present in the allowed_users collection
       // (managed from app/manage_access.html — no code change / redeploy needed).
       function isAllowed() { return authed() &&
         ( em() == 'chatcharat.13@gmail.com'
           || exists(/databases/$(database)/documents/allowed_users/$(em())) ); }

       match /workspaces/{ws}/{document=**} {
         allow read, write: if isAllowed();
       }
       match /allowed_users/{e} {
         allow read:  if isOwner() || (authed() && e == em());   // owner lists all; a user can check only their own
         allow write: if isOwner();                              // only the owner grants/revokes
       }
       // everything else: default-deny (no match = denied)
     }
   }
   ```
   The `/{document=**}` is **required** — fields are stored as individual
   documents in a `fields` subcollection, and this recursive match covers them.
   **This is the real privacy control.** Access = the **owner** OR an email in the
   Firestore **`allowed_users`** collection. **Add/remove people on the
   `app/manage_access.html` admin page** (owner-only) — it edits `allowed_users`
   and changes take effect **immediately, no redeploy / no rule edit**. Only the
   hardcoded owner can write the allowlist; anonymous users (no verified email) are
   always denied; forged tokens are impossible (Firestore verifies the JWT
   server-side). The owner email is hardcoded in 3 places that must match:
   `OWNER_EMAIL` in `app/field_manager.html`, `OWNER_EMAIL` in
   `app/manage_access.html`, and `isOwner()` here.

## 3. Enable Google sign-in (the app is gated behind it)
1. **Build → Authentication → Get started → Sign-in method**.
2. Enable **Google** → pick a support email → Save.
3. **Do NOT enable Anonymous** (and disable it if it's on). The app no longer uses
   anonymous auth; leaving it on is a hole — an anonymous token satisfies
   `request.auth != null` and is the only way to be signed-in without an
   allowlisted Google account. Disable it **after** confirming sign-in + the
   maintenance tools work.
4. The app shows a **"Sign in with Google"** gate before any content loads; only
   the owner + emails in the `allowed_users` collection (managed on
   `app/manage_access.html`) get in. Everyone else sees only the login screen.

## 4. Authorize your site's domain
**Authentication → Settings → Authorized domains → Add domain**. Add wherever you
host the app, e.g. `localhost` (for testing) and `<you>.github.io` (GitHub Pages) or
your Firebase Hosting domain. (`*.web.app`/`*.firebaseapp.com` are pre-authorized.)

## 5. Get the web config + paste it
1. Project **Settings (gear) → General → Your apps → Web app (`</>`)** → register.
2. Copy the `firebaseConfig` values into **`app/firebase-config.js`**:
   ```js
   window.FIREBASE_CONFIG = {
     apiKey: "AIza…",
     authDomain: "yourproj.firebaseapp.com",
     projectId: "yourproj",
     appId: "1:…:web:…"
   };
   ```
   This config is **not secret** — it's safe to commit/deploy. Security is the
   Firestore rules + the workspace code.

## 6. Use it
- Deploy the `app/` folder (see DEPLOY.md). Open the site, click **☁** (top-right).
- Enter a **workspace code** (a shared secret your team agrees on — use a long random
  one, e.g. `siteam-7Kq2m9`) and **your name**, then **เชื่อมต่อ / เข้าร่วม**.
- Everyone who enters the **same code** edits the **same** stations/fields/quotas,
  updating live (~1–2 s). Each field records who added it. The link
  `…/app/field_manager.html#ws=siteam-7Kq2m9` joins that workspace directly.

## Notes / limits
- **Shared-code security**: anyone with the code/link can edit. Fine for a trusted
  team; use a long random code. Google sign-in is a clean upgrade later (same data).
- **Free (Spark) tier**: ~20k writes / 50k reads per day, 1 GiB storage. Saves are
  debounced; ample for a small team. The whole workspace is one document (Firestore
  limit 1 MB) — plenty for hundreds of fields; thousands would need the paid tier or
  a per-field model.
- **Concurrency**: last save wins for the whole workspace; with a small team editing
  different things this is rarely an issue, and others' changes appear within seconds.
- Remove the code (**ออกจากออนไลน์**) to go back to offline/local mode.
