#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
LECTEUR DE BASE DE DONNÉES YAML — solar_cells_db.py (v28 FINAL, BILINGUE)
YAML DATA LOADER — uniform schema, 1/0 flags, POIDS [S1], F2/F4, F3, F5
===============================================================================
[FR] Charge solar_cells_database.yaml et expose l'API :
     CELLS, CELLULES_PHYSIQUE, CELLULES_BENCHMARK, N_CELLS,
     REFERENCES_BIBLIOGRAPHIQUES.

     • Schéma UNIFORME (mêmes champs, null si absent) + drapeaux 1/0.
     • Remap auto des clés (area_cm2→area, ep_um→ep, cg_um→cg, T_ref_C→T_ref)
       + alias fabricant→fab.
     • Drapeau tc_interpole : gère le désalignement flu ≠ tc.f.
     • [S1]  POIDS de confiance + rapport_provenance().
     • [F2]  provenance_elec (measured / manufacturer-derived).
     • [F4]  component_type (bare_cell / wafer / CIC / assembly).
     • [v28-F3] champ `radiation` structuré :
                particule, energie_MeV, fluence (valeurs absolues),
                unit, fluence_type, rdc_vers_1MeV_e.
                Backward compatible : si absent, conversion depuis flu/rad.
     • [v28-F5] champ `diode_v28` optionnel :
                statut, erreur, poids_confiance, R_sh.
                SEUIL_REJET = 5 % (au-delà → statut REJETÉ).
     • [v28-M22] champ `dommages` : 8 canaux (rad, thermal, age, opt,
                mech, ESD, impact, TJ).
     • [v28-M18] champ `recuit` : actif, type_recuit, familles, T_profil.
     • [v28-M23] champ `sous_cellules` : top/middle/bottom (TJ/QJ uniquement).
     • [v28-CRYO] champ `profil_mission` : LEO_STANDARD / GEO_STANDARD /
                JUICE_JUPITER / MARS_SURFACE.

[EN] Loads solar_cells_database.yaml and exposes the same API as the legacy
     .py module. Uniform schema (null-if-missing), 1/0 flags, key remap,
     tc_interpole handling, POIDS [S1], F2/F4 provenance, F3 structured
     radiation, F5 enriched diode (R_sh + rejection threshold), v28 damage
     channels, annealing, subcells, and mission profiles.

HISTORIQUE / HISTORY
     v3  : schéma uniforme + remap + ajout facile
     v5  : tc_interpole + validation étendue
     v27 : S1 (POIDS) + F2 (provenance_elec) + F4 (component_type)
     v28 : + F3 (fluence structurée {particule, énergie, unité})
           + F5 (R_sh + seuil de rejet 5 % + poids confiance)
           + M22 (dommages 8 canaux) + M18 (recuit) + M23 (sous-cellules)
           + CRYO (profil_mission)

COHÉRENCE / CONSISTENCY
     Le schéma produit est attendu par :
     - jumeau_numerique_final.py v28
     - converter.py v28
     - generer_yaml_uniforme.py v8
     Ne pas ajouter de champs supplémentaires sans mettre à jour CHAMPS_*.

USAGE / USAGE
     from solar_cells_db import CELLS, CELLULES_PHYSIQUE, ...  # dans le jumeau
     python solar_cells_db.py                                   # validation seule

RÉFÉRENCES / REFERENCES
     [1-18]  AZUR SPACE DB 00010894/92/91/93/97, 0003384/429/6050/6051/4301/2490/2162/3569.
     [19-23] Spectrolab XTE-SF / XTJ Prime / XTJ / TASC / UTJ.
     [24-26] SolAero ZTJ / ZTJ+ / ZTJ-Ω.
     [27]    CESI, "CTJ30 datasheet v2025.1," 2025.
     [28]    Pindado & Cubas, Renew. Energy 103 (2017).
     [29]    Pindado et al., Energies 11 (2018).
     [31]    Tada et al., "Solar Cell Radiation Handbook," JPL 82-69 (1982).
     [32]    Jain & Kapoor, Solar Energy Materials (2004).
     [33]    Corless et al., "On the Lambert W function," Adv. Comput. Math. (1996).
     [34]    ECSS-E-ST-20-08C Rev.2, ESA-ESTEC (20 avril 2023).
     RT3     Rapport RT3 CDS 25.DING.ING.PCCEC (RDC protonique 2.66, 9.03).
===============================================================================
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

try:
    import yaml
except ImportError:
    raise SystemExit("⚠️  pip install pyyaml")

__version__ = "28"
FICHIER = Path(__file__).parent / "solar_cells_database.yaml"

