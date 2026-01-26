# V2.0 Plan — Interview Practice Coach (Streamlit + PydanticAI + MySQL + Auth + Analytics)

This plan **replaces V1** and implements your new V2 requirements.

---

## 1) Product goals for V2

### What changes from V1
- Polished UI (not full width, no JSON, clearer interaction)
- Real **user authentication** (Streamlit native auth)
- Mandatory **JD upload** (like CV) - remove the text box for pasting the JD.
- Persist everything in **MySQL** (users, vacancies, questions, answers, suggestions)
- Analytics dashboard + ranking vs other users
- PDF export of analytics
- Dockerized system ready for Cloud Run deployment (The agent doesnt need to deploy)

---

## 2) Architecture overview

### 2.1 High-level components
1. **Streamlit App (single service)**
   - UI + orchestration + agent calls
   - Authentication handling (OIDC via Streamlit)
   - Writes data to MySQL

2. **MySQL Database**
   - Stores users, vacancies (JDs), questions, answers, suggestions, aggregated stats

3. **PydanticAI Agents**
   - Profile extraction (CV + JD)
   - Interview question generation (ensures top-10 skill coverage)
   - Answer evaluation (human-readable outputs only shown in UI)
   - Fallacy/logic hint detection (“Fallacy Detected” ribbon)

4. **Analytics + PDF export**
   - Analytics computed from DB
   - Charts rendered using D3 in Streamlit (via `components.html()` or a custom component)
   - PDF built server-side and offered via `st.download_button`

---

## 3) Authentication (Streamlit native)

### 3.1 Approach
- Use Streamlit’s native OIDC authentication (`st.login()`, `st.user`, `st.logout()`).
- After login, show user identity at top: **“Welcome, <name>”**.
- If `st.user` doesn’t provide clean first/last name:
  - show a one-time form to collect: `first_name`, `last_name`, `email` (pre-fill from `st.user` when possible).
- Save/match the user in DB:
  - if user exists (email match), reuse the same user record
  - else insert a new user row

> Note: Streamlit auth handles authentication (who you are). Authorization rules remain app-managed.

---

## 4) Frontend (UI/UX) requirements and implementation

### 4.1 Layout and styling
- Center the content at **~80% width** (max width + centered container).
- Implement via CSS injection (e.g., set `.block-container` width and margin).
- Add:
  - logo placeholder at top-left
  - favicon placeholder using `st.set_page_config(page_icon=...)`

### 4.2 No JSON on UI
- All agent outputs remain structured internally, but UI renders only:
  - Suggested rewrite
  - Role relevance (%)
  - Correctness (%)
  - Improvements (bullets)
  - Red flags (bullets)
  - Fallacies, coach hints, alerts (human text)
  - Optional follow-up question (toggle/button)

### 4.3 Mandatory JD upload
- JD uploaded similarly to CV:
  - allowed formats: PDF/DOCX/TXT
- JD upload is **mandatory** to start interview.
- Also collect:
  - `position_title` (text input)
- On upload:
  - parse automatically
  - store as a **Vacancy** record
  - link vacancy to user

### 4.4 Auto-parse CV (no button)
- CV parse runs automatically after upload (once per file hash).
- Save parsed CV + extracted profile in DB.

### 4.5 Interview flow changes
- **Submit Answer** can be clicked only once per question:
  - after click, disable the button
  - persist answer + feedback + suggestion
- **Next Question** button exists independently:
  - user may skip (empty answer)
  - skipping still stores a record (`answer_text=NULL`, `is_skipped=true`)
- Follow-up question:
  - show as optional via “Show follow-up” button/expander

### 4.6 Fallacy ribbon behavior
- If a fallacy is detected:
  - show an **orange ribbon/banner**:
    - `Fallacy Detected — <Fallacy Name>`
  - include a **Read more** expander:
    - definition of the fallacy
    - why the answer likely fits the pattern
    - why it can be a red flag in interviews
    - disclaimer: **probabilistic coaching, not truth**

### 4.7 Reset interview behavior
- “Reset Interview” clears:
  - current interview session (questions/answers/feedback visible)
- It **keeps**:
  - CV & JD shown in UI
  - CV/JD stored in DB
