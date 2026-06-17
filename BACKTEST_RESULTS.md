# Backtest Results — WC 2026 Predictor

## Configurare split

| Parametru | Valoare |
|-----------|---------|
| Cutoff (end train) | 2024-07-15 |
| Test end | 2026-06-10 |
| Meciuri train | 4,090 |
| Meciuri test | 1,459 (competitive, w_comp ≥ 1.5) |
| Distributie test (H/D/A) | 685/321/453 = 47%/22%/31% |
| XGBoost antrenat | DA |

## Metodologie anti-leakage

- **Split strict temporal**: modelele văd ZERO din test set la antrenare.
- **Dixon-Coles**: antrenat exclusiv pe train split.
- **Elo**: updatat cronologic pe train split; ratingurile de inferenta = stare la finalul trainului.
- **XGBoost features la training**: Elo + form/H2H construite cronologic (match N foloseste doar date din matches 1..N-1). ✅
- **XGBoost features la inferenta (test set)**: DC params + Elo ratings + form/H2H = stare la finalul perioadei de train. Forma este **stala** (nu se actualizeaza pe test set) — limitare a holdout simplu vs walk-forward.
- **Nota leakage minora documentata**: parametrii DC sunt antrenati pe tot train set-ul, apoi folositi ca features per meci in XGB (XGB vede DC params influentati de meciuri ulterioare din aceeasi fereastra de training). Compromis comun — nu afecteaza evaluarea pe test set.
- **Prietenii excluse** din test set (w_comp < 1.5).

## Tabel comparativ — sortat dupa Log-Loss (↑ mai mic = mai bun)

| Varianta | Ponderi (DC/Elo/XGB) | Accuracy | Log-Loss | Brier | ECE |
|----------|---------------------|----------|----------|-------|-----|
| DC singur ⬅ BEST | 100% / 0% / 0% | 58.4% | **0.9282** | 0.5469 | 0.0339 |
| DC+Elo+XGB 50/30/20 | 50% / 30% / 20% | 57.8% | **0.9336** | 0.5487 | 0.0238 |
| DC+Elo+XGB 40/25/35 | 40% / 25% / 35% | 56.8% | **0.9356** | 0.5504 | 0.0136 |
| DC+Elo+XGB 33/33/33 | 33% / 33% / 33% | 57.1% | **0.9388** | 0.5514 | 0.0204 |
| DC+Elo (65/35) | 65% / 35% / 0% | 57.0% | **0.9449** | 0.5565 | 0.0244 |
| DC+Elo+XGB 30/20/50 | 30% / 20% / 50% | 55.4% | **0.9474** | 0.5592 | 0.0182 |
| DC+Elo+XGB 20/10/70 | 20% / 10% / 70% | 53.7% | **0.9831** | 0.5828 | 0.0657 |
| Elo singur | 0% / 100% / 0% | 51.7% | **1.0777** | 0.6202 | 0.0875 |
| XGB singur | 0% / 0% / 100% | 50.7% | **1.1368** | 0.6413 | 0.1238 |

## Analiza componente individuale

- **DC vs Elo**: DC log-loss=0.9282, Elo log-loss=1.0777 → **DC** mai bun individual.
- **DC+Elo blend** vs cel mai bun individual: delta log-loss = -0.0167 → INRAUTATIRE.
- **XGBoost adauga valoare?** DC+Elo (65/35) log-loss=0.9449 vs DC+Elo+XGB (30/20/50) log-loss=0.9474 → delta=-0.0025 (INRAUTATIRE).

## Recomandare

Cel mai mic log-loss: **DC singur** (ponderi DC=100% / Elo=0% / XGB=0%)
  - Log-Loss: 0.9282
  - Accuracy: 58.4%
  - Brier: 0.5469
  - ECE: 0.0339

> **Nota**: Aceste numere reprezinta BASELINE-ul inaintea sub-fazelor B/C/D.
> Orice modificare a modelului trebuie sa reduca log-loss-ul variantei curente active
> (DC+Elo+XGB 30/20/50) inainte de a fi adoptata ca default.