# =============================================================================
# 1. POIDS DE CONFIANCE [S1] / CONFIDENCE WEIGHTS [S1]
# =============================================================================
POIDS = {
    "datasheet":  1.0,
    "analytique": 0.8,
    "numerique":  0.5,
    "estime":     0.3,
    "inexistant": 0.0,
}

# =============================================================================
# 2. CONSTANTES F3 — FLUENCE STRUCTURÉE / F3 CONSTANTS — STRUCTURED FLUENCE
# =============================================================================
PARTICULES_VALIDES = {"electron", "proton", "neutron", "heavy_ion"}
FLUENCE_TYPES = {"experimental", "equivalent_NIEL", "equivalent_DDD"}
UNITES_FLUENCE = {"e/cm²", "p/cm²", "n/cm²", "ion/cm²"}
FACTEUR_LEGACY = 1e14  # multiplicateur legacy (flu × 1e14)

# RDC mesurés (Rapport RT3 CDS) / Measured RDC (RT3 CDS report)
RDC_MESURES = {
    ("proton", 3.0): 2.66,   # RDC 3MeV p → 1MeV e
    ("proton", 9.5): 9.03,   # RDC 9.5MeV p → 1MeV e
}

# =============================================================================
# 3. CONSTANTES F5 — DIODE ENRICHIE / F5 CONSTANTS — ENRICHED DIODE
# =============================================================================
SEUIL_REJET = 0.05  # 5% d'erreur max sur P_max

# =============================================================================
# 4. PROFILS MISSION VALIDES [v28-CRYO] / VALID MISSION PROFILES
# =============================================================================
PROFILS_MISSION_VALIDES = {
    "LEO_STANDARD", "GEO_STANDARD", "JUICE_JUPITER", "MARS_SURFACE",
}

# =============================================================================
# 5. STATUT DES CANAUX DE DOMMAGE [v28-M22] / DAMAGE CHANNEL STATUS
# =============================================================================
STATUT_CANAL = {
    "rad":     "PARTIALLY_REVERSIBLE",
    "thermal": "PRACTICALLY_IRREVERSIBLE",
    "age":     "PRACTICALLY_IRREVERSIBLE",
    "opt":     "PRACTICALLY_IRREVERSIBLE",
    "mech":    "FUNDAMENTALLY_IRREVERSIBLE",
    "ESD":     "FUNDAMENTALLY_IRREVERSIBLE",
    "impact":  "FUNDAMENTALLY_IRREVERSIBLE",
    "TJ":      "PRACTICALLY_IRREVERSIBLE",
}

# =============================================================================
# 6. SCHÉMA — LISTES DE CHAMPS / SCHEMA — FIELD LISTS
# =============================================================================
# Remap des clés avec unités / Unit-suffixed key remap
_RENAMES = {"area_cm2": "area", "ep_um": "ep", "cg_um": "cg", "T_ref_C": "T_ref"}
_INV = {v: k for k, v in _RENAMES.items()}

# Champs à valeurs / Value fields
CHAMPS_VALEUR = [
    "ref", "fabricant", "tech", "N_s", "area", "ep", "cg", "T_ref",
    "spectre", "rad", "flu", "Voc", "Isc", "Vmp", "Imp",
    "tc", "tc_src", "eff", "note_fr", "note_en",
    "component_type", "provenance_elec",
]

# Drapeaux de disponibilité (1/0) / Availability flags (1/0)
CHAMPS_DISPO = [
    "aire_dispo", "ep_dispo", "coverglass_dispo", "tc_dispo", "flu_dispo",
    "eff_dispo", "spectre_dispo", "rad_dispo", "eol_dispo", "diode_dispo",
    "datasheet_dispo", "qualif_dispo",
]

# Propriétés booléennes (1/0) / Boolean properties (1/0)
CHAMPS_PROP = [
    "has_coverglass", "has_bypass_diode", "has_contacts",
    "space_qualified", "terrestrial",
]

# [v28] Champs v28 pour mécanismes M17-M24 / v28 fields for M17-M24
CHAMPS_V28 = [
    "mecanismes_applicables",   # dict: {"degradation": [...], "recovery": [...]}
    "sous_cellules",            # dict (top/middle/bottom) ou null
    "recuit",                   # dict: {actif, type_recuit, familles, T_profil}
    "d_stable_fraction",        # float ou null (dommage permanent)
    "in_orbit_annealing",       # dict ou null
    "profil_mission",           # str ou null
    "dommages",                 # dict: 8 canaux
]

# [v28-F3] Champ radiation structuré / Structured radiation field
CHAMPS_F3 = [
    "radiation",                # list de dicts structurés
]

# [v28-F5] Champ diode enrichie (optionnel) / Enriched diode field (optional)
CHAMPS_F5 = [
    "diode_v28",                # dict: {statut, erreur, poids_confiance, R_sh}
]