- Implementation:
  - clear Streamlit `session_state` interview keys
  - optionally mark the existing interview attempt as reset/archived in DB and start a new attempt

---

## 5) Database design (MySQL)

### 5.1 Tables (minimum)

#### `users`
- `user_id` (PK, auto-increment)
- `email` (unique)
- `first_name`
- `last_name`
- `created_at`, `last_login_at`
- `profile_json` (stored internally, not shown on UI)
- `top_skills_json` (top-10 skills)
- `cv_file_hash`, `cv_text`

#### `vacancies`
- `vacancy_id` (PK)
- `position_title`
- `jd_file_hash`
- `jd_text`
- `created_at`

#### `user_vacancies`
- `user_vacancy_id` (PK)
- `user_id` (FK)
- `vacancy_id` (FK)
- `created_at`

#### `questions`
- `question_id` (PK)
- `user_vacancy_id` (FK)
- `question_text`
- `category`
- `difficulty`
- `skill_tag` (single) OR `skill_tags_json` (list)
- `question_order` (int)
- `created_at`

#### `answers`
- `answer_id` (PK)
- `question_id` (FK)
- `answer_text` (nullable)
- `is_skipped` (bool)
- `created_at`

#### `suggestions`
- `suggestion_id` (PK)
- `question_id` (FK)
- `correctness` (0–100 int)
- `role_relevance` (0–100 int)
- `red_flags_count` (int)
- `red_flags_text` (text)
- `improvements_text` (text)
- `suggested_rewrite` (text)
- `followup_question` (text nullable)
- `fallacy_detected` (bool)
- `fallacy_name` (nullable)
- `fallacy_explanation` (nullable)
- `coach_hint` (nullable)
- `created_at`

#### Optional: `events` / `audit_logs`
- DB-level event logs to complement file logging

### 5.2 Queryability guarantee
At any time, you can query:
- which user (candidate)
- which vacancy/JD
- which questions were asked
- what the user answered (or skipped)
- what suggestions/flags were produced

---

## 6) Skill coverage requirement (top 10 skills)

### 6.1 Rule
- Questions must cover the **top 10 skills** extracted from the profile.

### 6.2 Implementation approach
1. Profile agent produces `top_skills: [skill1..skill10]`.
2. Store `top_skills` in `users.top_skills_json`.
3. Question generator receives:
   - `top_skills`
   - already-covered skills for the current `user_vacancy`
4. Selection algorithm:
   - pick the **least-covered** skill next
   - ensure all 10 are covered before repeating
5. Persist coverage:
   - each question stores `skill_tag(s)`
   - analytics can confirm distribution

---

## 7) Analytics (button + D3 charts + PDF export)

### 7.1 Analytics button
- Only visible if user has attempted at least one question.

### 7.2 Metrics required
1. **How many questions answered so far**
   - count questions where `answer_text` exists OR `is_skipped=true`
2. **% total correctness**
   - average correctness across suggestions
3. **% role relevance**
   - average role relevance across suggestions
4. **Average red flags per question**
   - `sum(red_flags_count) / questions_attempted`
5. **User ranking vs others (correctness)**
   - percentile + absolute rank based on avg correctness across all users

### 7.3 Charts (D3.js in Streamlit)
- Embed D3 using `streamlit.components.v1.html()` or a small custom component.
- Suggested charts:
  - Line chart: correctness over time (by question order)
  - Bar chart: correctness vs relevance averages
  - Distribution chart: user percentile vs population

### 7.4 Download analytics as PDF
- Build PDF server-side:
  - header (user name/email, date)
  - summary metrics
  - charts (either export D3 to image OR redraw charts with matplotlib for PDF)
- Provide `st.download_button`.
- Save PDFs in `./reports/` and log path.

---

## 8) Logging (full logs stored on disk)

### 8.1 Requirements
Log to:
1. stdout (best for Cloud Run)
2. disk (`./logs/app.log`) using rotation

Include:
- request/session id
- `user_id`, `vacancy_id` (when available)
- event name (e.g., `AUTH_LOGIN`, `CV_PARSED`, `QUESTION_GENERATED`, `ANSWER_SAVED`, `ANALYTICS_RENDERED`)
- agent durations
- DB query timings
- error stack traces

