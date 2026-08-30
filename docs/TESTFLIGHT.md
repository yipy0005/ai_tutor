# TestFlight release checklist

The iOS target is a native SwiftUI shell around the existing responsive Flask learner UI. It is suitable for a controlled beta only after the backend is reachable over HTTPS. It is not an offline-native client: the app needs the tutor server to start quests, submit answers, record progress, and finish quests.

## 1. Backend readiness

- [ ] Deploy the Flask app behind a production WSGI server and HTTPS reverse proxy.
- [ ] Use a stable public hostname. TestFlight users and Apple reviewers cannot reach a developer Mac at `127.0.0.1` or a private home IP.
- [ ] Set a strong, persistent `SECRET_KEY` in the deployment environment.
- [ ] For an unconfigured remote deployment, set `PARENT_SETUP_REQUIRE_TOKEN=1` and provide `PARENT_BOOTSTRAP_TOKEN` through the deployment secret manager before exposing the setup route. Direct loopback setup is tokenless only for the initial local operator setup.
- [ ] Set `SESSION_COOKIE_SECURE=1` in the deployment environment after HTTPS is working. Keep `SESSION_COOKIE_HTTPONLY=1` and SameSite protection enabled.
- [ ] Use a production database and a tested backup/restore process before accepting family data. The default SQLite file is appropriate for one household, not a multi-family hosted service.
- [ ] Confirm the deployment does not expose debug mode, the parent PIN default, database files, backups, or instance secrets.
- [ ] Test `/`, `/parent/setup`, `/welcome`, `/pick`, `/home`, `/play/<quest_id>`, `/api/quest/start`, `/api/quest/<id>/answer`, `/api/quest/<id>/finish`, and `/parent/login` from a real iPhone on cellular data.
- [ ] Test a failed network request, a resumed quest, a wrong answer, a second chance, an interactive diagram, read-aloud, and the typed fallback for audio questions.

The existing server uses signed cookie sessions and a session CSRF token. The WebView preserves the default website data store so cookies and the same-origin CSRF flow survive normal app restarts. Do not add a cross-origin proxy or disable CSRF to make the shell work.

## 2. Xcode configuration

- [ ] Open `ios/LearningQuest.xcodeproj` in Xcode.
- [ ] Set `PRODUCT_BUNDLE_IDENTIFIER` to an identifier owned by the Apple Developer team.
- [ ] Set `DEVELOPMENT_TEAM` in both target configurations.
- [ ] Set `BackendBaseURL` in `ios/LearningQuest/Info.plist` to the exact HTTPS origin. Do not include credentials, query parameters, or fragments.
- [ ] Increment `CURRENT_PROJECT_VERSION` for every archive. Update `MARKETING_VERSION` for user-visible releases.
- [ ] Confirm the app icon is present in `Assets.xcassets` and replace the starter artwork if the final brand asset differs.
- [ ] Review the microphone and local-network permission descriptions in `Info.plist`.
- [ ] Run the Debug simulator build, then run on a physical iPhone. Simulator testing cannot prove local-network discovery, microphone permission, or TestFlight cookie persistence.

Release builds reject HTTP server URLs. HTTP is accepted only in Debug for local development and is not an acceptable TestFlight backend.

## 3. Child-safety and privacy review

Learning Quest is designed for children and may store learner names, progress, parent-entered notes, free-text answers, handwriting, and optional audio responses. Before inviting external testers:

- [ ] Publish a plain-language privacy notice that states where data is stored, who can access it, how long it is kept, and how a parent can delete it.
- [ ] Decide whether the beta is one household per server or a hosted multi-family service. Do not mix the two models in tester instructions.
- [ ] Do not add advertising, tracking, analytics SDKs, social login, or unnecessary third-party services to the shell.
- [ ] Explain that the parent PIN is a household gate, not strong account authentication.
- [ ] Confirm audio is opt-in, bounded, reviewable, and deletable. Keep typed fallback available.
- [ ] Complete App Store Connect privacy nutrition labels, age rating, export-compliance questions, and TestFlight review notes accurately.
- [ ] Give reviewers a working HTTPS test account or a deterministic setup path that does not depend on a private home server.

## 4. TestFlight distribution

1. Upload a signed archive from Xcode Organizer.
2. Add the build to an internal tester group first.
3. Test installation, first launch, URL configuration, session persistence, deep links, microphone permission, rotation, and network loss.
4. For external testers, provide the server URL and a short parent setup guide. Never put a secret, PIN, or private database in the app bundle or tester notes.
5. Keep a rollback build and a database backup before changing server schema or question payloads.

## 5. Known beta limitations

- The shell does not create a server or include the Flask database.
- There is no true offline quest queue. A reload preserves answers already committed by Flask; unsent text, drawings, or recordings can be lost if the connection drops.
- The parent dashboard is available through the existing web routes, but the iOS shell is optimized for the learner surface.
- A bare WebView can face App Store minimum-functionality scrutiny. Treat this as a controlled beta and add native value, account/deployment hardening, or a proper native client if App Store distribution becomes a long-term requirement.
