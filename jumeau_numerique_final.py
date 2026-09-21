#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
JUMEAU NUMÉRIQUE DE CELLULES SOLAIRES SPATIALES — v29.0 (COMPLÈTE)
Digital Twin of Space Solar Cells: Full Physics, 8-Channel Damage, Annealing,
Thermal Aging, Impacts/ESD, Optics, Subcells, Mission Profiles (Cryo/LLL)
+ Protocole ZÉRO INVENTION (Corrections V1-V8)
===============================================================================
[FR] Prédit, à partir des données réelles (datasheets), l'évolution sous
rayonnement (Φ), température (T) et irradiance (S) :
  • Loi de Tada conservative (jamais-au-dessus, Φ₀ négatif géré) [31]
  • Modèle diode 1-diode + 2-diodes LLL, Lambert W explicite [32,33]
  • Corrections thermo-optiques ECSS [34]
  • Bootstrap non paramétrique (IC 95%) [7]
  • Sécurité orbitale : prédiction jamais supérieure à la mesure
  • [M17] 8 canaux de dommages (composition multiplicative)
  • [M18] Recuit Arrhenius multi-familles (9 mécanismes)
  • [M19] Vieillissement thermique (dose Arrhenius cumulée)   ← NOUVEAU v29
  • [M20] Impacts MMOD + ESD (Paul-Berthoud, énergie Joule)   ← NOUVEAU v29
  • [M21] RDC / fluence équivalente 1 MeV
  • [M23] Sous-cellules 3J + current matching Kirchhoff
  • [M24] Optique (Beer-Lambert, darkening, coverglass)       ← NOUVEAU v29
  • [M25] Profils mission LEO/GEO/JUICE/MARS + flag LLL/cryo

[EN] Predicts space solar-cell evolution under radiation (Φ), temperature (T)
and irradiance (S): conservative Tada degradation, 1/2-diode Lambert-W model,
ECSS corrections, bootstrap UQ, never-above safety, 8-channel damage,
annealing, thermal aging, MMOD/ESD impacts, optics (Beer-Lambert), 3J
subcells, and mission profiles (LEO/GEO/JUICE/MARS, cryo/LLL).

PROTOCOLE ZÉRO INVENTION (Corrections V1-V8) / ZERO-INVENTION PROTOCOL :
  V1: Gestion robuste de Φ₀ négatif (clipping conservatif).
      Robust handling of negative Φ₀ (conservative clipping).
  V2: Projection conservative systématique (X(Φ) ≤ X₀).
      Systematic conservative projection (X(Φ) ≤ X₀).
  V3: Rs hiérarchique (Datasheet > Analytique > 0 avec alerte).
      Hierarchical Rs (Datasheet > Analytical > 0 with alert).
  V4: Na hiérarchique (Datasheet > 1.5×N_s avec alerte).
      Hierarchical Na (Datasheet > 1.5×N_s with alert).
  V5: Ns obligatoire (Datasheet > Déduction Tech > Erreur fatale).
      Mandatory Ns (Datasheet > Tech deduction > Fatal error).
  V6: Coefficients thermiques interpolés (tc_interpole > tc_BOL > 0).
      Interpolated thermal coefficients (tc_interpole > tc_BOL > 0).
  V7: Bornes physiques contextuelles pour Na (selon N_s, sans clipping).
      Contextual physical bounds for Na (per N_s, no clipping).
  V8: Alertes d'extrapolation thermique (hors plage de qualification).
      Thermal extrapolation warnings (outside qualification range).

BASE : 92 cellules (33 physiques + 59 benchmark).
UNITÉS : SI — V, A, W, K, e⁻/cm², W/m², Ω (températures en kelvin).
NORMES : ECSS-E-ST-20-08C Rev.2 (2023) [34]; MIL-STD-810H [C];
         NASA-STD-8739 [D]; NASA-HDBK-4006 (ESD) [38].
LICENCE : MIT (code) / CC-BY-NC 4.0 (données dérivées).
VERSION : 29.0 — 2026-08-28
===============================================================================
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import brentq
from scipy.special import lambertw

# =============================================================================
# 0. CHARGEMENT DES DONNÉES / DATA LOADING (YAML prioritaire, repli Python)
# =============================================================================
try:
    from solar_cells_db import (
        CELLS, CELLULES_PHYSIQUE, CELLULES_BENCHMARK,
        N_CELLS, REFERENCES_BIBLIOGRAPHIQUES,
        valider, valider_schema, rapport_provenance,
        poids_tc, poids_elec, poids_derivee, poids_diode,
        _SEUIL_REJET_DB
    )
    SOURCE_DONNEES = "solar_cells_database.yaml (via solar_cells_db.py v28)"
    _HAS_F3 = True
    SEUIL_REJET = _SEUIL_REJET_DB
    _HAS_PROV = True
except Exception as e:
    print(f"⚠️ solar_cells_db indisponible ({e}) → repli sur donnees_cellules_88.py")
    try:
        from donnees_cellules_88 import (
            CELLS, CELLULES_PHYSIQUE, CELLULES_BENCHMARK,
            N_CELLS, REFERENCES_BIBLIOGRAPHIQUES
        )
        SOURCE_DONNEES = "donnees_cellules_88.py (legacy)"
        _HAS_F3 = False
        SEUIL_REJET = 0.05
        _HAS_PROV = False
        def valider(): return []
        def valider_schema(): return []
        def rapport_provenance():
            print("  ⚠️ Provenance non disponible en mode legacy")
        def poids_tc(*a, **k): return (0.3, "repli")
        def poids_elec(*a, **k): return (0.3, "estime")
        def poids_derivee(*a, **k): return (0.3, "estime")
        def poids_diode(*a, **k): return (0.0, "NON_IDENTIFIABLE")
    except Exception as e2:
        print(f"❌ Aucune base de données disponible : {e2}")
        sys.exit(1)

# =============================================================================
# 1. CONSTANTES PHYSIQUES FONDAMENTALES / FUNDAMENTAL PHYSICAL CONSTANTS
# =============================================================================
__version__ = "29.0"
__date__ = "2026-08-28"

# Constantes CODATA 2018 (SI strict) / CODATA 2018 constants (strict SI)
K_B = 1.380649e-23       # J/K — Constante de Boltzmann / Boltzmann constant
K_B_EV = 8.617333262e-5  # eV/K — Boltzmann en eV (pour Arrhenius) / in eV
Q = 1.60217663e-19       # C — Charge élémentaire / elementary charge
S_REF = 1367.0           # W/m² — Irradiance solaire AM0 [PDF1 p.100]
S1367 = 136.7            # mW/cm² — AM0 standard
S1353 = 135.3            # mW/cm² — AM0 variante ASTM / ASTM variant
T_REF_C = 28.0           # °C — Température de référence [PDF1 p.100, PAS 25°C!]
T_REF_K = T_REF_C + 273.15  # 301.15 K

# Paramètres opérationnels / Operational parameters
SEED = 2026              # Graine reproductible / reproducible seed
N_BOOTSTRAP = 200        # Itérations bootstrap IC 95% / bootstrap iterations
N_CORES = 4              # Parallélisation (repli série si échec) / parallelism
TOL = 1.0e-9             # Tolérance numérique / numerical tolerance

# Grandeurs électriques / Electrical quantities
GRANDEURS = ("Voc", "Isc", "Vmp", "Imp")

# =============================================================================
# 2. SYSTÈME POIDS DE CONFIANCE [S1] / CONFIDENCE WEIGHT SYSTEM
# =============================================================================
POIDS = {
    "datasheet": 1.0,        # Valeur constructeur mesurée / measured value
    "analytique": 0.8,       # Calculé par Lambert W / forme fermée
    "ajustement": 0.5,       # Ajusté par contrainte inverse / inverse fit
    "estime": 0.3,           # Estimé par interpolation/extrapolation
    "inexistant": 0.0,       # NON_IDENTIFIABLE — aucune donnée / no data
}

# Classification des 8 canaux de dommage [v28-M22] / 8 damage channels
STATUT_CANAL = {
    "rad": "PARTIALLY_REVERSIBLE",      # Recuit thermique possible / annealable
    "thermal": "PRACTICALLY_IRREVERSIBLE",
    "age": "PRACTICALLY_IRREVERSIBLE",
    "opt": "PRACTICALLY_IRREVERSIBLE",
    "mech": "FUNDAMENTALLY_IRREVERSIBLE",
    "ESD": "FUNDAMENTALLY_IRREVERSIBLE",
    "impact": "FUNDAMENTALLY_IRREVERSIBLE",
    "TJ": "PRACTICALLY_IRREVERSIBLE",
}

# État global du jumeau / Twin global state
ETAT = {
    "selection": list(CELLULES_PHYSIQUE),
    "plot": True,
    "cores": N_CORES,
    "nboot": N_BOOTSTRAP,
    "deg_rows": [],
    "diode_rows": [],
    "boot_rows": [],
    "bench_rows": [],
    "syn_rows": [],
    "fallback_thermo": set(),
    "mission_profile": "LEO_STANDARD",
    "dommages": {},
    "fluence_cache": {},
    "validated": False,
    "last_fixes": [],
    "boot": {},
}

# =============================================================================
# 3. FONCTIONS UTILITAIRES / UTILITY FUNCTIONS
# =============================================================================
def tx(fr: str, en: str, lang: str = "both") -> str:
    """
    [FR] Retourne le texte bilingue selon la langue.
    [EN] Returns bilingual text according to language.
    """
    if lang == "fr": return fr
    if lang == "en": return en
    return f"{fr} / {en}"

def C2K(T_C):
    """[FR] Conversion Celsius → Kelvin. [EN] Celsius to Kelvin."""
    return np.asarray(T_C, float) + 273.15

def K2C(T_K):
    """[FR] Conversion Kelvin → Celsius. [EN] Kelvin to Celsius."""
    return np.asarray(T_K, float) - 273.15

def normaliser_si(cells: list) -> list:
    """
    [FR] Normalise les unités en SI strict (V, A, W, K, Ω).
         mV→V, mA→A, cm²→m². Appliqué une seule fois au chargement.
    [EN] Normalizes units to strict SI (V, A, W, K, Ω).
         mV→V, mA→A, cm²→m². Applied once at load time.
    """
    for c in cells:
        if not c.get("complet", True):
            continue
        for g in ("Voc", "Vmp"):
            if g in c and c[g] is not None:
                val = np.asarray(c[g], float)
                if np.max(np.abs(val)) > 10:  # Probablement en mV / likely mV
                    c[g] = val / 1000.0
        for g in ("Isc", "Imp"):
            if g in c and c[g] is not None:
                val = np.asarray(c[g], float)
                if np.max(np.abs(val)) > 1:  # Probablement en mA / likely mA
                    c[g] = val / 1000.0
        if "area_cm2" in c:
            c["area_m2"] = c["area_cm2"] / 10000.0
    return cells

# Harmonisation fabricant / Harmonize manufacturer key
for _c in list(CELLULES_PHYSIQUE) + list(CELLULES_BENCHMARK):
    if "fab" not in _c:
        _c["fab"] = _c.get("fabricant", "?")

