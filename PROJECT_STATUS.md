# WC 2026 Predictor — Stare proiect
**Data raportului:** 17 iunie 2026  
**Scopul documentului:** rezumat tehnic pentru consultare externă (model advisor).

---

## 1. Stadiu general

### Faze completate
| Fază | Descriere | Status |
|------|-----------|--------|
| Faza 1 | Backend FastAPI + modele Dixon-Coles + Elo | ✅ Complet |
| Faza 2 | API complet (meciuri, predicții, rezultate, admin) | ✅ Complet |
| Faza 2+ | XGBoost (al 3-lea model) + Triple Ensemble | ✅ Complet |
| Faza 3–8 | Frontend React + Vite + Tailwind (UI complet) | ✅ Complet |
| Sub-faza A | Integrare date xG din StatsBomb Open Data | ✅ Complet (fișier parquet generat) |
| Sub-faza B | Semnal hibrid xG+goals în Dixon-Coles | ⏳ Urmează |
| Sub-faza C | Formă recentă + ajustaj confederație | ⏳ Urmează |
| Sub-faza D | Calibrare (isotonic regression + ECE) | ⏳ Urmează |

### Stivă tehnică
- **Backend:** Python 3.14, FastAPI, Uvicorn, Pydantic v2, Pandas, NumPy, SciPy, XGBoost 2.x, statsbombpy
- **Frontend:** React 18, Vite, Tailwind CSS, React Query v5, React Router v6
- **Date:** martj42/international_results (GitHub CSV), StatsBomb Open Data (Python SDK), openfootball (calendar WC 2026)

---

## 2. Date

### Surse integrate
| Sursă | Conținut | Status |
|-------|----------|--------|
| martj42/international_results | Rezultate istorice internaționale (din 1872) | ✅ Activ — descărcat automat la antrenare |
| openfootball WC 2026 | Calendar complet: 12 grupe × 48 meciuri + knockout | ✅ Integrat în fixtures.py |
| StatsBomb Open Data | Date xG reale (shot_statsbomb_xg) din 5 turnee majore | ✅ Descărcat (250 meciuri, parquet cacheuit) |
| FBref | — | ❌ Neimplementat (ales StatsBomb în locul lui) |

### Fereastra de antrenare și parametri
| Parametru | Valoare |
|-----------|---------|
| Fereastra de antrenare | **6 ani** (TRAINING_YEARS = 6, tăiat de la data curentă) |
| Total meciuri în fereastra curentă | **~6.039** meciuri |
| Time decay rate | **0.00275** pe zi (half-life ≈ 8,7 luni) |
| Shrinkage Base / Bonus / Min | 1.2 / 20.0 / 5.0 |
| Max goluri simulare DC | 10 |

### Ponderile competițiilor
| Competiție | Pondre |
|------------|--------|
| FIFA World Cup | 5.0 |
| WC Qualification | 4.0 |
| UEFA Euro / Copa América | 4.0 |
| AFCON / AFC Asian Cup | 3.5 |
| UEFA Nations League / Qualification | 2.5–3.0 |
| Friendly | 0.4 |
| Altele (default) | 1.5 |

### Acoperire xG (Sub-faza A — implementat)
| Metric | Valoare |
|--------|---------|
| Meciuri descărcate StatsBomb | 250 (5 competiții) |
| Meciuri matched în training set | **207 / 6.039** |
| Acoperire brută | **3.4%** |
| Acoperire ponderată (după weight coloane) | **2.0%** |
| Interval temporal xG | 2021-06-12 → 2024-07-14 |
| Competiții acoperite | WC 2022 (64), AFCON 2023 (52), Euro 2020 (51), Euro 2024 (51), Copa 2024 (32) |

> **Notă:** Acoperirea globală (3.4%) e mică deoarece StatsBomb Open Data conține exclusiv turnee majore,
> nu întreg setul de 6.039 meciuri istorice. Calitativ, cele 207 meciuri sunt exact din
> competițiile cu weight 3.5–5.0, deci impactul per meci este ridicat.

### Echipe WC 2026 fără date istorice (unmatched)
Conform codului (`_log_unmatched`), dacă există echipe în lista WC 2026 fără reprezentare
în training set, sunt loggate ca warning. **Status la momentul ultimei antrenări: toate 48 de echipe
au date istorice** (log: "All 48 WC 2026 teams have training data ✓").

Echipele cu date puține / izolate (low weighted_matches) includ probabil:
Curaçao, Haiti, Cabo Verde, Bosnia and Herzegovina, Uzbekistan — dar nu sunt unmatched, doar rar reprezentate.