# =============================================================================
# 7. FONCTIONS F3 — FLUENCE STRUCTURÉE / F3 FUNCTIONS — STRUCTURED FLUENCE
# =============================================================================
def parser_chaine_rad(rad_str: str) -> tuple:
    """[FR] Parse la chaîne rad legacy (ex: "1MeV e-", "3MeV p+") en
    (particule, energie_MeV). Retourne ("electron", 1.0) par défaut.
    [EN] Parses legacy rad string into (particle, energy_MeV)."""
    if not rad_str:
        return "electron", 1.0
    rad_lower = str(rad_str).lower()
    if any(k in rad_lower for k in ("p+", "proton")):
        particule = "proton"
    elif any(k in rad_lower for k in ("n", "neutron")):
        particule = "neutron"
    elif any(k in rad_lower for k in ("ion", "heavy")):
        particule = "heavy_ion"
    else:
        particule = "electron"
    m = re.search(r"([\d.]+)\s*MeV", str(rad_str), re.IGNORECASE)
    energie = float(m.group(1)) if m else 1.0
    return particule, energie


def normaliser_radiation(c: dict) -> list:
    """[FR] Normalise le champ radiation (v28) ou convertit depuis flu/rad (v27).
    Retourne une liste de dicts structurés.

    Cas 1 : champ "radiation" présent (schéma v28) → validation.
    Cas 2 : champ "radiation" absent → conversion depuis flu/rad (backward).

    [EN] Normalizes the radiation field (v28) or converts from flu/rad (v27).
    Returns a list of structured dicts.
    """
    # CAS 1 : champ "radiation" présent (schéma v28)
    if "radiation" in c and c["radiation"] is not None:
        rad_list = c["radiation"]
        if isinstance(rad_list, dict):
            rad_list = [rad_list]
        if not isinstance(rad_list, list):
            rad_list = []
        for r in rad_list:
            if not isinstance(r, dict):
                continue
            # Validation particule / Particle validation
            if r.get("particule") not in PARTICULES_VALIDES:
                r["particule"] = "electron"
            # Validation fluence_type / Fluence type validation
            if r.get("fluence_type") not in FLUENCE_TYPES:
                r["fluence_type"] = "experimental"
            # Validation unité / Unit validation
            if r.get("unit") not in UNITES_FLUENCE:
                r["unit"] = "e/cm²"
            # Normalisation fluence → list / Normalize fluence → list
            flu = r.get("fluence")
            if isinstance(flu, (int, float)):
                r["fluence"] = [float(flu)]
            elif isinstance(flu, np.ndarray):
                r["fluence"] = flu.tolist()
            elif not isinstance(flu, list):
                r["fluence"] = []
            # Lookup RDC mesuré si proton et rdc non fourni
            if r.get("rdc_vers_1MeV_e") is None and r.get("particule") == "proton":
                energie = r.get("energie_MeV", 1.0)
                for (p, e), rdc_val in RDC_MESURES.items():
                    if p == "proton" and abs(e - energie) < 0.5:
                        r["rdc_vers_1MeV_e"] = rdc_val
                        break
        return rad_list

    # CAS 2 : backward compatible v27 (flu + rad)
    flu = c.get("flu") or [0.0]
    rad_str = c.get("rad") or "1MeV e-"
    particule, energie = parser_chaine_rad(rad_str)
    if isinstance(flu, np.ndarray):
        flu = flu.tolist()
    fluence_absolue = [f * FACTEUR_LEGACY for f in flu]
    unite = {"electron": "e/cm²", "proton": "p/cm²",
             "neutron": "n/cm²", "heavy_ion": "ion/cm²"}.get(particule, "e/cm²")
    rdc = None
    if particule == "proton":
        for (p, e), rdc_val in RDC_MESURES.items():
            if abs(e - energie) < 0.5:
                rdc = rdc_val
                break
    return [{
        "particule": particule,
        "energie_MeV": float(energie),
        "fluence": fluence_absolue,
        "unit": unite,
        "fluence_type": "experimental",
        "rdc_vers_1MeV_e": rdc,
    }]