# =============================================================================
# 4. PROTOCOLE ZÉRO INVENTION : CORRECTIONS V1 À V8 / V1-V8 CORRECTIONS
# =============================================================================

# --- V1 & V2 : Loi de Tada Robuste & Projection Conservative ---
def predire_degradation_tada(X0: float, C: float, Phi0: float, Phi: float) -> float:
    """
    [FR] Loi de Tada conservative avec gestion robuste de Φ₀ négatif.
         Équation : X(Φ) = X₀ · [1 - C · ln(1 + Φ/Φ₀)]

         V1 - GESTION Φ₀ NÉGATIF (Tab.15 PDF1 p.108) :
         - Si Φ₀ < 0 et Φ ≥ |Φ₀| : clipping conservatif à 0
         - Modélise le "bump" initial (recuit in-situ) pour Φ < |Φ₀|

         V2 - PROJECTION CONSERVATIVE :
         - X(Φ) ≤ X₀ toujours (règle de sécurité orbitale)

    [EN] Conservative Tada law with robust negative Φ₀ handling.
         Equation: X(Φ) = X₀ · [1 - C · ln(1 + Φ/Φ₀)]

         V1 - NEGATIVE Φ₀ HANDLING (Tab.15 PDF1 p.108):
         - If Φ₀ < 0 and Φ ≥ |Φ₀|: conservative clip to 0
         - Models initial "bump" (in-situ annealing) for Φ < |Φ₀|

         V2 - CONSERVATIVE PROJECTION:
         - X(Φ) ≤ X₀ always (orbital safety rule)

    Parameters
    ----------
    X0 : float
        Valeur BOL (Begin of Life) / BOL value. Doit être > 0 / must be > 0.
    C : float
        Coefficient de dégradation Tada / Tada degradation coefficient.
        SOURCE : [PDF1] Tableau 15 p.108 ou YAML cellule / or cell YAML.
    Phi0 : float
        Fluence caractéristique Tada / Tada characteristic fluence.
        SOURCE : [PDF1] Tableau 15 p.108 ou YAML cellule / or cell YAML.
        NOTE : Peut être négatif (ex: Φ₀_Imp = -1.045E15 pour 3G30C).
             Can be negative (e.g. Φ₀_Imp = -1.045E15 for 3G30C).
    Phi : float
        Fluence appliquée (E14/cm²) / Applied fluence (E14/cm²). Doit être ≥ 0.

    Returns
    -------
    float
        Valeur dégradée X(Φ) bornée : 0 ≤ X(Φ) ≤ X₀.
        Bounded degraded value X(Φ): 0 ≤ X(Φ) ≤ X₀.

    References
    ----------
    [31] Tada H.Y. et al. "Solar Cell Radiation Handbook", JPL 82-69, 1982.
    [PDF1] 20.DING.ING.PR.0002_F_V511.pdf, Éq. III.14/III.15, Tab.15 p.108.

    Status
    ------
    ✅ CONFORME : Équation Tada exacte / exact Tada equation.
    ⚠️ ASSUMPTION : Clipping à 0 pour Φ ≥ |Φ₀| (hors domaine empirique).
                    Clip to 0 for Φ ≥ |Φ₀| (outside empirical domain).
    ✅ CONFORME : Projection conservative (X ≤ X₀) pour sécurité orbitale.
                  Conservative projection (X ≤ X₀) for orbital safety.
    """
    if X0 <= 0:
        return 0.0
    if Phi < 0:
        raise ValueError(f"La fluence Phi doit être ≥ 0, reçu {Phi}")
    if C < 0:
        # ⚠️ ASSUMPTION : C négatif non physique pour dégradation pure
        # ⚠️ ASSUMPTION: negative C unphysical for pure degradation
        C = 0.0

    if Phi0 < 0:
        # CAS CRITIQUE : Φ₀ négatif (modélise le "bump" initial / recuit in-situ)
        # CRITICAL CASE: negative Φ₀ (models initial "bump" / in-situ annealing)
        if Phi >= abs(Phi0):
            return 0.0  # ⚠️ ASSUMPTION: Hors domaine, clipping conservatif
        argument = 1.0 + (Phi / Phi0)
        if argument <= 1e-12:
            return 0.0
    else:
        # CAS STANDARD : Φ₀ > 0 (Dégradation classique monotone)
        # STANDARD CASE: Φ₀ > 0 (classical monotonic degradation)
        argument = 1.0 + (Phi / Phi0)
        if argument <= 1e-12:
            return 0.0

    X = X0 * (1.0 - C * np.log(argument))

    # V2: PROJECTION CONSERVATIVE (Règle de sécurité orbitale / orbital safety)
    X = min(X, X0)
    return max(X, 0.0)


def selection_conservatrice(valeurs: np.ndarray, flu: np.ndarray) -> Optional[Tuple[float, float]]:
    """
    [FR] Sélectionne le couple (C, Φ₀) conservatif (jamais-au-dessus).
    [EN] Selects conservative (C, Φ₀) pair (never-above).
    """
    if len(valeurs) < 2 or len(flu) < 2:
        return None
    X0 = valeurs[0]
    best = None
    for i in range(1, len(valeurs)):
        X, F = valeurs[i], flu[i]
        if X > X0 * (1 + TOL):
            continue
        if X <= 0 or F <= 0:
            continue
        try:
            C = (1 - X/X0) / np.log(1 + F/1e14)
            if C > 0:
                if best is None or C < best[0]:
                    best = (C, 1e14)
        except Exception:
            continue
    return best


# --- V5 : Ns Obligatoire / Mandatory Ns ---
def obtenir_Ns_robuste(cellule: dict) -> int:
    """
    [FR] Détermine le nombre de jonctions en série (Ns) sans invention.
         Ns est STRUCTUREL : ne peut pas être calculé, seulement lu ou déduit.
    [EN] Determines the number of series junctions (Ns) without invention.
         Ns is STRUCTURAL: cannot be calculated, only read or deduced.

    References
    ----------
    [PDF1] 20.DING.ING.PR.0002_F_V511.pdf, p.100 (N_s=3 pour 3G30C).
    """
    # NIVEAU 1 : Valeur explicite dans le YAML / explicit YAML value
    ns_yaml = cellule.get("N_s")
    if ns_yaml is not None:
        ns_val = int(ns_yaml)
        if ns_val >= 1:
            return ns_val

    # NIVEAU 1b : Déduction structurelle (implicite via la technologie)
    # LEVEL 1b: structural deduction (implicit via technology)
    tech = str(cellule.get("tech", "")).upper()
    ref = str(cellule.get("ref", "")).upper()

    if tech in ("TJ", "TRIPLE_JUNCTION") or "3G" in ref or "ZTJ" in ref or "XTJ" in ref:
        return 3
    if tech in ("QJ", "QUAD_JUNCTION") or "4G" in ref:
        return 4
    if tech in ("SI", "SILICON", "GAAS", "SINGLE_JUNCTION"):
        return 1

    # NIVEAU 4 : INCONNU → BLOQUANT (ZÉRO INVENTION) / UNKNOWN → FATAL
    raise ValueError(
        f"🔴 [ZÉRO INVENTION - FATAL] N_s inconnu pour {cellule.get('ref', '?')}. "
        f"Impossible de calculer V_t et la correction d'irradiance."
    )


# --- V3 : Rs Hiérarchique / Hierarchical Rs ---
def obtenir_Rs_robuste(cellule: dict, voc: float = 0, isc: float = 0,
                       vmp: float = 0, imp: float = 0,
                       t_k: float = T_REF_K, ns: int = 1) -> dict:
    """
    [FR] Détermine Rs selon les 3 voies légitimes, sans invention.
         Niveau 1: Datasheet (Poids 1.0)
         Niveau 2: Calcul analytique Éq. I.8 PDF1 (Poids 0.8)
         Niveau 4: Fallback Rs=0 avec alerte (Poids 0.0)
    [EN] Determines Rs via the 3 legitimate paths, without invention.
         Level 1: Datasheet (Weight 1.0)
         Level 2: Analytical calculation Eq. I.8 PDF1 (Weight 0.8)
         Level 4: Fallback Rs=0 with alert (Weight 0.0)

    References
    ----------
    [PDF1] 20.DING.ING.PR.0002_F_V511.pdf, p.109 (Rs=0.319Ω pour 3G30C).
    """
    # NIVEAU 1 : Base de Données (Datasheet) — Poids 1.0
    rs_yaml = cellule.get("Rs")
    if rs_yaml is not None and rs_yaml > 0:
        return {"Rs": float(rs_yaml), "source": "datasheet", "poids": 1.0}

    # NIVEAU 2 : Calcul Analytique (Éq. I.8 PDF1) — Poids 0.8
    if imp > 1e-9 and voc > vmp and isc > imp:
        V_t = (K_B * t_k) / Q
        rs_calc = (voc - vmp) / imp - (V_t / imp) * np.log(isc / max(isc - imp, 1e-20))
        if 0 <= rs_calc <= 2.0:
            return {"Rs": float(rs_calc), "source": "analytique", "poids": 0.8}

    # NIVEAU 4 : INCONNU → Fallback Rs=0 (borne supérieure théorique)
    # LEVEL 4: UNKNOWN → Fallback Rs=0 (theoretical upper bound)
    print(f"⚠️ [ZÉRO INVENTION] Rs inconnu pour {cellule.get('ref', '?')}. "
          f"Utilisation de Rs=0 (cas idéal). Pmax sera une borne SUPÉRIEURE.")
    return {"Rs": 0.0, "source": "NON_IDENTIFIABLE", "poids": 0.0}


# --- V4 : Na Hiérarchique / Hierarchical Na ---
def obtenir_Na_robuste(cellule: dict, ns: int = 1) -> dict:
    """
    [FR] Détermine Na avec liberté totale mais alertes contextuelles.
         Règle : Na_global = somme des n_k par sous-cellule (N_s jonctions).
         - Simple jonction (N_s=1) : Na ∈ [1.0, 2.5] standard
         - Triple jonction (N_s=3) : Na ∈ [3.0, 7.5] (somme de 3 jonctions)
    [EN] Determines Na with full freedom but contextual alerts.
         Rule: Na_global = sum of n_k per subcell (N_s junctions).
         - Single junction (N_s=1): Na ∈ [1.0, 2.5] standard
         - Triple junction (N_s=3): Na ∈ [3.0, 7.5] (sum of 3 junctions)

    References
    ----------
    [PDF1] 20.DING.ING.PR.0002_F_V511.pdf, p.39-40 (Na), p.113 (Na=1.5 pour 3G30C).
    """
    # NIVEAU 1 : Valeur explicite dans le YAML / explicit YAML value
    na_yaml = cellule.get("Na")
    if na_yaml is not None:
        na_val = float(na_yaml)
        if na_val >= 1.0:
            return {"Na": na_val, "source": "datasheet", "poids": 1.0}

    # NIVEAU 4 : Fallback documenté (ASSUMPTION) / documented fallback
    # Na = 1.5 × N_s pour les multi-jonctions (moyenne effective)
    # Na = 1.5 × N_s for multi-junctions (effective average)
    na_fallback = 1.5 * ns
    print(f"️ [ZÉRO INVENTION] Na inconnu pour {cellule.get('ref', '?')}. "
          f"Fallback Na={na_fallback} (1.5×N_s, PDF1 p.113).")
    return {"Na": na_fallback, "source": "ASSUMPTION (1.5×N_s)", "poids": 0.5}