---

## 3. Model

### Componente active
| Componentă | Status | Detalii |
|------------|--------|---------|
| Dixon-Coles (bivariate Poisson) | ✅ ON | Cu shrinkage regularizare + τ correcție pentru scoruri mici |
| Elo rating | ✅ ON | K=32 (K=40 pentru update-uri live WC 2026), HFA=100 puncte |
| XGBoost (multi:softprob) | ✅ ON | 26 features, 600 estimatori, max_depth=4 |
| Triple Ensemble blend | ✅ ON | DC 30% + Elo 20% + XGB 50% pentru H/D/A |
| Goal markets (xG, BTTS, O/U, scoreline) | ✅ ON | 100% Dixon-Coles (singurul care produce distribuție de scor) |
| Home advantage (HFA) | ✅ ON | Optimizat de DC (exp(log_hfa)); neutru flag pentru WC |
| WC 2026 live result injection | ✅ ON | Rezultate reale → retrain cu weight 2× față de WC normal |
| Formă recentă (în XGB features) | ✅ ON | Last-5 per echipă: wrate, drate, gf, ga, gd |
| H2H (în XGB features) | ✅ ON | Last-10 per pereche |
| xG real StatsBomb (în antrenament DC) | ❌ OFF | Sub-faza B neimplementată |
| Ajustaj confederație | ❌ OFF | Sub-faza C neimplementată |
| Calibrare (isotonic / Platt) | ❌ OFF | Sub-faza D neimplementată |

### Parametri configurabili și valorile curente
| Parametru | Valoare curentă | Unde se setează |
|-----------|-----------------|-----------------|
| `ensemble_alpha` | 0.65 (ignorat când XGB e activ) | config.py / .env |
| W_DC / W_ELO / W_XGB | **0.30 / 0.20 / 0.50** | app/model/ensemble.py |
| `training_years` | 6 | tournament_config.py |
| `time_decay_rate` | 0.00275 | tournament_config.py |
| `n_simulations` | 10.000 | config.py |
| Elo K (antrenament) | 32 | elo.py |
| Elo K (WC live updates) | 40 | model_service.py |
| Elo HFA | 100 puncte | elo.py |
| Elo initial rating | 1500 | elo.py |
| XGB n_estimators | 600 | xgboost_model.py |
| XGB max_depth | 4 | xgboost_model.py |
| XGB learning_rate | 0.05 | xgboost_model.py |
| XGB subsample / colsample | 0.80 / 0.75 | xgboost_model.py |
| XGB reg_alpha / reg_lambda | 0.15 / 1.5 | xgboost_model.py |
| XGB min_child_weight | 10 | xgboost_model.py |
| Value bet threshold (1/2) | ≥56% | ensemble.py |
| Value bet threshold (BTTS/O2.5) | ≥55% | ensemble.py |
| Value bet threshold (U2.5) | ≥62% | ensemble.py |

### Features XGBoost (26 total)
```
Elo (3):   elo_h, elo_a, elo_diff
DC  (7):   dc_att_h, dc_def_h, dc_att_a, dc_def_a, dc_xg_h, dc_xg_a, dc_xg_diff
Form home (5): fh_wrate, fh_drate, fh_gf, fh_ga, fh_gd
Form away (5): fa_wrate, fa_drate, fa_gf, fa_ga, fa_gd
H2H  (5):  h2h_h_wrate, h2h_draw_rate, h2h_h_gf, h2h_h_ga, h2h_n
Ctx  (1):  is_neutral
```
> Notă: `dc_xg_h/a` sunt xG **prezise de DC** (lambdas), nu xG real din StatsBomb.
> xG real din StatsBomb va fi integrat în Sub-faza B (semnal hibrid pentru DC) și
> potențial ca feature direct în XGB în Sub-faza C.

---

## 4. Performanță / metrici

### Backtest formal
**Neimplementat** — scriptul `backend/scripts/backtest.py` a fost creat în sesiunea curentă
dar nu a fost rulat încă. Motivul: backtestul necesită re-antrenare DC+Elo pe subset anterior
lui 2024-01-01, ceea ce durează câteva minute.

| Versiune | Accuracy | Log-loss | Brier | ECE |
|----------|----------|----------|-------|-----|
| Baseline (DC+Elo) | neimplementat | neimplementat | neimplementat | neimplementat |
| Triple Ensemble (DC+Elo+XGB) | neimplementat | neimplementat | neimplementat | neimplementat |
| Sub-faza B (cu xG în DC) | neimplementat | neimplementat | neimplementat | neimplementat |