### 8.2 Folders
- `./logs/` for logs
- `./reports/` for PDFs (optional retention policy)

> Cloud Run note: container disk is ephemeral; still implement file logs as requested, but rely on stdout logs for durability.

---

## 9) Dockerization (MySQL + app in containers)

### 9.1 Local development (recommended)
- Use `docker-compose` with:
  - `app` (Streamlit)
  - `mysql` (MySQL server)
- Persist MySQL data in a Docker volume.

### 9.2 “All-in-one container” note
You asked to include MySQL in the container. This is not ideal for Cloud Run scaling, but if you insist:
- run MySQL + Streamlit with a supervisor (e.g., `supervisord`)
- durable storage is tricky on Cloud Run

**Recommended real-world alternative:** Cloud SQL (managed MySQL) + app container only.

---

## 10) Git workflow rules for V2
- Work on **a single branch only**
- Commit after each step completion
- Clear incremental commit messages
- Keep tests green at every commit

---

## 11) V2 implementation steps (with commits)

### Step 1 — UI refactor + auth scaffolding
**Deliverables**
- Center layout (~80% width)
- Logo + favicon placeholder
- Streamlit native auth flow + show user name/email at top
- Capture missing first/last/email once; upsert into `users`
- No JSON rendered

**Commit**
- `V2 Step 1: UI layout + Streamlit auth + user identity header`

### Step 2 — JD mandatory + auto-parse CV/JD + DB persistence
**Deliverables**
- JD upload required to proceed
- CV upload auto-parse once per hash (no parse buttons)
- Persist:
  - CV/profile into `users`
  - JD/title into `vacancies`
  - link via `user_vacancies`
- Reset interview clears Q/A/feedback but keeps CV/JD

**Commit**
- `V2 Step 2: Mandatory JD upload + auto-parse CV/JD + persist user/vacancy`

### Step 3 — Interview flow improvements + DB storage
**Deliverables**
- Submit answer once → disable after click
- Next question button supports skipping (empty answer stored as skipped)
- Optional follow-up reveal
- Persist `questions`, `answers`, `suggestions`

**Commit**
- `V2 Step 3: Improved interview flow + DB storage for Q/A/suggestions`

### Step 4 — Fallacy ribbon + “Read more” explanations
**Deliverables**
- Orange ribbon: `Fallacy Detected — <name>`
- “Read more” expander contains explanation + red-flag rationale + disclaimer
- Persist fallacy fields in `suggestions`

**Commit**
- `V2 Step 4: Fallacy ribbon + read-more explanations + persistence`

### Step 5 — Skill coverage enforcement (top 10)
**Deliverables**
- Store `top_skills` in `users`
- Question generator enforces top-10 coverage (least-covered next)
- Persist skill tags per question

**Commit**
- `V2 Step 5: Top-10 skill coverage enforcement in question generation`

### Step 6 — Analytics dashboard + D3 charts
**Deliverables**
- Analytics button with required metrics
- D3 charts embedded in Streamlit

**Commit**
- `V2 Step 6: Analytics dashboard + D3 visualizations`

### Step 7 — PDF export of analytics
**Deliverables**
- Generate PDF report
- Download button
- Save to `./reports/` + log path

**Commit**
- `V2 Step 7: Analytics PDF export + report storage`

### Step 8 — Dockerization for local + Cloud Run readiness
**Deliverables**
- Dockerfile(s) + docker-compose
- Document in README:
  - local compose run
  - Cloud Run ready image (app-only; DB configured via env)

**Commit**
- `V2 Step 8: Docker + compose for MySQL + Cloud Run-ready packaging`

---

## 12) Testing strategy for V2
Add tests for:
- DB models + migrations / schema initialization
- user creation/matching on login
- JD mandatory gating logic
- question skill coverage algorithm
- answer-submit-once behavior (session state)
- analytics metric calculations

Mock agent outputs to keep tests deterministic.

---

## 13) Key implementation notes
- Keep structured outputs internally; UI shows only human-readable fields.
- Treat CV/JD as untrusted data; keep injection hardening.
- Prefer clean service layer modules:
  - `db.py` (CRUD)
  - `analytics.py` (queries + metrics)
  - `pdf_report.py` (PDF build)
  - `charts.py` (D3 embed scaffolding)