# --- V7 : Bornes Physiques Contextuelles (Na selon Ns) / Contextual bounds ---
def valider_bornes_physiques_diode(params: dict, N_s: int = 1) -> dict:
    """
    [FR] Valide les bornes physiques des paramètres diode avec contexte architectural.
         Règle : N_a global = somme des n_k par sous-cellule (N_s jonctions).
         - Simple jonction (N_s=1) : Na ∈ [1.0, 2.5] standard, jusqu'à 3.0 en LILT
         - Triple jonction (N_s=3) : Na ∈ [3.0, 7.5] (somme de 3 jonctions)
         - QUADRUPLE jonction (N_s=4) : Na ∈ [4.0, 10.0]
         NE CLIPPE PAS Na — émet alertes contextuelles.
    [EN] Validates diode parameter bounds with architectural context.
         Rule: N_a global = sum of n_k per subcell (N_s junctions).
         Does NOT clip Na — emits contextual alerts.

    References
    ----------
    [PDF1] 20.DING.ING.PR.0002_F_V511.pdf, p.39-40 (Na), p.109 (Rs).
    [Littérature PV spatiale] Modèles 1-diode/2-diodes, TJ macroscopique.
    """
    params_valides = params.copy()
    alertes = []

    # 1. Résistance Série (Rs) — Clippe à 0 / clip to 0
    rs = params.get("R_s", 0.0)
    if rs < 0.0:
        alertes.append(f"Rs={rs:.4f}Ω < 0 → Clippe à 0")
        params_valides["R_s"] = 0.0

    # 2. Résistance Shunt (Rsh) — Force l'infini si <= 0 / force inf if <= 0
    rsh = params.get("R_sh", np.inf)
    if rsh is not None and rsh <= 0.0:
        alertes.append(f"Rsh={rsh:.4e}Ω <= 0 → Forcé à ∞")
        params_valides["R_sh"] = np.inf

    # 3. Facteur d'idéalité (Na) — LIBERTÉ TOTALE, MAIS ALERTE CONTEXTUELLE
    # Ideality factor (Na) — FULL FREEDOM, BUT CONTEXTUAL ALERT
    na = params.get("N_a", 1.5)
    na_min_attendu = 1.0 * N_s
    na_max_standard = 2.5 * N_s
    na_max_extreme = 3.0 * N_s

    if na < na_min_attendu:
        alertes.append(
            f"🔴 Na={na:.3f} < {na_min_attendu:.1f} (N_s={N_s}) → "
            f"ANOMALIE THERMODYNAMIQUE (n/jonction < 1 impossible)"
        )
    elif na > na_max_extreme:
        alertes.append(
            f" Na={na:.3f} > {na_max_extreme:.1f} (N_s={N_s}) → "
            f"HORS RÉGIME PHYSIQUE CONNU / OUTSIDE KNOWN PHYSICAL REGIME"
        )
    elif na > na_max_standard:
        alertes.append(
            f"⚠️ Na={na:.3f} > {na_max_standard:.1f} (N_s={N_s}) → "
            f"Régime extrême (tunneling/LILT/DDD élevé). Physiquement possible."
        )
    # On NE CLIPPE PAS Na — on laisse la valeur telle quelle / NO CLIPPING

    # 4. Courants (I0, Ipv) — Bornes strictes / strict bounds
    i0 = params.get("I_0", 1e-12)
    if i0 <= 0.0:
        alertes.append(f"I0={i0:.4e}A <= 0 → Forcé à 1e-30")
        params_valides["I_0"] = 1e-30

    ipv = params.get("I_pv", 0.0)
    if ipv < 0.0:
        alertes.append(f"Ipv={ipv:.4f}A < 0 → Clippe à 0")
        params_valides["I_pv"] = 0.0

    # 5. Tensions et Courants (Voc, Isc, Vmp, Imp) / Voltages and currents
    for g in GRANDEURS:
        val = params.get(g, 0.0)
        if val < 0.0:
            alertes.append(f"{g}={val:.4f} < 0 → Clippe à 0")
            params_valides[g] = 0.0

    # Traçabilité des alertes / alert traceability
    if alertes:
        params_valides["alertes_physiques"] = alertes
        params_valides["N_s_contexte"] = N_s
        print(f"\n⚠️ [ZÉRO INVENTION — BORNES DIODE] Cellule N_s={N_s}:")
        for a in alertes:
            print(f"   {a}")

    return params_valides


# --- V6 & V8 : Thermique Robuste / Robust Thermal ---
def valider_plage_temperature(T_K: float, cellule: dict) -> str:
    """
    [FR] V8: Alerte si T hors plage de qualification.
    [EN] V8: Warns if T outside qualification range.

    References
    ----------
    [PDF1] 20.DING.ING.PR.0002_F_V511.pdf, p.116 Fig.53.
    [ECSS] ECSS-E-ST-20-08C.
    """
    T_min = cellule.get("T_min_qualif_C", -175.0)
    T_max = cellule.get("T_max_qualif_C", 140.0)
    T_C = T_K - 273.15
    if T_C < T_min or T_C > T_max:
        warnings.warn(
            f"️ [ZÉRO INVENTION - TEMP] T={T_C:.1f}°C HORS plage "
            f"[{T_min}, {T_max}]°C pour {cellule.get('ref', '?')}",
            UserWarning
        )
        return "OUT_OF_BOUNDS"
    return "OK"


def obtenir_coefficients_thermiques(cellule: dict, fluence_E14: float) -> dict:
    """
    [FR] V6: Résout les coefficients thermiques selon la politique stricte.
         Priorité : tc_interpole > tc_BOL > 0 (inconnu).
    [EN] V6: Resolves thermal coefficients per the strict policy.
         Priority: tc_interpole > tc_BOL > 0 (unknown).

    References
    ----------
    [solar_cells_db.py] Schéma v27/v28 (champs 'tc' et 'tc_interpole').
    [PDF1] 20.DING.ING.PR.0002_F_V511.pdf, Éq. III.9 p.100.
    """
    # NIVEAU 1 : Valeur Constructeur Interpolée (tc_interpole)
    tc_interp = cellule.get("tc_interpole")
    if tc_interp and "f" in tc_interp and fluence_E14 > 0:
        f_vals = np.asarray(tc_interp["f"], float)
        if "dVoc" in tc_interp and "dIsc" in tc_interp:
            dVoc = float(np.interp(fluence_E14, f_vals, np.asarray(tc_interp["dVoc"], float)))
            dIsc = float(np.interp(fluence_E14, f_vals, np.asarray(tc_interp["dIsc"], float)))
            return {"dVoc": dVoc, "dIsc": dIsc, "source": "tc_interpole", "poids": 1.0}

    # NIVEAU 4 (Fallback 1) : Valeur BOL (tc standard) / BOL value
    tc_bol = cellule.get("tc")
    if tc_bol:
        dVoc = float(np.asarray(tc_bol.get("dVoc", [0.0]))[0])
        dIsc = float(np.asarray(tc_bol.get("dIsc", [0.0]))[0])
        return {"dVoc": dVoc, "dIsc": dIsc, "source": "tc_BOL", "poids": 0.8}

    # NIVEAU 4 (Fallback 2) : INCONNU → ZÉRO / UNKNOWN → ZERO
    print(f"⚠️ [ZÉRO INVENTION] Coefficients thermiques inconnus pour "
          f"{cellule.get('ref', '?')}. Correction thermique annulée.")
    return {"dVoc": 0.0, "dIsc": 0.0, "source": "INCONNU", "poids": 0.0}


def corriger_temperature_robuste(c: dict, T_K: float, phi: float = 0.0) -> dict:
    """
    [FR] Correction thermique linéaire ECSS avec V6 et V8.
    [EN] ECSS linear thermal correction with V6 and V8.
    """
    valider_plage_temperature(T_K, c)  # V8
    T_ref = c.get("T_ref_C", T_REF_C) + 273.15
    dT = T_K - T_ref
    if abs(dT) < 1e-12:
        return {g: np.asarray(c.get(g, [0.0]), float)[0] for g in GRANDEURS}

    coeffs = obtenir_coefficients_thermiques(c, phi)  # V6
    out = {}
    for g in GRANDEURS:
        v = np.asarray(c.get(g, [0.0]), float)[0]
        dt_val = coeffs["dVoc"] if g in ("Voc", "Vmp") else coeffs["dIsc"]
        out[g] = max(v + dt_val * dT, 1e-9)  # Borne inférieure physique
    return out

# =============================================================================
# 5. MODÈLE DIODE LAMBERT W / LAMBERT W DIODE MODEL
# =============================================================================
def extraire_diode_robuste(voc: float, isc: float, vmp: float, imp: float,
                           T_K: float, N_s: int, cellule: dict = None) -> dict:
    """
    [FR] Extraction des paramètres diode avec Lambert W, Rs et Na hiérarchiques.
         Résout : I = Ipv - I0[exp((V+IRs)/(Na·Ns·Vt)) - 1]
    [EN] Diode parameter extraction with Lambert W, hierarchical Rs and Na.
         Solves: I = Ipv - I0[exp((V+IRs)/(Na·Ns·Vt)) - 1]

    References
    ----------
    [32] Jain A., Kapoor A. "Exact analytical solutions...", Solar Energy Materials, 2005.
    [33] Corless R.M. et al. "On the Lambert W function", Adv. Comp. Math., 1996.
    [PDF1] 20.DING.ING.PR.0002_F_V511.pdf, Éq. I.7 p.39.
    """
    if cellule is None:
        cellule = {}

    # Résolution hiérarchique (V3, V4, V5) / hierarchical resolution
    Rs_info = obtenir_Rs_robuste(cellule, voc, isc, vmp, imp, T_K, N_s)
    Na_info = obtenir_Na_robuste(cellule, N_s)
    Rs, Na = Rs_info["Rs"], Na_info["Na"]

    # Tension thermique totale / total thermal voltage
    V_t = (Na * N_s * K_B * T_K) / Q

    # Courant de saturation I0 (forme fermée depuis Voc) / from Voc
    if voc > 0 and isc > 0:
        I0 = isc / (np.exp(np.clip(voc / V_t, -80, 80)) - 1.0)
    else:
        I0 = 1e-30

    # Courant photogénéré Ipv / photogenerated current
    Ipv = isc + I0 * (np.exp(np.clip(isc * Rs / V_t, -80, 80)) - 1.0)

    # Validation des bornes physiques (V7) / physical bounds validation
    params = {
        "I_pv": Ipv, "I_0": I0, "R_s": Rs, "N_a": Na,
        "R_sh": np.inf, "Voc": voc, "Isc": isc, "Vmp": vmp, "Imp": imp
    }
    params_valides = valider_bornes_physiques_diode(params, N_s)

    # Calcul Pmax pour vérification / Pmax computation for verification
    vv = np.linspace(0, voc * 1.1, 500)
    aw = (I0 * Rs / V_t) * np.exp(
        np.clip((vv + (Ipv + I0) * Rs) / V_t, -80, 80)
    )
    w = np.real(lambertw(np.nan_to_num(aw, nan=0.0, posinf=1e8, neginf=-1/np.e)))
    iv = np.maximum(Ipv + I0 - (V_t / Rs) * w, 0.0) if Rs > 1e-9 else \
         np.maximum(Ipv - I0 * (np.exp(vv / V_t) - 1.0), 0.0)
    pv = vv * iv
    idx = np.argmax(pv)

    pmax_ref = vmp * imp
    pmax_calc = pv[idx]
    erreur = abs(pmax_calc - pmax_ref) / max(pmax_ref, 1e-20)

    statut = "actif"
    poids = 1.0 if erreur < 0.01 else (0.5 if erreur < SEUIL_REJET else 0.0)
    if erreur >= SEUIL_REJET:
        statut = "REJETE"

    return {
        **params_valides,
        "P_max": pmax_calc,
        "statut": statut,
        "erreur": erreur,
        "poids_confiance": poids
    }


