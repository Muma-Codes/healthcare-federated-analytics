# 🏥 Healthcare Federated Analytics

A full-stack, privacy-preserving clinical decision-support platform that combines **Federated Learning** with a secure multi-role web interface to deliver real-time chronic disease risk predictions for **diabetes** and **heart disease** — without centralising raw patient data.

---

## ✨ Features

- 🤖 **Federated Learning (FedAvg)** — models trained across distributed hospital nodes; raw patient data never leaves the local client
- 🩺 **Chronic Disease Prediction** — diabetes (8 features) and heart disease (13 features) risk assessments with confidence scores
- 🔐 **JWT Authentication** with server-side session revocation
- 🛡️ **Role-Based Access Control** — admin, doctor, nurse, and pending roles
- 🔒 **Account Lockout** after 5 consecutive failed login attempts with email alert
- 📱 **TOTP Multi-Factor Authentication** (Google Authenticator / Authy compatible)
- 🔑 **AES-256-GCM** column-level encryption for sensitive fields
- 📋 **Immutable Audit Trail** — every significant action is logged
- 🎓 **Annual Security Awareness Training** with a built-in quiz
- 📊 **Admin Dashboard** — user stats, prediction counts, security metrics, and charts
- 📧 **Email Alerts** for lockouts, suspicious access, and breach events
- ✅ **Full Test Suite** — unit and integration tests with pytest

---

## 🏗️ Architecture
```
healthcare-federated-analytics/
│
├── server/                        # FastAPI backend
│   ├── main.py                    # App factory, routers, lifespan
│   ├── config.py                  # Pydantic settings from .env
│   ├── auth/
│   │   ├── routes.py              # Auth endpoints
│   │   ├── utils.py               # Hashing, JWT, TOTP, AES
│   │   └── dependencies.py        # get_current_user, require_role
│   ├── federated/
│   │   ├── routes.py              # FL + prediction endpoints
│   │   └── server.py              # FedAvg simulation engine
│   ├── ml/
│   │   ├── preprocess.py          # Data loading, scaling, splitting
│   │   └── predict.py             # Inference + risk classification
│   ├── database/
│   │   ├── base.py                # Async engine + session factory
│   │   └── seed.py                # Default account seeding
│   ├── models/                    # ORM models (User, AuditLog, etc.)
│   ├── middleware/
│   │   └── audit_routes.py        # Request audit middleware
│   ├── notifications/
│   │   └── email.py               # SMTP security alert emails
│   ├── data/
│   │   ├── diabetes.csv           # Pima Indian Diabetes (768 rows)
│   │   └── heart.csv              # Cleveland Heart Disease (1025 rows)
│   └── tests/
│       └── test_backend.py        # Full pytest suite
│
└── streamlit_app/                 # Streamlit multi-page frontend
    ├── app.py                     # Entry point: login / sign-up
    ├── auth_ui.py                 # Session management + auth helpers
    ├── auth_utils_bridge.py       # Bridges server auth utils to UI
    ├── db.py                      # Sync SQLite helpers
    ├── utils.py                   # Sidebar renderer + sys.path setup
    ├── requirements.txt           # Frontend dependencies
    ├── .streamlit/
    │   └── config.toml            # Theme configuration
    └── pages/
        ├── 1_Dashboard.py         # Stats, charts, audit feed
        ├── 2_Predict.py           # Disease prediction forms
        ├── 3_Profile.py           # Account details + password change
        ├── 4_Users.py             # Admin user management
        ├── 5_Audit_Log.py         # Paginated audit trail
        ├── 6_Security_Training.py # Training module + quiz
        └── 7_FL_Training.py       # FL control panel
```

---

## 👥 Roles & Permissions

| Role | Dashboard | Predict | Profile | Users | Audit Log | FL Training | Security Training |
|------|-----------|---------|---------|-------|-----------|-------------|-------------------|
| **admin** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **doctor** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| **nurse** | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ |
| **pending** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

> **pending** accounts cannot log in until an admin assigns a role via the Users page.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- pip