def fluence_equivalente_1MeV(radiation: dict) -> Optional[List[float]]:
    """[FR] Calcule la fluence équivalente 1 MeV électron.
    Source : Rapport RT3 CDS (RDC 3MeV→1MeV = 2.66 ; 9.5MeV→1MeV = 9.03).
    Retourne None si NON_IDENTIFIABLE.
    [EN] Computes 1 MeV electron equivalent fluence. Returns None if
    NON_IDENTIFIABLE."""
    particule = radiation.get("particule")
    energie = radiation.get("energie_MeV", 1.0)
    fluence = radiation.get("fluence", [])

    if not fluence:
        return None

    # Électrons : déjà en e⁻/cm² / Electrons: already in e⁻/cm²
    if particule == "electron":
        if abs(energie - 1.0) < 0.1:
            return fluence  # déjà 1 MeV / already 1 MeV
        else:
            return None  # NON_IDENTIFIABLE sans table NIEL

    # Protons : utiliser RDC / Protons: use RDC
    elif particule == "proton":
        rdc = radiation.get("rdc_vers_1MeV_e")
        if rdc is None:
            for (p, e), rdc_val in RDC_MESURES.items():
                if p == "proton" and abs(e - energie) < 0.5:
                    rdc = rdc_val
                    break
        if rdc is not None:
            return [f * rdc for f in fluence]
        else:
            return None  # NON_IDENTIFIABLE

    # Autres particules : NON_IDENTIFIABLE / Other particles
    else:
        return None


def get_rdc(particule: str, energie_MeV: float) -> Optional[float]:
    """[FR] Retourne le RDC mesuré ou None (NON_IDENTIFIABLE).
    [EN] Returns measured RDC or None (NON_IDENTIFIABLE)."""
    for (p, e), rdc in RDC_MESURES.items():
        if p == particule and abs(e - energie_MeV) < 0.5:
            return rdc
    return None


def fluence_legacy(c: dict, i: int) -> Optional[float]:
    """[FR] Retourne la fluence legacy (multiplicateur ×10^14) pour l'index i.
    Utilisée pour backward compatibility avec les modules v27.
    [EN] Returns legacy fluence (×10^14 multiplier) for index i."""
    flu = c.get("flu")
    if flu is not None:
        if isinstance(flu, (list, np.ndarray)) and i < len(flu):
            return float(flu[i])
        return None
    # Fallback : depuis radiation structurée
    rad_list = c.get("radiation") or []
    if rad_list and isinstance(rad_list, list) and len(rad_list) > 0:
        fluence = rad_list[0].get("fluence", [])
        if fluence and i < len(fluence):
            return fluence[i] / FACTEUR_LEGACY
    return None

# =============================================================================
# 8. NORMALISATION — REMAP DES CLÉS / NORMALIZATION — KEY REMAP
# =============================================================================
def _norm(c: dict) -> dict:
    """[FR] Remap les clés avec unités + alias fabricant→fab + vecteurs numpy.
    [EN] Remaps unit-suffixed keys + manufacturer alias + numpy vectors."""
    c = dict(c)
    # Remap des clés avec unités / Remap unit-suffixed keys
    for k_new, k_old in _RENAMES.items():
        if k_new in c:
            c[k_old] = c.get(k_new)
    # Alias fabricant → fab / Manufacturer alias
    if "fab" not in c:
        c["fab"] = c.get("fabricant", "?")
    # Conversion vecteurs → numpy / Vector → numpy conversion
    for g in ("flu", "Voc", "Isc", "Vmp", "Imp"):
        if c.get(g) is not None and isinstance(c[g], list):
            c[g] = np.asarray(c[g], float)
    # [v28-F3] Normalisation radiation / Radiation normalization
    c["radiation"] = normaliser_radiation(c)
    return c

# =============================================================================
# 9. CHARGEMENT DU YAML / YAML LOADING
# =============================================================================
def charger(fichier: Path = FICHIER) -> Dict[str, List[dict]]:
    """[FR] Charge le YAML et retourne {physiques, benchmark}.
    [EN] Loads the YAML and returns {physiques, benchmark}."""
    if not fichier.exists():
        raise FileNotFoundError(f"❌ Fichier YAML introuvable : {fichier}")
    with open(fichier, encoding="utf-8") as f:
        db = yaml.safe_load(f)
    physiques = [_norm(c) for c in db.get("cellules_physique", [])]
    benchmark = [_norm(c) for c in db.get("cellules_benchmark", [])]
    return {"physiques": physiques, "benchmark": benchmark, "meta": db.get("meta", {})}

# =============================================================================
# 10. PROVENANCE — POIDS THERMIQUE & ÉLECTRIQUE [S1, F2, S2]
# =============================================================================
def poids_tc(c: dict) -> tuple:
    """[FR] (poids, source) du coeff thermique depuis la cellule. [v27-S2]
    Distingue datasheet / interpolé / extrapolé / repli générique.
    Échelle : datasheet=1.0 ; interpolé/extrapolé/repli/estimé=0.3.
    [EN] (weight, source) of thermal coeff from cell."""
    tc = c.get("tc")
    if not (tc and tc.get("f")):
        return 0.3, "repli générique"
    tcf = np.asarray(tc["f"], float)
    flu = np.asarray(c.get("flu") or [0.0], float)
    ti = c.get("tc_interpole")
    # extrapolation : fluence hors de la plage tc.f
    if bool(np.any((flu < tcf.min() - 1e-9) | (flu > tcf.max() + 1e-9))):
        return 0.3, "extrapolé"
    # interpolation : drapeau tc_interpole présent et actif
    if ti is not None and bool(np.any(np.asarray(ti) > 0)):
        return 0.3, "interpolé"
    return (1.0, "datasheet") if c.get("tc_src") == "datasheet" else (0.3, "estimé")