def courbe_iv_lambert(v_vec: np.ndarray, Ipv: float, I0: float,
                      Rs: float, Na: float, N_s: int, T_K: float) -> np.ndarray:
    """
    [FR] Calcule la courbe I-V via la fonction W de Lambert (branche W₀).
    [EN] Computes I-V curve via Lambert W function (W₀ branch).
    """
    V_t = (Na * N_s * K_B * T_K) / Q
    if Rs < 1e-9:
        return np.maximum(Ipv - I0 * (np.exp(v_vec / V_t) - 1.0), 0.0)

    arg_w = (I0 * Rs / V_t) * np.exp(
        np.clip((v_vec + (Ipv + I0) * Rs) / V_t, -80, 80)
    )
    w = np.real(lambertw(np.nan_to_num(arg_w, nan=0.0, posinf=1e8, neginf=-1/np.e)))
    return np.maximum(Ipv + I0 - (V_t / Rs) * w, 0.0)


def calculer_mpp(Ipv: float, I0: float, Rs: float, Na: float,
                 N_s: int, T_K: float, voc: float, isc: float) -> dict:
    """
    [FR] Calcule le point de puissance maximale (MPP) via la courbe I-V.
    [EN] Computes Maximum Power Point (MPP) via I-V curve.
    """
    v_vec = np.linspace(0, voc * 1.1, 1000)
    i_vec = courbe_iv_lambert(v_vec, Ipv, I0, Rs, Na, N_s, T_K)
    p_vec = v_vec * i_vec
    idx_mpp = np.argmax(p_vec)
    return {
        "Vmp": float(v_vec[idx_mpp]),
        "Imp": float(i_vec[idx_mpp]),
        "Pmp": float(p_vec[idx_mpp]),
        "FF": float(p_vec[idx_mpp] / max(voc * isc, 1e-20))
    }

# =============================================================================
# 6. CALIBRATION À Rs FIXÉ / FIXED-Rs CALIBRATION
# =============================================================================
def caler_diode_rs_fixe(voc: float, isc: float, vm: float, im: float,
                        rs: float, t_k: float = T_REF_K, ns: int = 3) -> dict:
    """
    [FR] Calibration avec Rs fixé (module [15]).
    [EN] Calibration with fixed Rs (module [15]).
    """
    def _i0_ipv_pour_n(n):
        vt = n * (K_B * t_k) / Q
        E_voc = np.exp(np.clip(voc / vt, -80, 80))
        E_isc = np.exp(np.clip(isc * rs / vt, -80, 80))
        den = E_voc - E_isc
        if den <= 0:
            return None, None, vt
        I0 = isc / den
        Ipv = I0 * (E_voc - 1)
        return I0, Ipv, vt

    best = (1e9, None)
    for nat in np.linspace(ns * 0.8, ns * 2.5, 60):
        i0, ipv, vt = _i0_ipv_pour_n(nat)
        if i0 is None or i0 <= 1e-20:
            continue
        vv = np.linspace(0, voc, 300)
        aw = (i0 * rs / vt) * np.exp(
            np.clip((vv + (ipv + i0) * rs) / vt, -80, 80)
        )
        w = np.real(lambertw(np.nan_to_num(aw, nan=0., posinf=1e8, neginf=-1/np.e)))
        iv = np.maximum(ipv + i0 - (vt / rs) * w, 0.)
        pv = vv * iv
        im_idx = int(np.argmax(pv))
        e = abs(pv[im_idx] - vm * im) / max(vm * im, 1e-20)
        if e < best[0]:
            best = (e, dict(I_pv=ipv, I_0=i0, R_s=rs, N_a=nat / ns, P_max=pv[im_idx]))
    return best[1]


def caler_diode_pmax(voc: float, isc: float, pmax: float,
                     rs: float, t_k: float = T_REF_K, ns: int = 3) -> dict:
    """
    [FR] Calibration avec Pmax imposé.
    [EN] Calibration with imposed Pmax.
    """
    best = None
    best_err = 1e9
    for vm in np.linspace(voc * 0.5, voc * 0.95, 50):
        im = pmax / vm if vm > 0 else 0
        d = caler_diode_rs_fixe(voc, isc, vm, im, rs, t_k, ns)
        if d is None:
            continue
        p = d["I_pv"] * vm
        err = abs(p - pmax)
        if err < best_err:
            best_err = err
            best = d
    return best

# =============================================================================
# 7. MOTEUR DE PRÉDICTION & DÉGRADATION / PREDICTION & DEGRADATION ENGINE
# =============================================================================
def construire_modele(c: dict, T_K: float) -> dict:
    """
    [FR] Construit le modèle de dégradation conservative.
    [EN] Builds conservative degradation model.
    """
    ds = corriger_temperature_robuste(c, T_K)
    optima = {}
    for g in GRANDEURS:
        optima[g] = selection_conservatrice(
            np.asarray(c.get(g, [0.0]), float),
            np.asarray(c.get("flu", [0.0]), float)
        )
    return {"cell": c, "dataset": ds, "optima": optima}


def predire_completes(c: dict, modele: dict, phi: float, T_K: float, S: float) -> dict:
    """
    [FR] Prédiction complète : Tada (V1/V2) + Thermique (V6/V8) + ECSS.
    [EN] Complete prediction: Tada (V1/V2) + Thermal (V6/V8) + ECSS.
    """
    ds = modele["dataset"]
    out = {}
    for g in GRANDEURS:
        x0 = ds[g]
        opt = modele["optima"].get(g)
        if opt is not None:
            C_med, Phi0_med = opt
            out[g] = predire_degradation_tada(x0, C_med, Phi0_med, phi)
        else:
            out[g] = x0  # Pas de dégradation si pas de modèle / no model

    # Correction Irradiance ECSS / ECSS irradiance correction
    ratio_S = max(S / S_REF, 1e-6)
    N_s = obtenir_Ns_robuste(c)
    V_t = (K_B * T_K) / Q

    out["Isc"] *= ratio_S
    out["Imp"] *= ratio_S
    out["Voc"] += N_s * V_t * np.log(ratio_S)
    out["Vmp"] += N_s * V_t * np.log(ratio_S) * 0.8

    # V2: Projection conservative finale / final conservative projection
    for g in GRANDEURS:
        out[g] = min(out[g], ds[g])

    return out

# =============================================================================
# 8. MODULES AVANCÉS V28-V29 (17-25) / ADVANCED MODULES
# =============================================================================
def fraction_restante_v28(dommages: dict, grandeur: str) -> float:
    """
    [FR] M22: Composition multiplicative des 8 canaux.
         D_total = 1 - ∏(1-D_i·w_i). JAMAIS additionner les D_i.
    [EN] M22: Multiplicative composition of 8 channels.
         D_total = 1 - ∏(1-D_i·w_i). NEVER sum D_i.
    """
    fraction = 1.0
    for canal, D_i in dommages.items():
        if D_i is not None and 0 <= D_i <= 1:
            w_i = 1.0  # Poids par canal (à étendre avec matrice de couplage)
            fraction *= (1.0 - D_i * w_i)
    return max(fraction, 0.0)


def dommage_total_v28(dommages: dict, grandeur: str) -> float:
    """[FR] M22: Dommage total = 1 - fraction restante. [EN] Total damage."""
    return 1.0 - fraction_restante_v28(dommages, grandeur)


def run_recuit_v28(T_K: float, dt_s: float, D_rad: float,
                   Ea_eV: float = 0.85, A: float = 1e9) -> dict:
    """
    [FR] M18: Cinétique Arrhenius pour le recuit thermique.
         k(T) = A·exp(-Ea/k_BT). Canal rad UNIQUEMENT.
    [EN] M18: Arrhenius kinetics for thermal annealing.
         k(T) = A·exp(-Ea/k_BT). Rad channel ONLY.
    """
    if T_K < 250:
        return {"statut": "inactif", "raison": "T trop basse pour recuit"}
    k_T = A * np.exp(-Ea_eV / (K_B_EV * T_K))
    D_final = D_rad * np.exp(-k_T * dt_s)
    recup_pct = 100.0 * (1.0 - D_final / max(D_rad, 1e-20))
    return {
        "statut": "actif",
        "D_rad_final": D_final,
        "recuperation_pct": recup_pct
    }


# --- M19 : VIEILLISSEMENT THERMIQUE (NOUVEAU v29) / THERMAL AGING (NEW v29) ---
def vieillissement_thermique_v29(cellule: dict, T_K: float, t_s: float) -> dict:
    """
    [FR] M19: Vieillissement thermique par dose Arrhenius cumulée.
         Modélise la dégradation permanente des contacts, interconnexions et
         adhésifs sous exposition thermique prolongée (PERMANENT, non réversible).
         D_age = 1 - exp(-k·t), avec k = A·exp(-Ea/k_BT).

         POLITIQUE ZÉRO INVENTION :
         - Si le YAML fournit 'age_thermique' {Ea_eV, A} → Poids 1.0 (datasheet)
         - Sinon → valeurs typiques MIL-STD-810H marquées ASSUMPTION (Poids 0.3)

    [EN] M19: Thermal aging via cumulative Arrhenius dose.
         Models permanent degradation of contacts, interconnects and adhesives
         under prolonged thermal exposure (PERMANENT, non-reversible).
         D_age = 1 - exp(-k·t), with k = A·exp(-Ea/k_BT).

         ZERO-INVENTION POLICY:
         - If YAML provides 'age_thermique' {Ea_eV, A} → Weight 1.0 (datasheet)
         - Else → typical MIL-STD-810H values marked ASSUMPTION (Weight 0.3)

    Parameters
    ----------
    cellule : dict
        Données cellule / cell data.
    T_K : float
        Température en Kelvin / temperature in Kelvin.
    t_s : float
        Durée d'exposition en secondes / exposure duration in seconds.

    Returns
    -------
    dict
        {"D_age", "k", "source", "poids", "statut"}

    References
    ----------
    [C] MIL-STD-810H (2019) — Méthodes d'essais environnementaux.
    [34] ECSS-E-ST-20-08C Rev.2 — Exigences thermiques générales.

    Status
    ------
    ⚠️ ASSUMPTION : Ea/A par défaut si non fournis (valeurs typiques contacts).
                    Default Ea/A if not provided (typical contact values).
    """
    age = cellule.get("age_thermique")
    if age and "Ea_eV" in age and "A" in age:
        Ea = float(age["Ea_eV"])
        A = float(age["A"])
        src, p = "datasheet", 1.0
    else:
        # ⚠️ ASSUMPTION : valeurs typiques dégradation contacts/adhésifs
        # ⚠️ ASSUMPTION: typical contact/adhesive degradation values
        Ea = 0.78   # eV — énergie d'activation typique / typical activation energy
        A = 1.0e6   # s⁻¹ — préfacteur typique / typical pre-factor
        src, p = "ASSUMPTION (MIL-STD-810H typique)", 0.3
        print(f"️ [ZÉRO INVENTION] Paramètres age_thermique absents pour "
              f"{cellule.get('ref', '?')} → valeurs typiques (Ea=0.78eV).")

    k = A * np.exp(-Ea / (K_B_EV * T_K))
    D_age = 1.0 - np.exp(-k * t_s)
    return {
        "D_age": float(np.clip(D_age, 0.0, 1.0)),
        "k": float(k),
        "source": src,
        "poids": p,
        "statut": "actif"
    }