### 1. Clone the repository
```bash
git clone https://github.com/your-username/healthcare-federated-analytics.git
cd healthcare-federated-analytics
```

### 2. Set up the backend
```bash
cd server
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example env file and fill in your values:
```bash
cp .env.example .env
```

Open `.env` and set at minimum:
```env
SECRET_KEY=your-strong-random-secret-key-32chars
ENCRYPTION_KEY=your-encryption-key
DATABASE_URL=sqlite+aiosqlite:///./healthcare.db
```

See the [Environment Variables](#environment-variables) section for the full list.

### 4. Start the FastAPI backend
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

On first startup the database tables are created automatically and the three default accounts are seeded. The API will be available at `http://localhost:8000` and interactive docs at `http://localhost:8000/docs`.

### 5. Set up and start the Streamlit frontend

Open a new terminal:
```bash
cd streamlit_app
pip install -r requirements.txt
streamlit run app.py
```

The app will be available at `http://localhost:8501`.

### 6. Train the federated models

1. Log in as **admin**
2. Navigate to **FL Training** in the sidebar
3. Click **Start Training**
4. Once complete, the **Predict** page becomes available for admins and doctors

---

## 🔑 Default Credentials

> ⚠️ **Change these immediately after first login.**

| Username | Password | Role |
|----------|----------|------|
| `admin` | `Admin@12345!` | admin |
| `dr_joseph` | `Doctor@12345!` | doctor |
| `nurse_patrick` | `Nurse@12345!` | nurse |

---

## 🌐 API Endpoints

### Authentication `/auth`
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | None | Self-registration (role = pending) |
| POST | `/auth/login` | None | Returns JWT or MFA challenge |
| POST | `/auth/verify-mfa` | temp_token | Complete MFA step |
| POST | `/auth/logout` | Bearer | Server-side session invalidation |
| POST | `/auth/change-password` | Bearer | Change own password |
| GET | `/auth/setup-mfa` | Bearer | Generate TOTP QR code |
| POST | `/auth/confirm-mfa` | Bearer | Activate MFA |
| GET | `/auth/me` | Bearer | Current user profile |

### Federated Learning `/federated`
| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| POST | `/federated/train` | admin | Start FL training |
| GET | `/federated/status` | any | Poll training progress |
| GET | `/federated/metrics` | any | Per-round metrics |
| GET | `/federated/dataset-info` | any | Dataset metadata |
| POST | `/federated/predict/diabetes` | admin, doctor | Diabetes prediction |
| POST | `/federated/predict/heart` | admin, doctor | Heart disease prediction |
| GET | `/federated/predictions` | any | Prediction history |

### Admin `/admin`
| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| GET | `/admin/users` | admin | List all users |
| GET | `/admin/users/pending` | admin | List pending accounts |
| PUT | `/admin/users/{id}/role` | admin | Assign role + approve |
| PUT | `/admin/users/{id}/unlock` | admin | Unlock account |
| DELETE | `/admin/users/{id}` | admin | Deactivate account |
| GET | `/admin/audit-logs` | admin | Paginated audit trail |
| GET | `/admin/dashboard-stats` | any | Aggregated stats |

### Security Training `/training`
| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| POST | `/training/complete` | any | Submit quiz result |
| GET | `/training/status` | any | Check training compliance |

---

## ⚙️ Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing secret | **required** |
| `ENCRYPTION_KEY` | AES-256 column encryption key | **required** |
| `DATABASE_URL` | SQLAlchemy async DSN | `sqlite+aiosqlite:///./healthcare.db` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT lifetime in minutes | `60` |
| `PASSWORD_MIN_LENGTH` | Minimum password length | `8` |
| `PASSWORD_EXPIRY_DAYS` | Days until password expires | `90` |
| `MAX_LOGIN_ATTEMPTS` | Failed attempts before lockout | `5` |
| `ACCOUNT_LOCKOUT_MINUTES` | Lockout duration in minutes | `30` |
| `FL_ROUNDS` | Number of federated learning rounds | `5` |
| `SMTP_HOST` | Email server host | `smtp.gmail.com` |
| `SMTP_PORT` | Email server port | `587` |
| `SMTP_USER` | SMTP login email | optional |
| `SMTP_PASSWORD` | SMTP app password | optional |
| `ALERT_EMAIL` | Recipient for security alerts | optional |
| `APP_NAME` | Display name for emails and TOTP | `HealthcareAnalytics` |
| `DEBUG` | Enable SQLAlchemy query logging | `False` |