def poids_elec(c: dict) -> tuple:
    """[FR] (poids, source) de la provenance électrique. [v27-F2]
    measured=1.0 ; manufacturer-derived=0.8.
    [EN] (weight, source) of electrical provenance."""
    prov = c.get("provenance_elec", "measured")
    if prov == "measured":
        return 1.0, "datasheet mesuré"
    if prov == "manufacturer-derived":
        return 0.8, "BOL × rétention"
    return 0.0, "inexistant"


def poids_diode_v28(c: dict) -> tuple:
    """[v28-F5] (poids, statut) de la diode enrichie.
    Retourne (poids, statut) depuis le champ diode_v28.
    [EN] (weight, status) of enriched diode from diode_v28 field."""
    dv = c.get("diode_v28")
    if not dv or not isinstance(dv, dict):
        return 0.0, "NON_IDENTIFIABLE"
    statut = dv.get("statut", "NON_IDENTIFIABLE")
    if statut == "actif":
        erreur = dv.get("erreur", 1.0)
        if erreur < 0.01:
            return 1.0, "actif (excellent)"
        elif erreur < SEUIL_REJET:
            return 0.5, "actif (acceptable)"
        else:
            return 0.0, "REJETE"
    elif statut == "REJETE":
        return 0.0, "REJETE"
    else:
        return 0.0, "NON_IDENTIFIABLE"


def rapport_provenance() -> None:
    """[FR] Affiche un rapport de provenance (TC + élec + type + diode v28).
    [S1/S2/F2/F4/v28-F5]
    [EN] Prints a provenance report (TC + elec + type + diode v28)."""
    print("\n📊 RAPPORT DE PROVENANCE / PROVENANCE REPORT")
    print("-" * 70)
    print(f"{'Ref':14s} {'TC':5s} {'Source TC':16s} {'Élec':5s} "
          f"{'Source Élec':20s} {'Type':12s} {'Diode':10s}")
    print("-" * 70)
    for c in CELLULES_PHYSIQUE:
        p_tc, s_tc = poids_tc(c)
        p_el, s_el = poids_elec(c)
        ct = c.get("component_type", "bare_cell")
        p_dv, s_dv = poids_diode_v28(c)
        print(f"{c.get('ref','?'):14s} {p_tc:.2f}  {s_tc:16s} {p_el:.2f}  "
              f"{s_el:20s} {ct:12s} {s_dv:10s}")
    print("-" * 70)

# =============================================================================
# 11. VALIDATION / VALIDATION
# =============================================================================
def valider_schema(db: Dict[str, List[dict]]) -> List[str]:
    """[FR] Valide le schéma uniforme (champs v27). Retourne liste d'anomalies.
    [EN] Validates the uniform schema (v27 fields). Returns issue list."""
    issues = []
    oblig = CHAMPS_VALEUR + CHAMPS_DISPO + CHAMPS_PROP + ["tc_interpole"]
    for groupe, cells in (("physique", db["physiques"]), ("benchmark", db["benchmark"])):
        for c in cells:
            ref = c.get("ref", "?")
            for k in oblig:
                if k not in c:
                    issues.append(f"{groupe}/{ref}: champ manquant {k}")
            # Cohérence longueur flu / vecteurs électriques
            flu = c.get("flu")
            if flu is not None:
                for g in ("Voc", "Isc", "Vmp", "Imp"):
                    v = c.get(g)
                    if v is not None and len(v) != len(flu):
                        issues.append(f"{groupe}/{ref}: {g} ({len(v)}) ≠ flu ({len(flu)})")
            # Anomalie efficacité > 40 %
            eff = c.get("eff")
            if eff is not None and eff > 40:
                issues.append(f"{groupe}/{ref}: eff={eff}% > 40% (assemblage ?)")
    return issues