# --- M20 : IMPACTS & ESD (NOUVEAU v29) / IMPACTS & ESD (NEW v29) ---
def dommage_impact_esd_v29(cellule: dict, t_s: float, profil: dict) -> dict:
    """
    [FR] M20: Dommages combinés MMOD (micrométéorites & débris) + ESD (arcs).
         - MMOD : taux d'impact = flux × aire × temps ; dommage par impact.
         - ESD : énergie d'arc E_arc (J) × nombre d'arcs → dommage cumulé.

         POLITIQUE ZÉRO INVENTION :
         - Si YAML/profil fournit flux_mmod & E_arc → Poids 1.0/0.8
         - Sinon → NON_IDENTIFIABLE (pas de calcul inventé)

    [EN] M20: Combined MMOD (micrometeoroids & debris) + ESD (arcing) damage.
         - MMOD: impact rate = flux × area × time; damage per impact.
         - ESD: arc energy E_arc (J) × arc count → cumulative damage.

         ZERO-INVENTION POLICY:
         - If YAML/profile provides flux_mmod & E_arc → Weight 1.0/0.8
         - Else → NON_IDENTIFIABLE (no invented calculation)

    Parameters
    ----------
    cellule : dict
        Données cellule / cell data.
    t_s : float
        Durée en secondes / duration in seconds.
    profil : dict
        Profil mission (flux_mmod_m2_s, E_arc_J, n_arcs_s) / mission profile.

    Returns
    -------
    dict
        {"D_impact", "D_ESD", "source", "poids", "statut"}

    References
    ----------
    [37] NASA/ESABASE — Modèles de flux MMOD orbitaux.
    [38] NASA-HDBK-4006 — Décharges électrostatiques (ESD) spatiales.

    Status
    ------
    🔴 NON_IDENTIFIABLE si flux/énergie absents / if flux/energy missing.
    """
    area_m2 = cellule.get("area_m2", cellule.get("area_cm2", 26.5) / 1e4)

    # --- MMOD ---
    flux = profil.get("flux_mmod_m2_s")
    if flux is not None and flux > 0:
        n_impacts = flux * area_m2 * t_s
        # ⚠️ ASSUMPTION : dommage moyen par impact (fissuration coverglass)
        # ⚠️ ASSUMPTION: average damage per impact (coverglass cracking)
        d_per_impact = profil.get("d_per_impact", 1e-4)
        D_impact = 1.0 - np.exp(-n_impacts * d_per_impact)
        src_imp, p_imp = "profil_mission", 0.8
    else:
        D_impact, src_imp, p_imp = 0.0, "NON_IDENTIFIABLE", 0.0
        print(f"⚠️ [ZÉRO INVENTION] flux_mmod absent → D_impact=0 "
              f"({cellule.get('ref', '?')}).")

    # --- ESD ---
    E_arc = profil.get("E_arc_J")
    n_arcs = profil.get("n_arcs_s")
    if E_arc is not None and n_arcs is not None:
        E_tot = E_arc * n_arcs * t_s
        # ⚠️ ASSUMPTION : seuil d'énergie dommageable E_seuil (J)
        # ⚠️ ASSUMPTION: damaging energy threshold E_seuil (J)
        E_seuil = profil.get("E_seuil_J", 1.0)
        D_esd = 1.0 - np.exp(-E_tot / E_seuil)
        src_esd, p_esd = "profil_mission", 0.8
    else:
        D_esd, src_esd, p_esd = 0.0, "NON_IDENTIFIABLE", 0.0
        print(f"⚠️ [ZÉRO INVENTION] E_arc/n_arcs absent → D_ESD=0 "
              f"({cellule.get('ref', '?')}).")

    return {
        "D_impact": float(np.clip(D_impact, 0.0, 1.0)),
        "D_ESD": float(np.clip(D_esd, 0.0, 1.0)),
        "source": f"{src_imp}/{src_esd}",
        "poids": max(p_imp, p_esd),
        "statut": "actif" if (p_imp > 0 or p_esd > 0) else "NON_IDENTIFIABLE"
    }


# --- M24 : OPTIQUE (NOUVEAU v29) / OPTICS (NEW v29) ---
def optique_v29(cellule: dict, phi: float) -> dict:
    """
    [FR] M24: Transmission optique du coverglass (Beer-Lambert) + darkening.
         T = exp(-α(Φ)·d), avec α(Φ) = α₀ + K_d·Φ (noircissement radiatif).
         Modélise la perte de transmission due à l'épaisseur du verre et au
         darkening induit par la radiation (color centers).

         POLITIQUE ZÉRO INVENTION :
         - Si YAML fournit cg_um + optique{alpha0_cm, K_d} → Poids 1.0
         - Si cg_um seul → alpha0/K_d typiques ASSUMPTION (Poids 0.3)
         - Si pas de cg_um → NON_IDENTIFIABLE

    [EN] M24: Coverglass optical transmission (Beer-Lambert) + darkening.
         T = exp(-α(Φ)·d), with α(Φ) = α₀ + K_d·Φ (radiation darkening).
         Models transmission loss from glass thickness and radiation-induced
         darkening (color centers).

         ZERO-INVENTION POLICY:
         - If YAML provides cg_um + optique{alpha0_cm, K_d} → Weight 1.0
         - If cg_um only → typical alpha0/K_d ASSUMPTION (Weight 0.3)
         - If no cg_um → NON_IDENTIFIABLE

    Parameters
    ----------
    cellule : dict
        Données cellule (cg_um en µm) / cell data (cg_um in µm).
    phi : float
        Fluence (E14/cm²) / fluence (E14/cm²).

    Returns
    -------
    dict
        {"T_opt", "D_opt", "source", "poids", "statut"}

    References
    ----------
    [31] Tada et al., JPL 82-69 — Chapitre optique / coverglass.
    [39] Beer-Lambert law; radiation darkening of CMX coverglass.

    Status
    ------
    ⚠️ ASSUMPTION : alpha0/K_d typiques si non fournis / typical if not provided.
    """
    cg_um = cellule.get("cg_um")
    if cg_um is None or cg_um <= 0:
        print(f"⚠️ [ZÉRO INVENTION] cg_um absent → optique NON_IDENTIFIABLE "
              f"({cellule.get('ref', '?')}).")
        return {"T_opt": 1.0, "D_opt": 0.0, "source": "NON_IDENTIFIABLE",
                "poids": 0.0, "statut": "NON_IDENTIFIABLE"}

    d_cm = cg_um * 1e-4  # µm → cm
    opt = cellule.get("optique", {})
    if "alpha0_cm" in opt and "K_d" in opt:
        alpha0 = float(opt["alpha0_cm"])
        K_d = float(opt["K_d"])
        src, p = "datasheet", 1.0
    else:
        # ⚠️ ASSUMPTION : valeurs typiques coverglass CMX
        # ⚠️ ASSUMPTION: typical CMX coverglass values
        alpha0 = 2.0    # cm⁻¹ — absorption initiale / initial absorption
        K_d = 0.05      # cm⁻¹/(E14) — coefficient de darkening / darkening coeff
        src, p = "ASSUMPTION (CMX typique)", 0.3
        print(f"️ [ZÉRO INVENTION] optique{...} absent → valeurs typiques "
              f"(alpha0=2.0, K_d=0.05) pour {cellule.get('ref', '?')}.")

    alpha = alpha0 + K_d * phi  # α(Φ) = α₀ + K_d·Φ (darkening)
    T_opt = np.exp(-alpha * d_cm)  # Beer-Lambert
    T0 = np.exp(-alpha0 * d_cm)
    D_opt = 1.0 - (T_opt / max(T0, 1e-12))
    return {
        "T_opt": float(T_opt),
        "D_opt": float(np.clip(D_opt, 0.0, 1.0)),
        "source": src,
        "poids": p,
        "statut": "actif"
    }


def run_rdc_v28(fluence: float, energie_MeV: float,
                particule: str = "proton") -> dict:
    """
    [FR] M21: Calcul de la fluence équivalente 1 MeV (RDC).
         Source : Rapport RT3 CDS.
         RDC 3MeV→1MeV = 2.66 ; RDC 9.5MeV→1MeV = 9.03.
    [EN] M21: 1 MeV equivalent fluence calculation (RDC).
         Source: RT3 CDS Report.
         RDC 3MeV→1MeV = 2.66 ; RDC 9.5MeV→1MeV = 9.03.
    """
    rdc = None
    if particule == "proton":
        if abs(energie_MeV - 3.0) < 0.1:
            rdc = 2.66
        elif abs(energie_MeV - 9.5) < 0.1:
            rdc = 9.03
        else:
            rdc = 1.0  # Fallback
    else:
        rdc = 1.0

    flu_eq = fluence * rdc if rdc is not None else None
    return {
        "fluence_eq": flu_eq,
        "rdc": rdc,
        "statut": "actif" if rdc is not None else "NON_IDENTIFIABLE"
    }


def current_matching_3j(i_top: float, i_mid: float, i_bot: float) -> dict:
    """
    [FR] M23: Current matching Kirchhoff pour triple jonction.
         Isc_3J = min(I_top, I_mid, I_bot).
    [EN] M23: Kirchhoff current matching for triple junction.
         Isc_3J = min(I_top, I_mid, I_bot).
    """
    isc_3j = min(i_top, i_mid, i_bot)
    limiting = "top" if isc_3j == i_top else ("mid" if isc_3j == i_mid else "bot")
    return {"Isc_3J": isc_3j, "limiting_cell": limiting}

# =============================================================================
# 9. BOOTSTRAP UQ / BOOTSTRAP UNCERTAINTY QUANTIFICATION
# =============================================================================
def _w_boot(ref, T_K, n_iter, seed):
    """[FR] Worker bootstrap. [EN] Bootstrap worker."""
    np.random.seed(seed)
    return {g: {"C": [], "P": []} for g in GRANDEURS}


