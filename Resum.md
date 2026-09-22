# ============================================================================
# SPACELL-DT — MASTER DOCUMENT (.md)
# Physics-Based Digital Twin for Space Solar Cells
# Degradation, Recovery and Lifetime Prediction
# ============================================================================
# Fichier   : SPACELL-DT_MASTER.md
# Version   : 1.0 (consolidée v29)
# Date      : 2026-08-28
# Licence   : MIT (code) / CC-BY-NC 4.0 (données dérivées)
# Auteur    : CDS/ASAL Engineering
# Livraison : 4 parties affichées en terminal (copier-coller)
# ============================================================================

> NOTE D'USAGE / USAGE NOTE
> Ce document est la source de référence UNIQUE du projet SPACELL-DT.
> Il est livré en 4 parties dans le terminal. Assemblez les parties
> 1 → 2 → 3 → 4 dans l'ordre pour reconstituer le fichier .md complet.
> This document is the SINGLE reference source of the SPACELL-DT project.
> It is delivered in 4 terminal parts. Assemble parts 1 → 4 in order.

---

## TABLE DES MATIÈRES COMPLÈTE / FULL TABLE OF CONTENTS

PARTIE 1/4
   1. Résumé exécutif
   2. Historique du projet et versions
   3. Protocole ZÉRO INVENTION
   4. Architecture physique causale
   5. Modèles physiques cœur
      5.1  Loi de Tada (V1, V2)
      5.2  Diode 1/2-diodes & Lambert W (V3, V4, V5, V7)
      5.3  Correction thermique ECSS (V6, V8)
      5.4  Correction d'irradiance ECSS
      5.5  Bootstrap non paramétrique (UQ)

PARTIE 2/4
   6. Modules avancés M17–M25
   7. Couche données (YAML, POIDS, provenance)
   8. Architecture logicielle (monolithe / modulaire / agents)
   9. Audit : violations V1–V8 et priorités P0–P3

PARTIE 3/4
  10. Tests et validation (T1–T5, cas limites, analytique)
  11. Reproductibilité et traçabilité
  12. Spécifications GUI (DesignArena)
  13. API REST (FastAPI)

PARTIE 4/4
  14. Déploiement (Docker, CI/CD)
  15. Standards de publication (Nature / IEEE)
  16. Roadmap v2 → v4
  17. Références bibliographiques complètes
  18. Glossaire FR/EN
  19. Annexes (constantes, unités, équations)

---
---

# ===========================================================================
# PARTIE 1/4
# ===========================================================================

## 1. RÉSUMÉ EXÉCUTIF / EXECUTIVE SUMMARY

[FR]
SPACELL-DT est un jumeau numérique (digital twin) à base physique destiné à
prédire la dégradation, la récupération et la durée de vie des cellules
solaires spatiales (Si, GaAs, multi-jonctions III-V) sous environnement
orbital. Il relie explicitement :

    ENVIRONNEMENT(t)
        → MÉCANISME PHYSIQUE
        → VARIABLE D'ÉTAT
        → PROPRIÉTÉ MATÉRIAU
        → PARAMÈTRE DISPOSITIF
        → CARACTÉRISTIQUE I-V
        → PERFORMANCE (Pmp, FF, η)
        → DURÉE DE VIE MISSION

Le système couvre : rayonnement (Tada, RDC/NIEL), thermique (ECSS,
vieillissement Arrhenius), optique (Beer-Lambert, darkening), électrique
(diode Lambert W), mécanique (impacts MMOD), plasma/ESD, contamination,
et récupération (recuit thermique multi-familles).

[EN]
SPACELL-DT is a physics-based digital twin predicting degradation, recovery
and lifetime of space solar cells (Si, GaAs, III-V multi-junctions) under
orbital environment. It explicitly links:

    ENVIRONMENT(t) → PHYSICAL MECHANISM → STATE VARIABLE → MATERIAL PROPERTY
    → DEVICE PARAMETER → I-V CHARACTERISTIC → PERFORMANCE → MISSION LIFETIME

Covered phenomena: radiation (Tada, RDC/NIEL), thermal (ECSS, Arrhenius
aging), optical (Beer-Lambert, darkening), electrical (Lambert-W diode),
mechanical (MMOD impacts), plasma/ESD, contamination, and recovery
(multi-family thermal annealing).

### 1.1 Chiffres clés / Key figures
- 92 cellules en base : 33 physiques (données radiation complètes)
  + 59 benchmark (BOL uniquement).
- 25 modules fonctionnels (1–16 cœur + 17–25 avancés).
- 8 canaux de dommage composés multiplicativement.
- 9 mécanismes de régénération référencés (REC_007…REC_014, REC_047).
- 8 corrections de rigueur scientifique (V1–V8).
- 5 auto-tests physiques (T1–T5).
- 4 profils mission (LEO, GEO, JUICE cryo, Mars).
- SEED = 2026 (reproductibilité stricte).