def valider_schema_v28(db: Dict[str, List[dict]]) -> List[str]:
    """[FR] Valide les nouveaux champs v28 (F3 + F5 + M22 + M18 + M23 + CRYO).
    Les champs v28 sont OPTIONNELS : absence = OK (backward compatible).
    [EN] Validates v28 fields (F3 + F5 + M22 + M18 + M23 + CRYO).
    v28 fields are OPTIONAL: absence = OK (backward compatible)."""
    issues = []
    for c in db["physiques"]:
        ref = c.get("ref", "?")
        tech = c.get("tech")

        # [v28-F3] Validation radiation
        rad = c.get("radiation")
        if rad is not None:
            if not isinstance(rad, list):
                issues.append(f"v28/{ref}: radiation non-liste")
            else:
                for i, r in enumerate(rad):
                    if not isinstance(r, dict):
                        issues.append(f"v28/{ref}: radiation[{i}] non-dict")
                        continue
                    if r.get("particule") not in PARTICULES_VALIDES:
                        issues.append(f"v28/{ref}: particule invalide '{r.get('particule')}'")
                    if r.get("fluence_type") not in FLUENCE_TYPES:
                        issues.append(f"v28/{ref}: fluence_type invalide")
                    if r.get("unit") not in UNITES_FLUENCE:
                        issues.append(f"v28/{ref}: unité invalide '{r.get('unit')}'")
                    flu = r.get("fluence")
                    if not isinstance(flu, list) or not all(
                            isinstance(x, (int, float)) for x in flu):
                        issues.append(f"v28/{ref}: fluence non-numérique")

        # [v28-F5] Validation diode_v28
        dv = c.get("diode_v28")
        if dv is not None:
            if not isinstance(dv, dict):
                issues.append(f"v28/{ref}: diode_v28 non-dict")
            else:
                statut = dv.get("statut")
                if statut not in ("actif", "REJETE", "NON_IDENTIFIABLE"):
                    issues.append(f"v28/{ref}: diode_v28 statut invalide '{statut}'")
                if statut == "actif":
                    erreur = dv.get("erreur")
                    if erreur is not None and erreur > SEUIL_REJET:
                        issues.append(f"v28/{ref}: diode_v28 erreur {erreur:.2%} > seuil")

        # [v28-M22] Validation dommages
        dom = c.get("dommages")
        if dom is not None:
            if not isinstance(dom, dict):
                issues.append(f"v28/{ref}: dommages non-dict")
            else:
                for k, v in dom.items():
                    if k not in STATUT_CANAL:
                        issues.append(f"v28/{ref}: canal inconnu '{k}'")
                    if v is not None and not (0 <= float(v) <= 1):
                        issues.append(f"v28/{ref}: D_{k}={v} hors [0,1]")

        # [v28-M23] Validation sous_cellules
        sc = c.get("sous_cellules")
        if tech in ("TJ", "QJ") and not sc:
            issues.append(f"v28/{ref}: TJ/QJ sans sous_cellules")
        if tech not in ("TJ", "QJ") and sc:
            issues.append(f"v28/{ref}: {tech} avec sous_cellules (devrait être null)")

        # [v28-CRYO] Validation profil_mission
        pm = c.get("profil_mission")
        if pm is not None and pm not in PROFILS_MISSION_VALIDES:
            issues.append(f"v28/{ref}: profil_mission '{pm}' invalide")

        # [v28-M18] Validation recuit
        rec = c.get("recuit")
        if rec is not None and isinstance(rec, dict):
            if rec.get("actif") and not rec.get("familles"):
                issues.append(f"v28/{ref}: recuit actif sans familles")

    return issues


def valider(db: Dict[str, List[dict]]) -> List[str]:
    """[FR] Validation complète (v27 + v28). [EN] Full validation (v27 + v28)."""
    return valider_schema(db) + valider_schema_v28(db)