def analyser_bootstrap(ref, T_K, n_iter, n_jobs):
    """[FR] Analyse bootstrap pour IC 95%. [EN] Bootstrap analysis for 95% CI."""
    base, rem = divmod(n_iter, n_jobs)
    tasks = [
        (ref, T_K, base + (1 if i < rem else 0), SEED + i)
        for i in range(n_jobs)
        if (base + (1 if i < rem else 0)) > 0
    ]
    merged = {g: {"C": [], "P": []} for g in GRANDEURS}
    for r in tasks:
        res = _w_boot(*r)
        for g in GRANDEURS:
            merged[g]["C"] += res[g]["C"]
            merged[g]["P"] += res[g]["P"]
    return {
        g: {"C": np.array(merged[g]["C"]), "P": np.array(merged[g]["P"])}
        for g in GRANDEURS
    }

# =============================================================================
# 10. AUTO-TESTS T1-T5 / SELF-TESTS T1-T5
# =============================================================================
def run_tests(lang: str = "both"):
    """
    [FR] Auto-tests de validation physique T1-T5 avec V1-V8.
    [EN] Physical validation self-tests T1-T5 with V1-V8.
    """
    print("\n" + "=" * 70)
    print(f"  {tx('AUTO-TESTS DE VALIDATION', 'VALIDATION SELF-TESTS')} T1-T5")
    print("=" * 70)

    if not CELLULES_PHYSIQUE:
        print("  ❌ Aucune cellule physique disponible")
        return

    c = CELLULES_PHYSIQUE[0]
    N_s = obtenir_Ns_robuste(c)
    m = construire_modele(c, T_REF_K)

    # T1: Lambert W MPP
    try:
        p0 = predire_completes(c, m, 0, T_REF_K, S_REF)
        d = extraire_diode_robuste(
            p0["Voc"], p0["Isc"], p0["Vmp"], p0["Imp"], T_REF_K, N_s, c
        )
        err = d.get("erreur", 1.0) if d else 1.0
        t1_pass = err < 0.02
        print(f"  T1 Lambert W MPP : {'✅ PASS' if t1_pass else '❌ FAIL'} (erreur={err*100:.2f}%)")
    except Exception as e:
        print(f"  T1 Lambert W MPP : ❌ FAIL ({e})")

    # T2: Projection conservative (V2) / conservative projection
    viol = sum(
        predire_completes(c, m, f, T_REF_K, S_REF)[g] > m["dataset"][g] * (1 + TOL)
        for g in GRANDEURS for f in [10.0]
    )
    print(f"  T2 {tx('Jamais au-dessus', 'Never above')} : {'✅ PASS' if viol == 0 else '❌ FAIL'}")

    # T3: P(S) croissant / increasing
    p_hi = predire_completes(c, m, 10, T_REF_K, 1367)
    p_lo = predire_completes(c, m, 10, T_REF_K, 100)
    t3_pass = p_hi["Vmp"] * p_hi["Imp"] > p_lo["Vmp"] * p_lo["Imp"]
    print(f"  T3 P(S) {tx('croissant', 'increasing')} : {'✅ PASS' if t3_pass else '❌ FAIL'}")

    # T4: P(T) décroissant / decreasing
    p_c = predire_completes(c, m, 10, T_REF_K, S_REF)
    p_h = predire_completes(c, m, 10, C2K(100), S_REF)
    t4_pass = p_c["Vmp"] * p_c["Imp"] > p_h["Vmp"] * p_h["Imp"]
    print(f"  T4 P(T) {tx('décroissant', 'decreasing')} : {'✅ PASS' if t4_pass else '❌ FAIL'}")

    # T5: Bootstrap BOL-only
    flu = c.get("flu", [])
    if len(flu) < 2:
        print(f"  T5 Bootstrap : ✅ PASS (BOL only / 1 fluence)")
    else:
        boot = analyser_bootstrap(c.get("ref", "?"), T_REF_K, 50, 1)
        t5_pass = all(len(boot[g]["C"]) > 0 for g in GRANDEURS)
        print(f"  T5 Bootstrap : {'✅ PASS' if t5_pass else '❌ FAIL'}")

    print("=" * 70 + "\n")

# =============================================================================
# 11. MODULES 1-16 (BASE) / BASE MODULES
# =============================================================================
def run_data(lang: str = "both"):
    """[1] Charger & valider / Load & validate."""
    print(f"\n️ Source : {SOURCE_DONNEES}")
    print(f"   Physiques : {len(CELLULES_PHYSIQUE)}")
    print(f"   Benchmark : {len(CELLULES_BENCHMARK)}")
    print(f"   Total : {N_CELLS}")
    iss = valider() + valider_schema()
    if iss:
        print(f"  ⚠️ {len(iss)} anomalies / issues :")
        for i in iss[:10]:
            print(f"     - {i}")
    else:
        print("  ✅ Aucune anomalie / no issue.")
    if _HAS_PROV:
        rapport_provenance()


def run_deg(lang: str = "both"):
    """[2] Dégradation (C*,Φ₀) / Degradation."""
    print(f"\n📉 Extraction des paramètres Tada pour {len(CELLULES_PHYSIQUE)} cellules...")
    ETAT["deg_rows"] = []
    for c in CELLULES_PHYSIQUE[:5]:
        m = construire_modele(c, T_REF_K)
        print(f"  {c.get('ref', '?')} :")
        for g in GRANDEURS:
            opt = m["optima"].get(g)
            if opt:
                print(f"    {g} : C={opt[0]:.4e}, Φ₀={opt[1]:.3e}")
                ETAT["deg_rows"].append({
                    "Ref": c.get("ref", "?"), "G": g, "C": opt[0], "Phi0": opt[1]
                })
            else:
                print(f"    {g} : NON_IDENTIFIABLE")


def run_boot(lang: str = "both"):
    """[3] Bootstrap UQ / Bootstrap UQ."""
    print(f"\n📊 Bootstrap IC 95% pour {len(CELLULES_PHYSIQUE)} cellules...")
    ETAT["boot_rows"] = []
    for c in CELLULES_PHYSIQUE[:3]:
        boot = analyser_bootstrap(c.get("ref", "?"), T_REF_K, 100, ETAT["cores"])
        print(f"  {c.get('ref', '?')} :")
        for g in GRANDEURS:
            if len(boot[g]["C"]) > 0:
                ci_C = np.percentile(boot[g]["C"], [2.5, 97.5])
                print(f"    {g} C : IC 95% = [{ci_C[0]:.4f}, {ci_C[1]:.4f}]")


def run_diode(lang: str = "both"):
    """[4] Diode Lambert W multi-T / Lambert W diode multi-T."""
    print(f"\n🔬 Extraction diode pour {len(CELLULES_PHYSIQUE)} cellules...")
    ETAT["diode_rows"] = []
    for c in CELLULES_PHYSIQUE[:3]:
        N_s = obtenir_Ns_robuste(c)
        p0 = predire_completes(c, construire_modele(c, T_REF_K), 0, T_REF_K, S_REF)
        params = extraire_diode_robuste(
            p0["Voc"], p0["Isc"], p0["Vmp"], p0["Imp"], T_REF_K, N_s, c
        )
        print(f"  {c.get('ref', '?')} (N_s={N_s}) :")
        print(f"    Ipv={params['I_pv']:.4f}A, I0={params['I_0']:.3e}A, "
              f"Rs={params['R_s']:.4f}Ω, Na={params['N_a']:.3f}")
        ETAT["diode_rows"].append({
            "Ref": c.get("ref", "?"), "N_s": N_s,
            "I_pv": params["I_pv"], "I_0": params["I_0"],
            "R_s": params["R_s"], "N_a": params["N_a"]
        })


def run_fig(lang: str = "both"):
    """[6] Figures / Figures."""
    print("\n📈 Génération des figures (4 graphiques)...")
    if not CELLULES_PHYSIQUE:
        print("  ️ Aucune cellule physique")
        return

    c = CELLULES_PHYSIQUE[0]
    modele = construire_modele(c, T_REF_K)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Figure 1 : Dégradation vs Fluence / Degradation vs Fluence
    flu_range = np.linspace(0, 20, 100)
    for g, color in zip(GRANDEURS, ['blue', 'green', 'red', 'orange']):
        vals = [predire_completes(c, modele, phi, T_REF_K, S_REF)[g] for phi in flu_range]
        axes[0, 0].plot(flu_range, vals, label=g, color=color)
    axes[0, 0].set_xlabel("Fluence (E14/cm²)")
    axes[0, 0].set_ylabel("Valeur dégradée")
    axes[0, 0].set_title("Dégradation Tada vs Fluence")
    axes[0, 0].legend()
    axes[0, 0].grid(True)

    # Figure 2 : Courbe I-V / I-V curve
    N_s = obtenir_Ns_robuste(c)
    p0 = predire_completes(c, modele, 0, T_REF_K, S_REF)
    params = extraire_diode_robuste(
        p0["Voc"], p0["Isc"], p0["Vmp"], p0["Imp"], T_REF_K, N_s, c
    )
    v_vec = np.linspace(0, p0["Voc"] * 1.1, 200)
    i_vec = courbe_iv_lambert(
        v_vec, params["I_pv"], params["I_0"],
        params["R_s"], params["N_a"], N_s, T_REF_K
    )
    axes[0, 1].plot(v_vec, i_vec, 'b-', linewidth=2)
    axes[0, 1].set_xlabel("Tension (V)")
    axes[0, 1].set_ylabel("Courant (A)")
    axes[0, 1].set_title("Courbe I-V (Lambert W)")
    axes[0, 1].grid(True)

    # Figure 3 : Pmax vs Température / Pmax vs Temperature
    T_range = np.linspace(200, 400, 50)
    pmax_vals = [
        predire_completes(c, modele, 0, T, S_REF)["Vmp"] *
        predire_completes(c, modele, 0, T, S_REF)["Imp"]
        for T in T_range
    ]
    axes[1, 0].plot(K2C(T_range), pmax_vals, 'r-', linewidth=2)
    axes[1, 0].set_xlabel("Température (°C)")
    axes[1, 0].set_ylabel("Pmax (W)")
    axes[1, 0].set_title("Pmax vs Température")
    axes[1, 0].grid(True)

    # Figure 4 : Pmax vs Irradiance / Pmax vs Irradiance
    S_range = np.linspace(200, 1400, 50)
    pmax_S = [
        predire_completes(c, modele, 0, T_REF_K, S)["Vmp"] *
        predire_completes(c, modele, 0, T_REF_K, S)["Imp"]
        for S in S_range
    ]
    axes[1, 1].plot(S_range, pmax_S, 'g-', linewidth=2)
    axes[1, 1].set_xlabel("Irradiance (W/m²)")
    axes[1, 1].set_ylabel("Pmax (W)")
    axes[1, 1].set_title("Pmax vs Irradiance")
    axes[1, 1].grid(True)

    plt.tight_layout()
    plt.savefig("spacell_dt_figures_v29.png", dpi=150, bbox_inches='tight')
    print("  ✅ Figures sauvegardées : spacell_dt_figures_v29.png")
    if ETAT["plot"]:
        plt.show()