> Leave `SMTP_USER`, `SMTP_PASSWORD`, and `ALERT_EMAIL` blank to disable email alerts silently.

---

## 🧪 Running Tests
```bash
cd server
pytest tests/ -v
```

The test suite covers 8 areas across 40+ tests:

- **Auth utilities** — hashing, JWT, TOTP, AES encryption, password expiry
- **ML preprocessing** — feature counts, split ratios, data leakage prevention
- **Federated training** — round counts, metric validity, model file persistence
- **Predictions** — output structure, risk levels, invalid input rejection
- **API: Auth** — registration, login, pending block, wrong password
- **API: Federated** — dataset info, RBAC enforcement (nurse forbidden)
- **API: Admin** — user management, role assignment, audit logs, dashboard stats
- **API: Training** — quiz submission, compliance status, unauthenticated rejection

> Tests use a separate `test_healthcare.db` database and set `FL_ROUNDS=2` for speed.

---

## 🔒 Security Design

| Feature | Implementation |
|---------|----------------|
| Password hashing | Argon2 via passlib — memory-hard, GPU-resistant |
| JWT revocation | Sessions table — true server-side logout |
| Account lockout | 5 failed attempts → locked + admin email alert |
| Password policy | Min 8 chars, uppercase, lowercase, digit, special char |
| Password expiry | 90-day enforcement with must_change_password flag |
| MFA | TOTP (RFC 6238) via pyotp — compatible with any authenticator app |
| Column encryption | AES-256-GCM for sensitive stored fields |
| Audit trail | Immutable AuditLog table — cannot be deleted via API |
| Patient privacy | No PII in PredictionLog — anonymised clinical values only |
| Federated privacy | Raw data never leaves hospital node — only weights transmitted |
| Data leakage prevention | StandardScaler fitted on training data only |

---

## 🤖 Federated Learning

The system implements **Federated Averaging (FedAvg)** using the [Flower](https://flower.dev) framework in an in-process simulation (no TCP sockets required):

1. Two simulated hospital clients each hold a local dataset
2. Each client trains a **Logistic Regression** on its local data only
3. The server performs **weighted averaging** of model weights by sample count
4. This repeats for `FL_ROUNDS` rounds
5. Final models and scalers are saved as `.pkl` files

| Client | Dataset | Rows | Features |
|--------|---------|------|----------|
| Hospital A | Pima Indian Diabetes | 768 | 8 |
| Hospital B | Cleveland Heart Disease | 1025 | 13 |

> Raw patient data **never** leaves the local client. Only model weight vectors are exchanged.

---

## 📋 Risk Classification

| Risk Level | Probability Threshold | Action |
|------------|----------------------|--------|
| 🟢 Low Risk | < 35% | Routine monitoring |
| 🟡 Moderate Risk | 35% – 65% | Follow-up testing recommended |
| 🔴 High Risk | > 65% | Urgent clinical evaluation recommended |

> ⚕️ All predictions are **decision-support outputs only** and do not constitute a medical diagnosis. Always consult a qualified healthcare professional.

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- [Pima Indian Diabetes Dataset](https://www.kaggle.com/datasets/uciml/pima-indians-diabetes-database) — UCI Machine Learning Repository
- [Cleveland Heart Disease Dataset](https://www.kaggle.com/datasets/cherngs/heart-disease-cleveland-uci) — UCI Machine Learning Repository
- [Flower Federated Learning Framework](https://flower.dev)
- [FastAPI](https://fastapi.tiangolo.com) — modern async Python API framework
- [Streamlit](https://streamlit.io) — rapid data app framework