# =============================================================================
# 12. AJOUT DE CELLULES / ADDING CELLS
# =============================================================================
def ajouter_cellule_physique(ref, fabricant, tech, N_s, area_cm2, flu, Voc, Isc,
                             Vmp, Imp, tc=None, tc_src="estime", eff=None,
                             component_type="bare_cell", provenance_elec="measured",
                             radiation=None, dommages=None, recuit=None,
                             sous_cellules=None, profil_mission=None, **kwargs) -> None:
    """[FR] Ajoute une cellule physique au schéma uniforme + champs v28.
    [EN] Adds a physical cell to the uniform schema + v28 fields."""
    c = {
        "ref": ref, "fabricant": fabricant, "tech": tech, "N_s": N_s,
        "area_cm2": area_cm2, "flu": list(flu),
        "Voc": list(Voc), "Isc": list(Isc), "Vmp": list(Vmp), "Imp": list(Imp),
        "tc": tc, "tc_src": tc_src, "eff": eff,
        "component_type": component_type, "provenance_elec": provenance_elec,
        "note_fr": kwargs.get("note_fr", ""), "note_en": kwargs.get("note_en", ""),
        "spectre": kwargs.get("spectre"), "rad": kwargs.get("rad"),
        "ep_um": kwargs.get("ep_um"), "cg_um": kwargs.get("cg_um"),
        "T_ref_C": kwargs.get("T_ref_C"),
    }
    # Drapeaux / Flags
    c.update({
        "aire_dispo": int(area_cm2 is not None),
        "ep_dispo": int(kwargs.get("ep_um") is not None),
        "coverglass_dispo": int(kwargs.get("cg_um") is not None),
        "tc_dispo": int(bool(tc and tc.get("f"))),
        "flu_dispo": 1,
        "eff_dispo": int(eff is not None),
        "spectre_dispo": int(kwargs.get("spectre") is not None),
        "rad_dispo": int(kwargs.get("rad") is not None),
        "eol_dispo": int(len(flu) > 1),
        "diode_dispo": 0,
        "datasheet_dispo": 1,
        "qualif_dispo": int(kwargs.get("space_qualified", 1)),
        "has_coverglass": int((kwargs.get("cg_um") or 0) > 0),
        "has_bypass_diode": 0,
        "has_contacts": 1,
        "space_qualified": int(kwargs.get("space_qualified", 1)),
        "terrestrial": int(kwargs.get("terrestrial", 0)),
        "tc_interpole": None,
    })
    # Champs v28 / v28 fields
    c["radiation"] = radiation
    c["dommages"] = dommages
    c["recuit"] = recuit
    c["sous_cellules"] = sous_cellules
    c["profil_mission"] = profil_mission
    c["mecanismes_applicables"] = kwargs.get("mecanismes_applicables")
    c["d_stable_fraction"] = kwargs.get("d_stable_fraction")
    c["in_orbit_annealing"] = kwargs.get("in_orbit_annealing")
    c["diode_v28"] = kwargs.get("diode_v28")
    # Normalisation + ajout / Normalize + add
    CELLULES_PHYSIQUE.append(_norm(c))
    CELLS[ref] = CELLULES_PHYSIQUE[-1]


def ajouter_cellule_benchmark(ref, fabricant, tech, eff, flag=False, **kwargs) -> None:
    """[FR] Ajoute une cellule benchmark (BOL only). [EN] Adds a benchmark cell."""
    c = {
        "ref": ref, "fabricant": fabricant, "tech": tech, "eff": eff,
        "flag": flag, "note_fr": "", "note_en": "",
        "component_type": kwargs.get("component_type", "bare_cell"),
        "provenance_elec": kwargs.get("provenance_elec", "measured"),
    }
    for k in CHAMPS_DISPO:
        c[k] = 0
    for k in CHAMPS_PROP:
        c[k] = 0
    c["aire_dispo"] = int(kwargs.get("area_cm2") is not None)
    c["eff_dispo"] = int(eff is not None)
    c["datasheet_dispo"] = 1
    c["terrestrial"] = int(kwargs.get("terrestrial", 1))
    c["tc_interpole"] = None
    # Champs v28 / v28 fields
    for k in CHAMPS_V28 + CHAMPS_F3 + CHAMPS_F5:
        c[k] = None
    CELLULES_BENCHMARK.append(_norm(c))
    CELLS[ref] = CELLULES_BENCHMARK[-1]

# =============================================================================
# 13. EXPORT STYLE BLOC / BLOCK-STYLE EXPORT
# =============================================================================
def exporter_style_bloc(fichier: str = "solar_cells_database_bloc.yaml") -> None:
    """[FR] Ré-écrit la base en style bloc lisible. [EN] Re-writes in block style."""

    def nat(v):
        if isinstance(v, np.ndarray):
            return v.tolist()
        if isinstance(v, (np.floating, np.integer)):
            return v.item()
        return v

    data = {
        "meta": {"version": "2.3", "n_physique": len(CELLULES_PHYSIQUE),
                 "n_benchmark": len(CELLULES_BENCHMARK),
                 "generateur": f"solar_cells_db.py v{__version__}"},
        "cellules_physique": [{k: nat(v) for k, v in c.items()}
                              for c in CELLULES_PHYSIQUE],
        "cellules_benchmark": [{k: nat(v) for k, v in c.items()}
                               for c in CELLULES_BENCHMARK],
    }
    with open(fichier, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False,
                       default_flow_style=False, width=90)
    print(f"✅ {fichier} écrit ({len(CELLULES_PHYSIQUE)} phys + "
          f"{len(CELLULES_BENCHMARK)} bench)")