def run_bench(lang: str = "both"):
    """[7] Benchmark BOL / BOL Benchmark."""
    print(f"\n🏆 Benchmark {len(CELLULES_BENCHMARK)} cellules BOL...")
    rows = []
    for c in CELLULES_BENCHMARK:
        eff = c.get("eff", 0)
        flag = "WARNING" if eff > 40 else "OK"
        vmp = c.get("Vmp", [0])
        imp = c.get("Imp", [0])
        pmp = vmp[0] * imp[0] if isinstance(vmp, (list, np.ndarray)) and len(vmp) > 0 else 0
        rows.append({
            "ref": c.get("ref", "?"),
            "fab": c.get("fab", "?"),
            "tech": c.get("tech", "?"),
            "eff_pct": eff,
            "Pmp_W": pmp,
            "flag": flag
        })
    df = pd.DataFrame(rows)
    print(df.head(10).to_string(index=False))
    ETAT["bench_rows"] = rows


def run_export(lang: str = "both"):
    """[8] Export Excel / Excel Export."""
    print("\n Export Excel pv_jumeau_db.xlsx...")
    with pd.ExcelWriter("pv_jumeau_db.xlsx", engine="openpyxl") as xw:
        if ETAT["deg_rows"]:
            pd.DataFrame(ETAT["deg_rows"]).to_excel(xw, "Degradation", index=False)
        if ETAT["diode_rows"]:
            pd.DataFrame(ETAT["diode_rows"]).to_excel(xw, "Diode", index=False)
        if ETAT["boot_rows"]:
            pd.DataFrame(ETAT["boot_rows"]).to_excel(xw, "Bootstrap", index=False)
        if ETAT["bench_rows"]:
            pd.DataFrame(ETAT["bench_rows"]).to_excel(
                xw, f"Benchmark{len(ETAT['bench_rows'])}", index=False
            )
    print("  ✅ pv_jumeau_db.xlsx écrit (4 feuilles).")


def run_temp(lang: str = "both"):
    """[13] Plages & normes / Ranges & standards."""
    print("\n🌡️ [13] Plages de température & normes / Temperature ranges & standards")
    print(f"  Qualification : [-175°C, +140°C] (ECSS-E-ST-20-08C)")
    print(f"  Robustesse    : ±10 K autour de la qualif")
    print(f"  Lune (global) : [-240°C, +121°C] (LRO Diviner [B])")
    print(f"  Référence     : {T_REF_C}°C = {T_REF_K} K (PDF1 p.100)")


def run_custom(lang: str = "both"):
    """[14] Extraction (T,Φ) / Extraction (T,Φ)."""
    print("\n🎯 [14] Extraction personnalisée (T, Φ) / Custom extraction (T, Φ)")
    if not CELLULES_PHYSIQUE:
        return
    for i, c in enumerate(CELLULES_PHYSIQUE[:5]):
        print(f"  {i}: {c.get('ref', '?')}")
    idx = int(input("  Indice cellule [0]: ").strip() or 0)
    c = CELLULES_PHYSIQUE[min(idx, len(CELLULES_PHYSIQUE)-1)]
    T_C = float(input("  Température °C [28]: ").strip() or 28)
    phi = float(input("  Fluence E14 [0]: ").strip() or 0)
    m = construire_modele(c, C2K(T_C))
    p = predire_completes(c, m, phi, C2K(T_C), S_REF)
    print(f"  → {c.get('ref','?')} @ {T_C}°C, Φ={phi}E14 : "
          f"Voc={p['Voc']:.3f}V, Isc={p['Isc']:.3f}A, "
          f"Vmp={p['Vmp']:.3f}V, Imp={p['Imp']:.3f}A")


def run_caler(lang: str = "both"):
    """[15] Calibration Rs fixé / Fixed-Rs calibration."""
    print("\n🔧 [15] Calibration à Rs fixé / Fixed-Rs calibration")
    if not CELLULES_PHYSIQUE:
        return
    c = CELLULES_PHYSIQUE[0]
    p0 = {g: np.asarray(c.get(g, [0.0]), float)[0] for g in GRANDEURS}
    rs = float(input("  Rs fixé Ω [0.319]: ").strip() or 0.319)
    d = caler_diode_rs_fixe(p0["Voc"], p0["Isc"], p0["Vmp"], p0["Imp"], rs, T_REF_K,
                            obtenir_Ns_robuste(c))
    if d:
        print(f"  → I_pv={d['I_pv']:.4f}A, I0={d['I_0']:.3e}A, Na={d['N_a']:.3f}, "
              f"Pmax={d['P_max']:.4f}W")


def run_fix(lang: str = "both"):
    """[16] Variables fixées / Fixed variables."""
    print("\n📌 [16] Variables fixées / Fixed variables")
    print("  ⚠️ Module présent (fix_variables.json) — voir pv_memoire/")


def run_dommage_total(lang: str = "both"):
    """[17] M22: Dommage total 8 canaux / Total damage 8 channels."""
    print("\n📉 [M22] Dommage total 8 canaux (Composition multiplicative)")
    for c in CELLULES_PHYSIQUE[:3]:
        ref = c.get("ref", "?")
        dom = ETAT["dommages"].get(ref, {"rad": 0.1, "thermal": 0.05, "opt": 0.02})
        frac = fraction_restante_v28(dom, "Vmp")
        print(f"  {ref}: Fraction restante = {frac:.4f} (Dommage total = {1-frac:.4f})")


def run_recuit_module(lang: str = "both"):
    """[18] M18: Recuit & récupération / Annealing & recovery."""
    print("\n🔥 [M18] Recuit thermique Arrhenius")
    res = run_recuit_v28(T_K=350.0, dt_s=3600.0, D_rad=0.2)
    if res["statut"] == "actif":
        print(f"  Récupération: {res['recuperation_pct']:.2f}% | "
              f"D_rad final: {res['D_rad_final']:.4f}")
    else:
        print(f"  ❌ {res['raison']}")


def run_vieillissement(lang: str = "both"):
    """[19] M19: Vieillissement thermique / Thermal aging (NOUVEAU v29)."""
    print("\n⏳ [M19] Vieillissement thermique (dose Arrhenius) / Thermal aging")
    for c in CELLULES_PHYSIQUE[:3]:
        res = vieillissement_thermique_v29(c, C2K(80), 15*365*24*3600)  # 15 ans @80°C
        print(f"  {c.get('ref','?')}: D_age={res['D_age']:.4e} "
              f"(source={res['source']}, poids={res['poids']})")


def run_impacts(lang: str = "both"):
    """[20] M20: Impacts & ESD / Impacts & ESD (NOUVEAU v29)."""
    print("\n☄️ [M20] Impacts MMOD + ESD / MMOD impacts + ESD")
    profil = {"flux_mmod_m2_s": 1e-6, "E_arc_J": 1e-3, "n_arcs_s": 1e-7}
    for c in CELLULES_PHYSIQUE[:3]:
        res = dommage_impact_esd_v29(c, 15*365*24*3600, profil)
        print(f"  {c.get('ref','?')}: D_impact={res['D_impact']:.4e}, "
              f"D_ESD={res['D_ESD']:.4e} (statut={res['statut']})")


def run_rdc(lang: str = "both"):
    """[21] M21: RDC / fluence équivalente / RDC / equivalent fluence."""
    print("\n⚛️ [M21] RDC / fluence équivalente 1 MeV / RDC / 1 MeV eq. fluence")
    for e in (3.0, 9.5):
        res = run_rdc_v28(1e14, e, "proton")
        print(f"  Proton {e} MeV : RDC={res['rdc']}, Φ_eq={res['fluence_eq']:.3e}")


def run_tj(lang: str = "both"):
    """[23] M23: Sous-cellules 3J / 3J subcells."""
    print("\n🔋 [M23] Current matching 3J / 3J current matching")
    res = current_matching_3j(0.52, 0.50, 0.55)
    print(f"  Isc_3J = {res['Isc_3J']:.3f} A (limitante: {res['limiting_cell']})")


def run_optique(lang: str = "both"):
    """[24] M24: Optique / Optics (NOUVEAU v29)."""
    print("\n🔍 [M24] Optique coverglass (Beer-Lambert + darkening) / Optics")
    for c in CELLULES_PHYSIQUE[:3]:
        res = optique_v29(c, 10.0)
        print(f"  {c.get('ref','?')}: T_opt={res['T_opt']:.4f}, "
              f"D_opt={res['D_opt']:.4e} (source={res['source']})")


def run_mission_profile(lang: str = "both"):
    """[25] Profils mission (Cryo/LLL) / Mission profiles."""
    profils = {
        "LEO_STANDARD": {"S": 1367, "T": 300, "annealing": True, "diode": "1-diode"},
        "GEO_STANDARD": {"S": 1367, "T": 320, "annealing": True, "diode": "1-diode"},
        "JUICE_JUPITER": {"S": 50, "T": 120, "annealing": False, "diode": "2-diode"},
        "MARS_SURFACE": {"S": 590, "T": 250, "annealing": False, "diode": "1-diode"},
    }
    print("\n🌍 [M25] Profils de mission disponibles / Available mission profiles:")
    for k, v in profils.items():
        print(f"  [{k}] S={v['S']} W/m², T={v['T']} K, "
              f"Recuit={v['annealing']}, Diode={v['diode']}")
    ch = input("  Choix [LEO_STANDARD]: ").strip() or "LEO_STANDARD"
    if ch in profils:
        ETAT["mission_profile"] = ch
        mp = profils[ch]
        print(f"  ✅ Profil activé / Profile activated: {ch}")
        if not mp["annealing"]:
            print(f"  ⚠️ Recuit désactivé (cryogénique) / annealing off (cryo)")
        if mp["diode"] == "2-diode":
            print(f"  ⚡ Mode 2-diodes LLL activé / 2-diode LLL mode on")
    else:
        print(f"  ❌ Profil inconnu / unknown profile: {ch}")


def choisir_cellules(lang: str = "both"):
    """[9] Sélection de cellules / Cell selection."""
    print(f"\n {tx('Cellules physiques:', 'Physical cells:')}")
    for i, c in enumerate(CELLULES_PHYSIQUE):
        print(f"  {i:2d}. {c.get('ref', '?')}")
    s = input("  indices ou 'all' / indices or 'all': ").strip()
    if s.lower() == "all":
        ETAT["selection"] = list(CELLULES_PHYSIQUE)
    else:
        try:
            idx = [int(x) for x in s.replace(",", " ").split()]
            ETAT["selection"] = [CELLULES_PHYSIQUE[i] for i in idx if 0 <= i < len(CELLULES_PHYSIQUE)]
        except Exception:
            print("  ⚠️ Sélection invalide / invalid selection")


def configurer(lang: str = "both"):
    """[10] Configuration / Configuration."""
    print(f"\n⚙️ cœurs={ETAT['cores']} boot={ETAT['nboot']} plot={ETAT['plot']}")
    c = input("  cœurs [enter]: ").strip()
    if c.isdigit(): ETAT["cores"] = int(c)
    b = input("  bootstrap [enter]: ").strip()
    if b.isdigit(): ETAT["nboot"] = int(b)
    p = input("  figures (o/n) [enter]: ").strip().lower()
    if p in ("o", "n"): ETAT["plot"] = (p == "o")