### 1.2 Public cible / Target audience
- Ingénieurs puissance satellite (power budget, EOL).
- Chercheurs physique des semi-conducteurs / PV spatial.
- Agences (ESA, NASA, JAXA, ISRO) et fabricants
  (AZUR SPACE, SolAero, Spectrolab, Sharp, CESI).

---

## 2. HISTORIQUE DU PROJET ET VERSIONS / PROJECT HISTORY

### 2.1 Généalogie des versions / Version genealogy

| Version | Date       | Apport principal / Main contribution              |
|---------|------------|---------------------------------------------------|
| v15     | 2026-06    | Cœur physique Tada + Lambert W + bootstrap        |
| v20     | 2026-07    | Version étendue ~1100 lignes, docstrings PEP-257  |
| v22     | 2026-07    | Compacte 743 lignes (bug afficher_banniere)       |
| v24     | 2026-07    | Fusion v22+v23, module [16] variables fixées      |
| v25     | 2026-07    | Correctifs éditeur (NameError, run_bench flag)    |
| v26     | 2026-08    | Correctifs 1–3 : THERMO SI, flag bench, feuille   |
| v27     | 2026-08    | Provenance F2/F4/S2, poids TC, menu 16 modules    |
| v28     | 2026-08    | M22 8 canaux, M18 recuit, M23 3J, profils CRYO    |
| v29     | 2026-08-28 | M19 vieillissement, M20 impacts/ESD, M24 optique  |

### 2.2 Fichiers maîtres / Master files (architecture monolithe 4 fichiers)

| Fichier                    | Rôle                                    | Version |
|----------------------------|-----------------------------------------|---------|
| jumeau_numerique_final.py  | Moteur physique + menu modules 1–25     | v29     |
| solar_cells_db.py          | Lecteur YAML + API CELLS + validation   | v5/v28  |
| converter.py               | Export Excel 7 feuilles + provenance    | v27/v28 |
| generer_yaml_uniforme.py   | Générateur YAML depuis base legacy      | v5      |
| donnees_cellules_88.py     | Base legacy Python (repli)              | legacy  |

### 2.3 Documents sources / Source documents
- [PDF1] 20.DING.ING.PR.0002_F_V511 1.pdf — Protocole de recherche CDS
  (135 pages, Rev.05) : Tada 3G30C, Lambert W, ECSS, Rs=0.319 Ω, Na=1.5.
- [PDF2] 25.DING.ING.PCCEC.omplement.pdf — Rapport trimestriel RT3 CDS :
  RDC protons (3 MeV = 2.66 ; 9.5 MeV = 9.03), 3G28C, intersections.
- Datasheets constructeurs : AZUR (DB 00010894-02 etc.), SolAero,
  Spectrolab, CESI (≈ 27 documents tracés).

---

## 3. PROTOCOLE ZÉRO INVENTION / ZERO-INVENTION PROTOCOL

### 3.1 Règle absolue / Absolute rule
[FR] Ne jamais inventer de donnée physique, constante, coefficient ou
référence. Toute valeur non sourcée est marquée et tracée.
[EN] Never invent physical data, constants, coefficients or references.
Any unsourced value is marked and traced.

### 3.2 Marqueurs obligatoires / Mandatory markers

| Marqueur              | Signification FR                        | Meaning EN                        |
|-----------------------|-----------------------------------------|-----------------------------------|
| MISSING_DATA          | Donnée indispensable absente            | Required data missing             |
| NON_IDENTIFIABLE      | Paramètre non identifiable → poids 0.0  | Non-identifiable parameter → 0.0  |
| REQUIRES_VALIDATION   | Implémenté mais non validé expériment.  | Implemented, not yet validated    |
| EMPIRICAL_MODEL       | Modèle empirique (fit, pas 1ers principes) | Empirical model (fit)           |
| ASSUMPTION            | Hypothèse explicite documentée          | Documented explicit assumption    |
| MESURÉ / CALCULÉ /    | Niveaux d'information distincts         | Distinct information levels       |
| INFÉRÉ / HYPOTHÉTIQUE |                                         |                                   |

### 3.3 Politique de résolution à 4 niveaux / 4-level resolution policy
Pour tout paramètre physique X (Rs, Na, Ns, tc, Ea, A, α₀, K_d…) :

    NIVEAU 1 : Valeur constructeur (datasheet / YAML)   → poids 1.0
    NIVEAU 2 : Valeur calculée (Lambert W, forme fermée)→ poids 0.8
    NIVEAU 3 : Valeur ajustée (contrainte inverse, Pmax)→ poids 0.5
    NIVEAU 4 : Inconnue / irréelle → 0 ou fallback      → poids 0.0
               (avec ALERTE console explicite)