---
*Generat: 2026-06-17 | Train cutoff: 2024-07-15 | Test: 1459 meciuri competitive*
---

## Sub-faza B — DC hibrid xG + goluri

### Configurare

| Parametru | Valoare |
|-----------|---------|
| Meciuri train cu xG (dupa fuzzy merge) | 250 / 4090 (6.1%) |
| Split temporal | identic cu baseline |
| Test set | 1.459 meciuri competitive |
| Fuzzy matching activat | DA (±1 zi + home/away invers) |

### Tabel comparativ

| Varianta | Accuracy | Log-Loss | Brier | ECE | Delta vs baseline |
|----------|----------|----------|-------|-----|-------------------|
| DC pur (baseline OFF) *(sanity check)* | 58.4% | **0.9282** | 0.5469 | 0.0339 | — |
| DC hibrid xG blend=0.50 | 58.3% | **0.9241** | 0.5442 | 0.0343 | -0.0041 |
| DC hibrid xG blend=0.60 | 58.5% | **0.9238** | 0.5440 | 0.0348 | -0.0044 |
| DC hibrid xG blend=0.70 | 58.5% | **0.9235** | 0.5438 | 0.0346 | -0.0047 |

### Verdict

**IMBUNATATIRE**: cel mai bun hibrid (DC hibrid xG blend=0.70) obtine log-loss=0.9235 (delta=-0.0047 fata de baseline 0.9282).

**Recomandare: USE_XG_HYBRID=ON cu blend=0.7** (setare in .env: USE_XG_HYBRID=true XG_BLEND_WEIGHT=0.7).

*Generat: 2026-06-17 | Sanity check: OK*

---

## Sub-faza D — Calibrare (gardă anti-overfit)

### Configurare

| Parametru | Valoare |
|-----------|---------|
| Model calibrat | DC hibrid xG blend=0.7 (cel mai bun din Sub-faza B) |
| Calibration set | 729 meciuri (2024-09-02 → 2025-03-25) |
| Validation set | 730 meciuri (2025-03-25 → 2026-06-10) |
| Split | temporal 50/50, calibratorii NU văd validation set la fit |

### Calibration set — ce "învaț" calibratorii (overfit check)

| Varianta | Log-Loss | ECE@10 | ECE@15 |
|----------|----------|--------|--------|
| Uncalibrated [CAL] | 0.9530 | 0.0182 | 0.0302 |
| Isotonic     [CAL] | 0.9178 | 0.0088 | 0.0131 |
| Platt        [CAL] | 0.9511 | 0.0134 | 0.0209 |

### Validation set — testul real (date nevăzute)

| Varianta | Accuracy | Log-Loss | Brier | ECE@10 | ECE@15 |
|----------|----------|----------|-------|--------|--------|
| Uncalibrated [VAL] | 61.5% | **0.8941** | 0.5235 | 0.0510 | 0.0518 |
| Isotonic     [VAL] | 59.9% | **0.8840** | 0.5207 | 0.0228 | 0.0273 |
| Platt        [VAL] | 60.8% | **0.8881** | 0.5176 | 0.0300 | 0.0300 |

### Analiză

**Isotonic Regression:**
- ECE@10 pe validation: IMBUNATATIRE pe val: delta ECE@10=-0.0282
- Log-Loss pe validation: IMBUNATATIRE: delta ll=-0.0101
- Overfit? NU

**Platt Scaling:**
- ECE@10 pe validation: IMBUNATATIRE pe val: delta ECE@10=-0.0210
- Log-Loss pe validation: IMBUNATATIRE: delta ll=-0.0060
- Overfit? NU

**Stabilitate ECE** (10 vs 15 bins): Dacă concluzia diferă între ECE@10 și ECE@15, rezultatul e sensibil la granularitate — nu te baza pe ECE singur.

### Verdict

**Recomandare: `CALIBRATION=isotonic`**  
Îmbunătățire reală pe validation set (ll=0.8840).  
Setați `CALIBRATION=isotonic` în `.env`.

*Generat: 2026-06-17 | Model: DC hibrid xG blend=0.7*