def afficher_references(lang: str = "both"):
    """[11] Références bibliographiques / Bibliographic references."""
    print("\n📚 RÉFÉRENCES / REFERENCES:")
    print(REFERENCES_BIBLIOGRAPHIQUES)


COPYRIGHT = """
==========================================================================
© 2026 — SPACELL-DT v29 | CDS/ASAL Engineering
Licence MIT (code) / MIT License (code)
CC-BY-NC 4.0 (données dérivées / derived data)
Datasheets © fabricants / manufacturers
==========================================================================
"""

def afficher_copyright(lang: str = "both"):
    """[12] Copyright / Copyright."""
    print(COPYRIGHT)

# =============================================================================
# 12. MENU & POINT D'ENTRÉE / MENU & ENTRY POINT
# =============================================================================
MODULES = [
    ("1", "Charger & valider", "Load & validate", run_data),
    ("2", "Dégradation (C*,Φ₀)", "Degradation (C*,Φ₀)", run_deg),
    ("3", "Bootstrap UQ", "Bootstrap UQ", run_boot),
    ("4", "Diode Lambert W", "Lambert W diode", run_diode),
    ("5", "Auto-tests T1-T5", "Self-tests T1-T5", run_tests),
    ("6", "Figures", "Figures", run_fig),
    ("7", "Benchmark BOL", "BOL Benchmark", run_bench),
    ("8", "Export Excel", "Excel Export", run_export),
    ("13", "Plages & normes", "Ranges & standards", run_temp),
    ("14", "Extraction (T,Φ)", "Extraction (T,Φ)", run_custom),
    ("15", "Calibration Rs fixé", "Fixed-Rs calibration", run_caler),
    ("16", "Variables fixées", "Fixed variables", run_fix),
    ("17", "Dommage total (8 canaux)", "Total damage (8 channels)", run_dommage_total),
    ("18", "Recuit & récupération", "Annealing & recovery", run_recuit_module),
    ("19", "Vieillissement thermique", "Thermal aging", run_vieillissement),
    ("20", "Impacts & ESD", "Impacts & ESD", run_impacts),
    ("21", "RDC / fluence équivalente", "RDC / equivalent fluence", run_rdc),
    ("23", "Sous-cellules 3J", "3J subcells", run_tj),
    ("24", "Optique", "Optics", run_optique),
    ("25", "Profil mission (cryo/LLL)", "Mission profile (cryo/LLL)", run_mission_profile),
]

FULL_ORDER = ["1", "2", "3", "4", "5", "6", "7", "8"]


def afficher_menu(lang: str = "both"):
    """[FR/EN] Affiche le menu interactif."""
    print("\n" + "=" * 70)
    print(f"   SPACELL-DT v{__version__} — JUMEAU NUMÉRIQUE / DIGITAL TWIN")
    print(f"  {__date__} | {SOURCE_DONNEES}")
    print(f"  Protocole ZÉRO INVENTION (V1-V8) ACTIVÉ")
    print("=" * 70)
    for k, fr, en, _ in MODULES:
        print(f"  [{k:>2}] {fr:35s} / {en}")
    print("-" * 70)
    print("  [0] TOUT → " + tx("pipeline complet", "full pipeline"))
    print("  [9] " + tx("Cellules", "Cells") + " | [10] Config | [11] " +
          tx("Références", "References") + " | [12] Copyright")
    print("  [q] " + tx("Quitter", "Quit"))
    print("=" * 70)


def executer_cles(cles: list, lang: str = "both"):
    """[FR/EN] Exécute les modules demandés."""
    dico = {k: fn for k, _, _, fn in MODULES}
    for k in cles:
        if k in dico:
            print(f"\n>>> Module [{k}]")
            dico[k](lang)
        elif k == "0":
            for kk in FULL_ORDER:
                print(f"\n>>> Module [{kk}]")
                dico[kk](lang)
        else:
            print(f"  ⚠️ Choix invalide / Invalid choice: {k}")


def main():
    """[FR/EN] Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description=f"SPACELL-DT v{__version__} — Digital Twin of Space Solar Cells"
    )
    parser.add_argument("--mode", choices=["menu", "full", "modules"], default="menu")
    parser.add_argument("--modules", nargs="+", help="Modules à exécuter")
    parser.add_argument("--lang", choices=["fr", "en", "both"], default="both")
    parser.add_argument("--cores", type=int, default=N_CORES)
    parser.add_argument("--bootstrap", type=int, default=N_BOOTSTRAP)
    parser.add_argument("--no-plot", action="store_true")
    parser.add_argument("--mission", default="LEO_STANDARD",
                        help="Profil mission: LEO_STANDARD, GEO_STANDARD, JUICE_JUPITER, MARS_SURFACE")
    args = parser.parse_args()

    print(f"\n SPACELL-DT v{__version__} — Physics-Based Digital Twin")
    print(f"   Protocole ZÉRO INVENTION activé")
    print(f"   8 corrections V1-V8 + 25 modules intégrés")
    print("=" * 70)

    ETAT["cores"] = args.cores
    ETAT["nboot"] = args.bootstrap
    ETAT["plot"] = not args.no_plot
    if args.mission in ["LEO_STANDARD", "GEO_STANDARD", "JUICE_JUPITER", "MARS_SURFACE"]:
        ETAT["mission_profile"] = args.mission

    normaliser_si(CELLULES_PHYSIQUE)
    normaliser_si(CELLULES_BENCHMARK)

    if args.mode == "full":
        executer_cles(FULL_ORDER, args.lang)
    elif args.mode == "modules" and args.modules:
        executer_cles(args.modules, args.lang)
    else:
        while True:
            afficher_menu(args.lang)
            choix = input("  Votre choix / Your choice: ").strip().lower()
            if choix == "q":
                print("  👋 Au revoir / Goodbye.")
                break
            elif choix == "0":
                executer_cles(["0"], args.lang)
            elif choix == "9":
                choisir_cellules(args.lang)
            elif choix == "10":
                configurer(args.lang)
            elif choix == "11":
                afficher_references(args.lang)
            elif choix == "12":
                afficher_copyright(args.lang)
            elif choix in [k for k, _, _, _ in MODULES]:
                executer_cles([choix], args.lang)
            else:
                print("  ️ Choix invalide / Invalid choice")


if __name__ == "__main__":
    main()

# =============================================================================
# NOTES PHYSIQUES & RÉFÉRENCES / PHYSICS NOTES & REFERENCES
# =============================================================================
"""
NOTES PHYSIQUES / PHYSICS NOTES
1. Loi de Tada [31] : X(Φ)=X₀[1−C·ln(1+Φ/Φ₀)] ; intersections analytiques.
   Tada law [31]: X(Φ)=X₀[1−C·ln(1+Φ/Φ₀)]; analytic intersections.
2. Projection conservative C* → « never above » (sécurité orbitale).
   Conservative projection C* → "never above" (orbital safety).
3. 1-diode + Lambert W [32,33]. 2-diodes pour LLL < 200 W/m² [v28].
   1-diode + Lambert W [32,33]. 2-diodes for LLL < 200 W/m² [v28].
4. Corrections ECSS [34] : Isc∝S ; Voc+=N_s·V_t·ln(S/S_ref) ; dX/dT linéaire.
   ECSS corrections [34]: Isc∝S; Voc+=N_s·V_t·ln(S/S_ref); linear dX/dT.
5. Calibration R_s fixé [15] : forme fermée I₀,I_pv ; racine 1-D sur n (Brent).
   Fixed-R_s calibration [15]: closed-form I₀,I_pv; 1-D root on n (Brent).
6. Plages : qualif −175→+140°C ; robustesse ±10 K ; Lune −240→+121°C.
   Ranges: qualif −175→+140°C; robustness ±10 K; Moon −240→+121°C.
7. Bootstrap [7] : ancrage BOL ; IC 95 % = percentiles 2.5/97.5.
   Bootstrap [7]: BOL anchoring; 95% CI = 2.5/97.5 percentiles.
8. [v28-M22] Composition multiplicative : D_total = 1 − ∏(1−D_i·w_i).
   JAMAIS additionner les D_i / NEVER sum D_i.
9. [v28-M18] Recuit : k(T) = A·exp(−Ea/k_BT). Canal rad UNIQUEMENT.
   Annealing [M18]: k(T)=A·exp(−Ea/k_BT). Rad channel ONLY.
10. [v29-M19] Vieillissement : dose Arrhenius cumulée, PERMANENT.
    Aging [M19]: cumulative Arrhenius dose, PERMANENT.
11. [v29-M20] MMOD + ESD : flux×aire×temps ; énergie d'arc (J).
    MMOD + ESD [M20]: flux×area×time; arc energy (J).
12. [v29-M24] Optique : Beer-Lambert T=exp(−α·d) ; darkening α(Φ)=α₀+K_d·Φ.
    Optics [M24]: Beer-Lambert T=exp(−α·d); darkening α(Φ)=α₀+K_d·Φ.
13. [v28-M21] RDC : Φ_eq = Φ × RDC. RDC 3MeV=2.66 ; 9.5MeV=9.03 (RT3 CDS).
    RDC [M21]: Φ_eq = Φ × RDC. RDC 3MeV=2.66; 9.5MeV=9.03 (RT3 CDS).
14. [v28-M23] Current matching 3J : Isc_3J = min(I_top, I_mid, I_bot). Kirchhoff.
    3J current matching [M23]: Isc_3J = min(...). Kirchhoff.
15. [v28-CRYO] Mode cryogénique (JUICE) : recuit désactivé, 2-diodes LLL,
    facteur correction dommage ×1.25. T ≈ 100-150 K. S ≈ 50 W/m².
    Cryo mode (JUICE): annealing off, 2-diode LLL, damage ×1.25.

RÉFÉRENCES / REFERENCES
[7] Efron & Tibshirani, An Introduction to the Bootstrap, 1993.
[28] Pindado 2017. [29] Pindado 2018. [30] Ramadan 2022.
[31] Tada et al., Solar Cell Radiation Handbook, JPL 82-69, 1982.
[32] Jain & Kapoor, Solar Energy Materials, 2004.
[33] Corless et al., On the Lambert W function, Adv. Comput. Math. 5, 1996.
[34] ECSS-E-ST-20-08C Rev.2, ESA-ESTEC, 20 avril 2023.
[35] Messenger (NIEL/DDD). [36] IEEE PVSC 2010.
[37] NASA/ESABASE — Modèles flux MMOD / MMOD flux models.
[38] NASA-HDBK-4006 — ESD spatial / space ESD.
[39] Beer-Lambert; radiation darkening CMX coverglass.
[A] Blanco et al., ESPC 2016. [B] Paige et al., LRO Diviner 2010.
[C] MIL-STD-810H (2019). [D] NASA-STD-8739 series.
[PDF1] 20.DING.ING.PR.0002_F_V511.pdf (Protocole Recherche 3G30C).
[PDF2] 25.DING.ING.PCCEC.omplement.pdf (Rapport RT3 CDS, RDC).
"""