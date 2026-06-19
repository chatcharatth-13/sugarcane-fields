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
3. Open the **Rules** tab, paste this, and **Publish**:
   ```
   rules_version = '2';
   service cloud.firestore {
     match /databases/{database}/documents {
       match /workspaces/{ws} {
         allow read, write: if request.auth != null;
       }
     }
   }
   ```
   This allows any signed-in (anonymous) user to read/write a workspace — the
   protection is the **unguessable workspace code** (see §6). To tighten later,
   switch to Google sign-in.

## 3. Enable Anonymous sign-in
1. **Build → Authentication → Get started → Sign-in method**.
2. Enable **Anonymous** → Save.

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