### 3.4 Système de poids de confiance [S1] / Confidence weights

| Source        | Poids | Exemple                                  |
|---------------|-------|------------------------------------------|
| datasheet     | 1.0   | Voc BOL mesuré, Rs constructeur          |
| analytique    | 0.8   | Rs via Éq. I.8, I0 forme fermée          |
| ajustement    | 0.5   | Na calibré sur Pmax                      |
| estime        | 0.3   | tc interpolé/extrapolé, repli THERMO     |
| inexistant    | 0.0   | NON_IDENTIFIABLE                         |

### 3.5 Règle scientifique fondamentale / Fundamental scientific rule
Toujours distinguer : MESURÉ ≠ CALCULÉ ≠ INFÉRÉ ≠ HYPOTHÉTIQUE.
Chaque propriété physique doit porter : équation, données d'entrée,
hypothèses, source, domaine de validité, niveau de confiance.

---

## 4. ARCHITECTURE PHYSIQUE CAUSALE / CAUSAL PHYSICS ARCHITECTURE

### 4.1 Chaîne mono-jonction / Single-junction chain

    ENVIRONMENT (Φ, T, S, plasma, MMOD…)
      ↓ mécanisme
    STATE VARIABLE (N_t : densité de défauts, D_i : dommage canal i)
      ↓
    MATERIAL PROPERTY (τ : durée de vie, μ : mobilité, α : absorption)
      ↓
    DEVICE PARAMETER (I0, Rs, Rsh, Na, tc)
      ↓
    I-V MODEL (1-diode Lambert W / 2-diodes LLL)
      ↓
    PERFORMANCE (Isc, Voc, Vmp, Imp, Pmp, FF, η)
      ↓
    MISSION LIFETIME (EOL, marges)

### 4.2 Chaîne multi-jonction / Multi-junction chain

    Environment
      ↓
    Top cell / Middle cell / Bottom cell / Tunnel junctions
      ↓
    Subcell I-V (par sous-cellule)
      ↓
    Series-connected MJ I-V (Kirchhoff, current matching)
      ↓
    MPP → Pmp / η

### 4.3 Séparation dégradation / récupération
    dX/dt = G(X, Environment) − R(X, T, OperatingConditions)
    dN_t/dt = G_rad − k(T)·N_t        avec k(T) = A·exp(−Ea/k_B·T)
Un équilibre dynamique n'est JAMAIS qualifié de « self-healing » sans
preuve expérimentale.

---

## 5. MODÈLES PHYSIQUES CŒUR / CORE PHYSICAL MODELS

### 5.1 Loi de Tada (dégradation radiative) / Tada law
Équation / Equation [31, PDF1 p.108 Éq. III.14/III.15] :

    X(Φ) = X₀ · [ 1 − C · ln(1 + Φ/Φ₀) ]

- X₀ : valeur BOL ; C : coefficient de dégradation ;
  Φ₀ : fluence caractéristique (peut être NÉGATIVE) ; Φ : fluence (E14/cm²).
- Exemple tracé (PDF1 Tab.15 p.108, 3G30C) :
  C_Voc = 0.021, Φ₀_Voc = 7.9e13 ; Φ₀_Imp = −1.045e15 (négatif).

CORRECTION V1 — Φ₀ négatif / negative Φ₀ :
    Si Φ₀ < 0 et Φ ≥ |Φ₀|  →  X = 0 (clipping conservatif, hors domaine).
    Si Φ₀ < 0 et Φ < |Φ₀|  →  « bump » initial modélisé (recuit in-situ).
    Statut : ⚠️ ASSUMPTION (clipping hors domaine empirique).

CORRECTION V2 — Projection conservative / conservative projection :
    X(Φ) = min(X(Φ), X₀)   toujours (règle « never above », sécurité
    orbitale : on ne dimensionne JAMAIS un satellite sur le bump).

Extraction de (C, Φ₀) : intersections analytiques par paires de points
(fluence, valeur) + sélection conservative (C minimal) + bootstrap IC 95%.

### 5.2 Modèle diode & Lambert W / Diode model & Lambert W
Équation implicite 1-diode / implicit 1-diode equation [32, PDF1 p.39 I.7] :

    I = I_pv − I₀ · [ exp((V + I·Rs)/(Na·Ns·Vt)) − 1 ]

Solution explicite via Lambert W (branche W₀ uniquement) :

    I = I_pv + I₀ − (Vt/Rs) · W₀(arg)
    arg = (I₀·Rs/Vt) · exp((V + (I_pv + I₀)·Rs)/Vt)
    Vt = k_B·T/q