> **Prioritate înaltă:** rularea backtestului pe baseline înainte de Sub-faza B este
> obligatorie (Regula de Aur: orice adăugare trebuie să reducă log-loss/Brier față de baseline).

### Tracking live pe meciurile WC 2026
| Metric | Valoare |
|--------|---------|
| Meciuri jucate înregistrate | Depinde de datele introduse în admin (sistem existent) |
| Correct picks / accuracy | **Neimplementat ca raport automat** |
| Log-loss / Brier cumulat live | **Neimplementat** |

> Sistemul de admin (`/admin`) permite introducerea rezultatelor reale, dar nu există
> încă un raport automat de acuratete live calculat din predicțiile logate.

---

## 5. Probleme cunoscute / nelămuriri

### Probleme tehnice
| Problemă | Severitate | Status |
|----------|-----------|--------|
| `UnicodeEncodeError` în logger pentru `→` (cp1252 pe Windows) | Scăzută | Cosmetic — datele s-au salvat corect; de corectat encoding în logging |
| `app/models/ensemble.py` vs `app/model/ensemble.py` — două fișiere ensemble | Medie | Cel activ este `app/model/ensemble.py` (triple); cel vechi `app/models/ensemble.py` e bifuncțional dar nefolosit — de șters pentru claritate |
| Backtest nerunat | Ridicată | Fără baseline numeric nu se poate valida că sub-fazele B/C/D îmbunătățesc ceva |

### Nelămuriri de model / decizii pendinte

1. **Ponderi ensemble (30/20/50):** Alese intuitiv. Fără backtest nu știm dacă 50% XGB e optim
   sau dacă un blend mai conservator (ex. 40/25/35) ar da log-loss mai mic.

2. **Acoperire xG 3.4% — merită Sub-faza B?**
   Doar 207 din 6.039 meciuri au xG real. Semnalul hibrid (70% xG + 30% goals) va afecta
   maxim ~207 rânduri din antrenament. Ipoteza: cele 207 meciuri sunt turnee de top cu
   weight 3.5–5.0, deci impactul per meci e ridicat, dar riscul de overfit pe un subset mic există.
   De validat numeric cu backtest înainte și după.

3. **Formă recentă în DC vs. doar în XGB:**
   Momentan forma last-5 este feature pentru XGB. DC nu folosește forma — antrenează pe toată
   fereastra de 6 ani cu time decay. Dacă adăugăm formă și în DC (Sub-faza C), există risc de
   redundanță cu XGB features.

4. **Echipe slab reprezentate (Curaçao, Haiti, Uzbekistan, Cabo Verde):**
   Primesc parametri DC mediocri (media populației). Predicțiile pentru meciurile lor sunt
   practic bazate pe Elo + fallback DC mediu. Fără date istorice suplimentare, aceasta e
   limita fundamentală a abordării.

5. **Calibrare (Sub-faza D):**
   Nu știm dacă modelul este over/underconfident fără reliability diagram. ECE neimplementat.
   Isotonic regression e planificată dar riscă overfit pe un calibration set mic (turneele finale).

---

## Fișiere cheie

```
backend/
├── app/
│   ├── config.py                    # Settings: training_years, decay, alpha
│   ├── main.py                      # FastAPI lifespan, version: 0.3.0-triple
│   ├── model/ensemble.py            # Triple ensemble ACTIV (DC+Elo+XGB)
│   ├── models/
│   │   ├── dixon_coles.py           # DC bivariate Poisson + shrinkage
│   │   ├── elo.py                   # Elo secvential + HFA
│   │   └── xgboost_model.py         # XGB 26 features
│   ├── data/
│   │   ├── historical.py            # Download + preprocess martj42
│   │   ├── tournament_config.py     # Grupe WC 2026, weights, params
│   │   └── xg_fetcher.py            # StatsBomb xG fetcher (Sub-faza A)
│   └── services/model_service.py    # load_or_train (DC+Elo+XGB)
├── scripts/
│   └── backtest.py                  # Script backtest (creat, nerunat încă)
└── .cache/
    ├── results.csv                  # Date istorice (auto-descărcate)
    ├── dc_model.pkl / elo_model.pkl / xgb_model.pkl
    └── xg/
        ├── xg_all.parquet           # 250 meciuri xG (StatsBomb)
        └── xg_comp*.parquet         # Cache per competiție
```