# =============================================================================
# 14. RÉFÉRENCES BIBLIOGRAPHIQUES / BIBLIOGRAPHIC REFERENCES
# =============================================================================
REFERENCES_BIBLIOGRAPHIQUES = """
[1-18]  AZUR SPACE DB 00010894/92/91/93/97, 0003384/429/6050/6051/4301/2490/2162/3569.
[19-23] Spectrolab XTE-SF / XTJ Prime / XTJ / TASC / UTJ.
[24-26] SolAero ZTJ / ZTJ+ / ZTJ-Ω.
[27]    CESI, "CTJ30 datasheet v2025.1," 2025.
[28]    Pindado & Cubas, "Simple mathematical approach to solar cell/panel
        behavior," Renewable Energy 103, 2017.
[29]    Pindado et al., "Assessment of Explicit Models for Different
        Photovoltaic Technologies," Energies 11, 2018.
[30]    Ramadan et al., "Accurate Parameters Extraction of 3-Diode PV Model,"
        IEEE Access, 2022.
[31]    Tada et al., "Solar Cell Radiation Handbook," JPL 82-69, 1982.
[32]    Jain & Kapoor, "Exact analytical method to determine I0 and Rs,"
        Solar Energy Materials & Solar Cells, 2004.
[33]    Corless et al., "On the Lambert W function," Adv. Comput. Math. 5, 1996.
[34]    ECSS-E-ST-20-08C Rev.2, "Photovoltaic assemblies and components,"
        ESA-ESTEC, 20 avril 2023.
[35]    Messenger et al., "Modeling solar cell degradation in space,"
        Prog. Photovolt. 9(2), 103-121, 2001.
[36]    Baur & Bett, "Modeling of the degradation of III-V TJ cells,"
        35th IEEE PVSC, 2010.
[37]    Imaizumi et al., "Radiation degradation characteristics of component
        subcells," Prog. Photovolt. 25(2), 161-174, 2017.
[105]   Rival & Mandeville, "Modeling ejecta from hypervelocity impacts,"
        Space Debris 1(1), 37-48, 1999.
[107]   Paul & Berthoud, "Cratering of spacecraft surfaces by micrometeoroids,"
        AIAA, 1995.
RT3     Rapport RT3 CDS 25.DING.ING.PCCEC → RDC protonique
        (3MeV→1MeV = 2.66 ; 9.5MeV→1MeV = 9.03).
[A]     Blanco et al., "Temperature coefficients of space solar cells," ESPC 2016.
[B]     Paige et al., "LRO Diviner lunar temperature," Space Sci. Rev. 150, 2010.
"""

# =============================================================================
# 15. API PUBLIQUE — CHARGEMENT INITIAL / PUBLIC API — INITIAL LOADING
# =============================================================================
try:
    _DB = charger(FICHIER)
    CELLULES_PHYSIQUE = _DB["physiques"]
    CELLULES_BENCHMARK = _DB["benchmark"]
    N_CELLS = len(CELLULES_PHYSIQUE) + len(CELLULES_BENCHMARK)
    CELLS = {c["ref"]: c for c in CELLULES_PHYSIQUE + CELLULES_BENCHMARK}
except FileNotFoundError:
    # Repli sur donnees_cellules_88.py / Fallback to legacy Python base
    try:
        from donnees_cellules_88 import (CELLULES_PHYSIQUE, CELLULES_BENCHMARK,
                                         CELLS as _CELLS_LEGACY)
        N_CELLS = len(CELLULES_PHYSIQUE) + len(CELLULES_BENCHMARK)
        CELLS = _CELLS_LEGACY
    except ImportError:
        raise SystemExit("❌ Ni solar_cells_database.yaml ni donnees_cellules_88.py trouvés.")

# =============================================================================
# 16. POINT D'ENTRÉE — VALIDATION + RAPPORT / ENTRY POINT — VALIDATION + REPORT
# =============================================================================
if __name__ == "__main__":
    print(f"📖 solar_cells_db.py v{__version__}")
    print(f"   physiques : {len(CELLULES_PHYSIQUE)}")
    print(f"   benchmark : {len(CELLULES_BENCHMARK)}")
    print(f"   total     : {N_CELLS}")

    # Validation v27 + v28
    issues = valider({"physiques": CELLULES_PHYSIQUE, "benchmark": CELLULES_BENCHMARK})
    if issues:
        print(f"\n⚠️  {len(issues)} anomalie(s) :")
        for i in issues:
            print(f"   - {i}")
    else:
        print("✅ Schéma uniforme OK + aucune anomalie (v27 + v28).")

    # Rapport provenance
    rapport_provenance()

    # [v28-F3] Statut radiation
    n_rad = sum(1 for c in CELLULES_PHYSIQUE if c.get("radiation"))
    print(f"\n🔬 F3 Radiation structurée : {n_rad}/{len(CELLULES_PHYSIQUE)} cellules")

    # [v28-F5] Statut diode enrichie
    n_dv = sum(1 for c in CELLULES_PHYSIQUE if c.get("diode_v28"))
    print(f"🔬 F5 Diode enrichie : {n_dv}/{len(CELLULES_PHYSIQUE)} cellules")

    # Références
    print(REFERENCES_BIBLIOGRAPHIQUES)