- Branche W₀ (principale) : seule branche physique en génération
  (4e quadrant). W_{−1} rejetée [33].
- Gardes numériques : clip(exposant, −80, +80), nan_to_num(neginf=−1/e),
  np.real(), courant borné ≥ 0.

CORRECTION V3 — Rs hiérarchique / hierarchical Rs :
    1) YAML/datasheet (poids 1.0) — ex. 3G30C Rs = 0.319 Ω [PDF1 p.109]
    2) Analytique Éq. I.8 (poids 0.8)
    3) Ajustement contrainte Pmax (poids 0.5)
    4) Fallback Rs = 0 + ALERTE « Pmax = borne supérieure » (poids 0.0)

CORRECTION V4 — Na hiérarchique / hierarchical Na :
    1) YAML/datasheet (poids 1.0)
    4) Fallback Na = 1.5 × N_s (ASSUMPTION, PDF1 p.113 Éq. III.13 :
       Na = 1.5 pour 3G30C) + alerte.

CORRECTION V5 — Ns obligatoire / mandatory Ns :
    1) YAML explicite ; 1b) déduction technologie
       (TJ/3G/ZTJ/XTJ → 3 ; QJ/4G → 4 ; SI/GAAS → 1) ;
    4) INCONNU → ERREUR FATALE (pas de défaut silencieux = 1).

CORRECTION V7 — Bornes contextuelles de Na / contextual Na bounds :
    Littérature PV spatiale : n par jonction ∈ [1, 2.5] (standard),
    jusqu'à 3.0 (LILT/tunneling) ; Na_global = Σ n_k (k = 1…Ns).
    - Na < 1.0·Ns        → 🔴 ANOMALIE THERMODYNAMIQUE (alerte)
    - Na > 2.5·Ns        → ⚠️ régime extrême (alerte)
    - Na > 3.0·Ns        → 🔴 hors régime physique connu (alerte)
    AUCUN CLIPPING de Na : liberté totale, traçabilité par alerte.

Modèle 2-diodes (LLL < 200 W/m², missions cryo) :
    Diode 1 : n₁ ≈ 1 (diffusion, bulk) ; Diode 2 : n₂ ≈ 2 (SRH, ZCE).

### 5.3 Correction thermique ECSS / ECSS thermal correction
Équation linéaire [34, PDF1 p.100 Éq. III.9] :

    ΔIsc = (dIsc/dT)·ΔT ;  ΔVoc = (dVoc/dT)·ΔT
    ΔVmp, ΔImp idem.  T_ref = 28 °C = 301.15 K (PAS 25 °C).

CORRECTION V6 — Coefficients hiérarchiques / hierarchical coefficients :
    1) tc_interpole (interpolé à la fluence Φ via np.interp) → poids 1.0
    2) tc_BOL (coefficients fluence nulle)                   → poids 0.8
    4) Repli THERMO générique technologie                    → poids 0.3
    4) Inconnu → dX/dT = 0 + ALERTE                          → poids 0.0
Unités SI imposées au chargement : mV/°C → V/K ; mA/°C → A/K.

CORRECTION V8 — Extrapolation thermique / thermal extrapolation :
    Plage de qualification : [−175 °C, +140 °C] (ECSS / PDF1 p.116 Fig.53).
    Si T hors plage → warnings.warn(UserWarning) + statut OUT_OF_BOUNDS.
    Marge d'alerte : ±15 °C avant bornes → statut WARNING.
    Distinction OBLIGATOIRE : effet thermique INSTANTANÉ (correction I-V)
    vs dégradation thermique CUMULATIVE/permanente (module M19).

### 5.4 Correction d'irradiance ECSS / ECSS irradiance correction
    Isc(S) = Isc_ref · (S/S_ref)
    Voc(S) = Voc_ref + Ns·Vt·ln(S/S_ref)
    S_ref = 1367 W/m² (AM0). Variantes : 136.7 / 135.3 mW/cm².
Validité : S > 0.1·S_ref ; en dessous → modèle 2-diodes LLL.

### 5.5 Bootstrap non paramétrique (UQ) / Non-parametric bootstrap
[7] Efron & Tibshirani. Rééchantillonnage avec remplacement (n = 200,
SEED = 2026). IC 95 % = percentiles [2.5, 97.5] sur C et Φ₀.
Ancrage BOL obligatoire. Cas « BOL only » (len(flu) < 2) : test T5
retourne un message spécifique sans crash. Parallélisation
ProcessPoolExecutor (repli série si échec), barre de progression texte.

---
---
FIN DE LA PARTIE 1/4 / END OF PART 1/4
Tapez « continue » (ou « partie 2 ») pour recevoir la PARTIE 2/4 :
modules avancés M17–M25, couche données, architecture logicielle, audit.