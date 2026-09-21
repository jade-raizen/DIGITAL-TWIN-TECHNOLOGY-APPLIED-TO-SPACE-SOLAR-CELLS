#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
GÉNÉRATEUR YAML UNIFORME — generer_yaml_uniforme.py (v8 FINAL, BILINGUE)
UNIFORM-SCHEMA YAML GENERATOR
(+ F2 provenance élec, + F4 component_type, + v7 champs M17-M24, + F3 fluence
   structurée {particule, énergie, unité})
===============================================================================
[FR] RÔLE
     Lit la base Python legacy (donnees_cellules_88.py) et produit
     solar_cells_database.yaml avec un schéma STRICTEMENT UNIFORME :
       • mêmes champs pour TOUTES les cellules (physiques + benchmark) ;
       • valeur absente → null ;
       • drapeaux 1/0 → *_dispo (disponibilité) + propriétés ;
       • clés avec unités : area_cm2, ep_um, cg_um, T_ref_C ;
       • correction datasheet CESI (CTJ30 / CTJ_LC) [27] ;
       • drapeau tc_interpole (calculé par le lecteur, généré à null) ;
       • [F2] champ provenance_elec (measured / manufacturer-derived) ;
       • [F4] champ component_type (bare_cell / wafer / CIC / assembly).

     NOUVEAUTÉS v7 (alignées sur le jumeau v28) :
       • [v7-M22] champ mecanismes_applicables ;
       • [v7-M23] champ sous_cellules (top/middle/bottom) pour TJ/QJ ;
       • [v7-M18] champ recuit (actif, type_recuit, familles, T_profil) ;
       • [v7-M22] champ d_stable_fraction (dommage permanent) ;
       • [v7-CRYO] champ in_orbit_annealing ;
       • [v7-CRYO] champ profil_mission.

     NOUVEAUTÉS v8 (F3 — fluence structurée) :
       • [v8-F3] champ `radiation` : liste de dicts structurés avec
                 particule, energie_MeV, fluence (valeurs absolues),
                 unit, fluence_type, temperature_irradiation_C,
                 rdc_vers_1MeV_e ;
       • [v8-F3] conversion automatique depuis flu/rad (backward compat) ;
       • [v8-F3] champ `flu` conservé mais marqué DÉPRÉCIÉ ;
       • [v8-F3] RDC mesurés intégrés (2.66, 9.03 — Rapport RT3 CDS).

     RÈGLE D'HONNÊTETÉ / HONESTY RULE :
       Toute donnée inconnue → null + méthode d'identification en note.
       JAMAIS inventer une valeur (A, Ea, d_stable, RDC inconnu, etc.).

[EN] ROLE
     Reads the legacy Python base (donnees_cellules_88.py) and produces
     solar_cells_database.yaml with a STRICTLY UNIFORM schema:
       • same fields for ALL cells (physical + benchmark) ;
       • missing value → null ;
       • 1/0 flags → *_dispo (availability) + properties ;
       • unit-suffixed keys: area_cm2, ep_um, cg_um, T_ref_C ;
       • CESI datasheet correction (CTJ30 / CTJ_LC) [27] ;
       • tc_interpole flag (computed by loader, generated as null) ;
       • [F2] provenance_elec field (measured / manufacturer-derived) ;
       • [F4] component_type field (bare_cell / wafer / CIC / assembly).

     v7 NEW FEATURES (aligned with twin v28):
       • mecanismes_applicables, sous_cellules, recuit, d_stable_fraction,
         in_orbit_annealing, profil_mission fields.

     v8 NEW FEATURES (F3 — structured fluence):
       • `radiation` field: list of structured dicts with particle,
         energy_MeV, fluence (absolute values), unit, fluence_type,
         irradiation_temperature_C, rdc_to_1MeV_e ;
       • Automatic conversion from flu/rad (backward compatible) ;
       • `flu` field kept but marked DEPRECATED ;
       • Measured RDC integrated (2.66, 9.03 — RT3 CDS report).

     HONESTY RULE:
       Any unknown data → null + identification method in note.
       NEVER invent a value (A, Ea, d_stable, unknown RDC, etc.).

HISTORIQUE / HISTORY
     v5 : schéma uniforme + correction CESI + tc_interpole
     v6 : + F2 (provenance_elec) + F4 (component_type)
     v7 : + champs v28 (mécanismes, sous-cellules, recuit, mission)
     v8 : + F3 (fluence structurée {particule, énergie, unité})

SCHÉMA / SCHEMA
     CHAMPS_VALEUR + CHAMPS_DISPO + CHAMPS_PROP + CHAMPS_V28 + CHAMPS_F3
     (constantes ci-dessous / constants below).

USAGE / USAGE
     python generer_yaml_uniforme.py                  # génère le YAML
     python generer_yaml_uniforme.py --sortie X.yaml  # sortie personnalisée

RÉFÉRENCES / REFERENCES
     [1-27] Datasheets fabricants / manufacturer datasheets
            (AZUR, Spectrolab, SolAero, CESI).
     [27]   CESI, "CTJ30 datasheet v2025.1," 2025 → correction CTJ30/CTJ_LC.
     [31]   Tada et al., "Solar Cell Radiation Handbook," JPL 82-69 (1982).
     [34]   ECSS-E-ST-20-08C Rev.2, ESA-ESTEC (20 avril 2023).
     [36]   Baur & Bett, "Modeling of the degradation of III-V TJ cells,"
            35th IEEE PVSC (2010).
     [37]   Imaizumi et al., "Radiation degradation characteristics of
            component subcells," Prog. Photovolt. 25(2), 161-174 (2017).
     RT3    Rapport RT3 CDS 25.DING.ING.PCCEC → RDC protonique
            (3MeV→1MeV = 2.66 ; 9.5MeV→1MeV = 9.03).

DÉPENDANCES / DEPENDENCIES : pip install pyyaml numpy
===============================================================================
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

try:
    import yaml
except ImportError:
    raise SystemExit("⚠️  pip install pyyaml")

try:
    import numpy as np
except ImportError:
    raise SystemExit("⚠️  pip install numpy")

try:
    import donnees_cellules_88 as d  # base source legacy / legacy source base
except ImportError:
    raise SystemExit(
        "❌ donnees_cellules_88.py introuvable (requis par le générateur).\n"
        "   File not found (required by the generator).")

__version__ = "8"
SORTIE = Path(__file__).parent / "solar_cells_database.yaml"

# =============================================================================
# 1. SCHÉMA UNIFORME — LISTES DE CHAMPS / UNIFORM SCHEMA — FIELD LISTS
# =============================================================================
# Champs à valeurs (vecteurs ou scalaires) / Value fields (vectors or scalars)
CHAMPS_VALEUR = [
    "ref", "fabricant", "tech", "N_s", "area_cm2", "ep_um", "cg_um",
    "T_ref_C", "spectre", "rad", "flu", "Voc", "Isc", "Vmp", "Imp",
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

# [v7] Champs v28 pour les mécanismes M17-M24 (OPTIONNELS)
# [v7] v28 fields for M17-M24 mechanisms (OPTIONAL)
CHAMPS_V28 = [
    "mecanismes_applicables",   # dict: {"degradation": [...], "recovery": [...]}
    "sous_cellules",            # dict (top/middle/bottom) ou null
    "recuit",                   # dict: {actif, type_recuit, familles, T_profil}
    "d_stable_fraction",        # float ou null (dommage permanent)
    "in_orbit_annealing",       # dict ou null
    "profil_mission",           # str ou null (LEO_STANDARD, JUICE_JUPITER, ...)
]

# [v8-F3] Nouveaux champs F3 pour la fluence structurée
# [v8-F3] New F3 fields for structured fluence
CHAMPS_F3 = [
    "radiation",                # list de dicts structurés (remplace flu + rad)
]

# Profils de mission valides [v7-CRYO] / Valid mission profiles
PROFILS_MISSION_VALIDES = {
    "LEO_STANDARD", "GEO_STANDARD", "JUICE_JUPITER", "MARS_SURFACE",
}

# =============================================================================
# 2. CONSTANTES F3 — FLUENCE STRUCTURÉE / F3 CONSTANTS — STRUCTURED FLUENCE
# =============================================================================
# Particules valides / Valid particles
PARTICULES_VALIDES = {"electron", "proton", "neutron", "heavy_ion"}

# Types de fluence / Fluence types
FLUENCE_TYPES = {"experimental", "equivalent_NIEL", "equivalent_DDD"}

# Unités de fluence / Fluence units
UNITES_FLUENCE = {"e/cm²", "p/cm²", "n/cm²", "ion/cm²"}

# Facteur de conversion legacy (flu × 1e14) / Legacy conversion factor
FACTEUR_LEGACY = 1e14

# RDC mesurés (Rapport RT3 CDS) / Measured RDC (RT3 CDS report)
# Source : Rapport RT3 25.DING.ING.PCCEC, p.6
RDC_MESURES = {
    ("proton", 3.0):  2.66,   # RDC 3MeV p → 1MeV e
    ("proton", 9.5):  9.03,   # RDC 9.5MeV p → 1MeV e
}

# =============================================================================
# 3. COMPOSITION DES SOUS-CELLULES CONNUES (DATASHEETS) / KNOWN SUBCELLS
# =============================================================================
# [FR] Seule la composition (matériaux + Eg) est pré-remplie car elle provient
#      des datasheets. Les valeurs électriques (Isc_mA, Voc_mV) restent null
#      car elles ne sont pas publiées par les fabricants.
# [EN] Only composition (materials + Eg) is pre-filled because it comes from
#      datasheets. Electrical values (Isc_mA, Voc_mV) remain null because
#      they are not published by manufacturers.
# Source : [36] Baur & Bett 2010, [37] Imaizumi 2017.
SOUS_CELLULES_TJ = {
    "top":    {"materiau": "GaInP", "Eg_eV": 1.87,
               "Isc_mA": None, "Voc_mV": None,
               "note": "UNKNOWN — requires subcell characterization [37]"},
    "middle": {"materiau": "GaAs", "Eg_eV": 1.424,
               "Isc_mA": None, "Voc_mV": None,
               "note": "UNKNOWN — requires subcell characterization [37]"},
    "bottom": {"materiau": "Ge", "Eg_eV": 0.66,
               "Isc_mA": None, "Voc_mV": None,
               "note": "UNKNOWN — requires subcell characterization [37]"},
}

SOUS_CELLULES_QJ = {
    "top":          {"materiau": "GaInP", "Eg_eV": 1.87,
                     "Isc_mA": None, "Voc_mV": None,
                     "note": "UNKNOWN — requires subcell characterization"},
    "upper_middle": {"materiau": "GaAs", "Eg_eV": 1.424,
                     "Isc_mA": None, "Voc_mV": None,
                     "note": "UNKNOWN — requires subcell characterization"},
    "lower_middle": {"materiau": "GaInAsP", "Eg_eV": 1.0,
                     "Isc_mA": None, "Voc_mV": None,
                     "note": "UNKNOWN — requires subcell characterization"},
    "bottom":       {"materiau": "GaInAs", "Eg_eV": 0.66,
                     "Isc_mA": None, "Voc_mV": None,
                     "note": "UNKNOWN — requires subcell characterization"},
}

# =============================================================================
# 4. MÉCANISMES APPLICABLES PAR TECHNOLOGIE / MECHANISMS BY TECHNOLOGY
# =============================================================================
# [FR] IDs des mécanismes de dégradation/récupération applicables par techno.
#      Source : mechanisms/degradation_matrix.yaml + recovery_matrix.yaml.
# [EN] Degradation/recovery mechanism IDs applicable per technology.
MECANISMES_PAR_TECH = {
    "TJ": {
        "degradation": ["DEG_RAD_001", "DEG_RAD_002", "DEG_THM_012",
                        "DEG_MJ_001", "DEG_MJ_002", "DEG_MJ_005"],
        "recovery":    ["REC_007", "REC_008", "REC_009", "REC_047"],
    },
    "QJ": {
        "degradation": ["DEG_RAD_001", "DEG_RAD_002", "DEG_THM_012",
                        "DEG_MJ_001", "DEG_MJ_002", "DEG_MJ_005", "DEG_MJ_010"],
        "recovery":    ["REC_007", "REC_008", "REC_009", "REC_047"],
    },
    "Si": {
        "degradation": ["DEG_RAD_001", "DEG_RAD_002", "DEG_THM_012",
                        "DEG_MAT_001", "DEG_MAT_007"],
        "recovery":    ["REC_007", "REC_008", "REC_009", "REC_047"],
    },
    "GaAs": {
        "degradation": ["DEG_RAD_001", "DEG_RAD_002", "DEG_THM_012",
                        "DEG_MAT_001", "DEG_MAT_007"],
        "recovery":    ["REC_007", "REC_008", "REC_009", "REC_047"],
    },
    "CIGS": {
        "degradation": ["DEG_RAD_001", "DEG_THM_011", "DEG_OPT_001"],
        "recovery":    ["REC_013"],  # light soaking pour CIGS / CIGS light soaking
    },
}

# =============================================================================
# 5. CORRECTION DATASHEET CESI / CESI DATASHEET CORRECTION
# =============================================================================
# [FR] Source [27] : CESI, "CTJ30 datasheet v2025.1," 2025.
#      Coefficients thermiques réels + dégradation corrigée.
# [EN] Source [27]: CESI, "CTJ30 datasheet v2025.1," 2025.
#      Real thermal coefficients + corrected degradation.
CORRECTION_CESI = {
    "CESI_CTJ30": {
        "flu": [0.0, 1.0, 5.0, 10.0],
        "Voc": [2650.0, 2580.0, 2530.0, 2470.0],
        "Isc": [470.0, 456.0, 446.0, 432.0],
        "Vmp": [2360.0, 2280.0, 2230.0, 2170.0],
        "Imp": [456.0, 442.0, 432.0, 418.0],
        "tc": {
            "f":    [0.0, 1.0, 5.0, 10.0],
            "dVoc": [-6.2, -6.4, -6.6, -6.7],
            "dIsc": [0.35, 0.33, 0.34, 0.37],
            "dVmp": [-6.7, -6.8, -7.0, -7.1],
            "dImp": [0.23, 0.20, 0.23, 0.27],
        },
        "tc_src": "datasheet",
        "provenance_elec": "manufacturer-derived",
        "note_fr": "Cellule CESI reconstruite à partir des facteurs de rétention [27].",
        "note_en": "CESI cell reconstructed from retention factors [27].",
    },
    "CESI_CTJ_LC": {
        "provenance_elec": "manufacturer-derived",
        "note_fr": "Cellule CESI Low Concentration [27].",
        "note_en": "CESI Low Concentration cell [27].",
    },
}

# =============================================================================
# 6. FONCTIONS F3 — FLUENCE STRUCTURÉE / F3 FUNCTIONS — STRUCTURED FLUENCE
# =============================================================================
def parser_chaine_rad(rad_str: str) -> tuple:
    """[FR] Parse la chaîne rad legacy (ex: "1MeV e-", "3MeV p+") en
    (particule, energie_MeV). Retourne ("electron", 1.0) par défaut.
    [EN] Parses legacy rad string (e.g. "1MeV e-", "3MeV p+") into
    (particle, energy_MeV). Returns ("electron", 1.0) by default."""
    if not rad_str:
        return "electron", 1.0

    rad_lower = rad_str.lower()

    # Détermine la particule / Determine particle
    if any(k in rad_lower for k in ("p+", "proton")):
        particule = "proton"
    elif any(k in rad_lower for k in ("n", "neutron")):
        particule = "neutron"
    elif any(k in rad_lower for k in ("ion", "heavy")):
        particule = "heavy_ion"
    else:
        particule = "electron"  # défaut / default

    # Extrait l'énergie numérique / Extract numeric energy
    m = re.search(r"([\d.]+)\s*MeV", rad_str, re.IGNORECASE)
    energie = float(m.group(1)) if m else 1.0

    return particule, energie


def convertir_flu_legacy(flu: list, rad_str: str, T_ref_C: float = 28.0) -> list:
    """[FR] Convertit les champs legacy flu/rad en champ radiation structuré.
    Backward compatible v7 → v8.

    Parameters
    ----------
    flu : list
        Multiplicateurs legacy (ex: [0, 2.5, 5.0, 10.0] signifie ×10^14).
    rad_str : str
        Chaîne legacy (ex: "1MeV e-").
    T_ref_C : float
        Température d'irradiation [°C].

    Returns
    -------
    list de dicts structurés / list of structured dicts.

    [EN] Converts legacy flu/rad fields into structured radiation field.
    Backward compatible v7 → v8.
    """
    if flu is None:
        flu = [0.0]
    if rad_str is None:
        rad_str = "1MeV e-"

    particule, energie = parser_chaine_rad(rad_str)

    # Convertit flu (multiplicateur ×10^14) → fluence absolue
    fluence_absolue = [f * FACTEUR_LEGACY for f in flu]

    # Détermine l'unité / Determine unit
    unite = {"electron": "e/cm²", "proton": "p/cm²",
             "neutron": "n/cm²", "heavy_ion": "ion/cm²"}[particule]

    # Cherche le RDC mesuré / Look up measured RDC
    rdc = None
    for (p, e), rdc_val in RDC_MESURES.items():
        if p == particule and abs(e - energie) < 0.5:
            rdc = rdc_val
            break

    return [{
        "particule": particule,
        "energie_MeV": energie,
        "fluence": fluence_absolue,
        "unit": unite,
        "fluence_type": "experimental",
        "temperature_irradiation_C": T_ref_C,
        "rdc_vers_1MeV_e": rdc,
        "note": "Converti depuis flu/rad legacy (v7→v8) / Converted from legacy",
    }]


def normaliser_radiation(cell: dict) -> list:
    """[FR] Normalise le champ radiation (v8) ou convertit depuis flu/rad (v7).
    Retourne une liste de dicts structurés.

    Cas 1 : champ "radiation" présent (schéma v8) → validation + normalisation.
    Cas 2 : champ "radiation" absent → conversion depuis flu/rad (backward).

    [EN] Normalizes the radiation field (v8) or converts from flu/rad (v7).
    Returns a list of structured dicts.

    Case 1: "radiation" field present (v8 schema) → validation + normalization.
    Case 2: "radiation" field absent → conversion from flu/rad (backward).
    """
    # CAS 1 : champ "radiation" présent (schéma v8)
    if "radiation" in cell and cell["radiation"] is not None:
        rad_list = cell["radiation"]
        if isinstance(rad_list, dict):
            rad_list = [rad_list]

        for r in rad_list:
            # Validation particule / Particle validation
            assert r.get("particule") in PARTICULES_VALIDES, \
                f"Particule invalide / Invalid particle: {r.get('particule')}"
            # Validation fluence_type / Fluence type validation
            assert r.get("fluence_type", "experimental") in FLUENCE_TYPES, \
                f"fluence_type invalide / Invalid: {r.get('fluence_type')}"
            # Validation unité / Unit validation
            assert r.get("unit") in UNITES_FLUENCE, \
                f"Unité invalide / Invalid unit: {r.get('unit')}"
            # Normalisation fluence → list / Normalize fluence → list
            if isinstance(r.get("fluence"), (int, float)):
                r["fluence"] = [r["fluence"]]
            if isinstance(r.get("fluence"), np.ndarray):
                r["fluence"] = r["fluence"].tolist()
        return rad_list

    # CAS 2 : backward compatible v7 (flu + rad)
    flu = cell.get("flu") or [0.0]
    rad_str = cell.get("rad") or "1MeV e-"
    T_ref = cell.get("T_ref", 28.0)

    return convertir_flu_legacy(flu, rad_str, T_ref)


def fluence_equivalente_1MeV(radiation: dict) -> float:
    """[FR] Calcule la fluence équivalente 1 MeV électron.
    Source : Rapport RT3 CDS (RDC 3MeV→1MeV = 2.66 ; 9.5MeV→1MeV = 9.03).

    Returns None si NON_IDENTIFIABLE (RDC inconnu, particule non supportée).

    [EN] Computes 1 MeV electron equivalent fluence.
    Source: RT3 CDS report (RDC 3MeV→1MeV = 2.66; 9.5MeV→1MeV = 9.03).

    Returns None if NON_IDENTIFIABLE (unknown RDC, unsupported particle).
    """
    particule = radiation.get("particule")
    energie = radiation.get("energie_MeV", 1.0)
    fluence = radiation.get("fluence")

    if fluence is None:
        return None

    # Électrons : déjà en e⁻/cm² / Electrons: already in e⁻/cm²
    if particule == "electron":
        if abs(energie - 1.0) < 0.1:
            return fluence  # déjà 1 MeV / already 1 MeV
        else:
            # Nécessite NIEL(E) / NIEL(1MeV) — NON_IDENTIFIABLE sans table
            # Requires NIEL(E) / NIEL(1MeV) — NON_IDENTIFIABLE without table
            return None

    # Protons : utiliser RDC / Protons: use RDC
    elif particule == "proton":
        rdc = radiation.get("rdc_vers_1MeV_e")
        if rdc is None:
            # Cherche dans RDC_MESURES / Look up in RDC_MESURES
            for (p, e), rdc_val in RDC_MESURES.items():
                if p == "proton" and abs(e - energie) < 0.5:
                    rdc = rdc_val
                    break
        if rdc is not None:
            return [f * rdc for f in fluence] if isinstance(fluence, list) else fluence * rdc
        else:
            return None  # NON_IDENTIFIABLE

    # Autres particules : NON_IDENTIFIABLE / Other particles: NON_IDENTIFIABLE
    else:
        return None


def get_rdc(particule: str, energie_MeV: float):
    """[FR] Retourne le RDC mesuré ou None (NON_IDENTIFIABLE).
    [EN] Returns measured RDC or None (NON_IDENTIFIABLE)."""
    for (p, e), rdc in RDC_MESURES.items():
        if p == particule and abs(e - energie_MeV) < 0.5:
            return rdc
    return None  # NON_IDENTIFIABLE

# =============================================================================
# 7. FONCTIONS UTILITAIRES — DRAPEAUX / UTILITY FUNCTIONS — FLAGS
# =============================================================================
def _flags_phys(c: dict) -> dict:
    """[FR] Déduit les drapeaux de disponibilité depuis la cellule physique.
    [EN] Derives availability flags from the physical cell."""
    return dict(
        aire_dispo=int(c.get("area") is not None),
        ep_dispo=int(c.get("ep") is not None),
        coverglass_dispo=int(c.get("cg") is not None),
        tc_dispo=int(bool(c.get("tc") and c["tc"].get("f"))),
        flu_dispo=int(bool(c.get("flu"))),
        eff_dispo=int(c.get("eff") is not None),
        spectre_dispo=int(c.get("spectre") is not None),
        rad_dispo=int(c.get("rad") is not None),
        eol_dispo=int(bool(c.get("flu")) and len(c["flu"]) > 1),
        diode_dispo=0,
        datasheet_dispo=1,
        qualif_dispo=int(c.get("space_qualified", 1)),
        has_coverglass=int((c.get("cg") or 0) > 0),
        has_bypass_diode=0,
        has_contacts=1,
        space_qualified=int(c.get("space_qualified", 1)),
        terrestrial=int(c.get("terrestrial", 0)),
    )


def _flags_bench(c: dict) -> dict:
    """[FR] Drapeaux pour cellule benchmark (BOL only).
    [EN] Flags for benchmark cell (BOL only)."""
    return dict(
        aire_dispo=int(c.get("area") is not None),
        ep_dispo=0, coverglass_dispo=0, tc_dispo=0, flu_dispo=0,
        eff_dispo=int(c.get("eff") is not None),
        spectre_dispo=int(c.get("spectre") is not None),
        rad_dispo=0, eol_dispo=0, diode_dispo=0,
        datasheet_dispo=1, qualif_dispo=0,
        has_coverglass=0, has_bypass_diode=0,
        has_contacts=1, space_qualified=0,
        terrestrial=int(c.get("terrestrial", 1)),
    )

# =============================================================================
# 8. CONSTRUCTION DES ENREGISTREMENTS / RECORD BUILDING
# =============================================================================
def _record_phys(c: dict) -> dict:
    """[FR] Construit l'enregistrement uniforme d'une cellule physique.
    Applique la correction CESI si applicable + champs v28 + F3.
    [EN] Builds the uniform record of a physical cell.
    Applies CESI correction if applicable + v28 fields + F3."""
    ref = c["ref"]
    tech = c.get("tech")
    corr = CORRECTION_CESI.get(ref, {})

    # Champs de base / Base fields
    rec = dict(
        ref=ref,
        fabricant=c.get("fab"),
        tech=tech,
        N_s=c.get("N_s"),
        area_cm2=c.get("area"),
        ep_um=c.get("ep"),
        cg_um=c.get("cg"),
        T_ref_C=c.get("T_ref"),
        spectre=c.get("spectre"),
        rad=c.get("rad"),               # [v8] conservé mais DÉPRÉCIÉ
        flu=corr.get("flu", c.get("flu")),  # [v8] conservé mais DÉPRÉCIÉ
        Voc=corr.get("Voc", c.get("Voc")),
        Isc=corr.get("Isc", c.get("Isc")),
        Vmp=corr.get("Vmp", c.get("Vmp")),
        Imp=corr.get("Imp", c.get("Imp")),
        tc=corr.get("tc", c.get("tc")),
        tc_src=corr.get("tc_src", c.get("tc_src")),
        eff=c.get("eff"),
        note_fr=corr.get("note_fr", ""),
        note_en=corr.get("note_en", ""),
        # [v27-F4] Component type / Type de composant
        component_type=c.get("component_type", "bare_cell"),
        # [v27-F2] Provenance élec / Electrical provenance
        provenance_elec=corr.get("provenance_elec",
                                 c.get("provenance_elec", "measured")),
    )
    rec.update(_flags_phys(c))

    # Drapeau tc_interpole (calculé par le lecteur, généré à null)
    # tc_interpole flag (computed by loader, generated as null)
    rec["tc_interpole"] = None

    # =========================================================================
    # [v7] CHAMPS v28 / v28 FIELDS
    # =========================================================================
    # [v7-M22] Mécanismes applicables / Applicable mechanisms
    rec["mecanismes_applicables"] = MECANISMES_PAR_TECH.get(tech, {
        "degradation": ["DEG_RAD_001", "DEG_THM_012"],
        "recovery":    ["REC_007", "REC_008"],
    })

    # [v7-M23] Sous-cellules (TJ/QJ uniquement) / Subcells (TJ/QJ only)
    if tech == "TJ":
        rec["sous_cellules"] = SOUS_CELLULES_TJ
    elif tech == "QJ":
        rec["sous_cellules"] = SOUS_CELLULES_QJ
    else:
        rec["sous_cellules"] = None  # Si, GaAs, CIGS → pas de sous-cellules

    # [v7-M18] Recuit / Annealing
    # Règle d'honnêteté : A et Ea sont UNKNOWN (non fournis par les fabricants)
    # Honesty rule: A and Ea are UNKNOWN (not provided by manufacturers)
    rec["recuit"] = {
        "actif": False,
        "type_recuit": None,
        "familles": None,
        "T_profil": None,
        "note": ("UNKNOWN — paramètres Arrhenius (A, Ea) non fournis par le "
                 "fabricant. Requires isochronal annealing + DLTS."),
    }

    # [v7-M22] Fraction de dommage permanent / Permanent damage fraction
    rec["d_stable_fraction"] = None

    # [v7-CRYO] Recuit in-orbit / In-orbit annealing
    rec["in_orbit_annealing"] = None

    # [v7-CRYO] Profil mission / Mission profile
    rec["profil_mission"] = None

    # =========================================================================
    # [v8-F3] CHAMP RADIATION STRUCTURÉ / STRUCTURED RADIATION FIELD
    # =========================================================================
    rec["radiation"] = normaliser_radiation(rec)

    return rec


def _record_bench(c: dict) -> dict:
    """[FR] Construit l'enregistrement uniforme d'une cellule benchmark.
    [EN] Builds the uniform record of a benchmark cell."""
    rec = dict(
        ref=c["ref"], fabricant=c.get("fab"), tech=c.get("tech"),
        N_s=None, area_cm2=None, ep_um=None, cg_um=None, T_ref_C=None,
        spectre=None, rad=None, flu=None, Voc=None, Isc=None,
        Vmp=None, Imp=None, tc=None, tc_src=None, eff=c.get("eff"),
        component_type="bare_cell", provenance_elec="measured",
        note_fr="", note_en="",
    )
    rec.update(_flags_bench(c))
    rec["tc_interpole"] = None
    # [v7] Champs v28 pour benchmark / v28 fields for benchmark
    rec["mecanismes_applicables"] = None
    rec["sous_cellules"] = None
    rec["recuit"] = None
    rec["d_stable_fraction"] = None
    rec["in_orbit_annealing"] = None
    rec["profil_mission"] = None
    # [v8-F3] Champ radiation pour benchmark / Radiation field for benchmark
    rec["radiation"] = None
    return rec

# =============================================================================
# 9. GÉNÉRATION / GENERATION
# =============================================================================
def generer(sortie: Path = SORTIE) -> None:
    """[FR] Écrit le YAML uniforme (style bloc lisible) avec champs v28 + F3.
    [EN] Writes the uniform YAML in readable block style with v28 + F3 fields."""
    phys = [_record_phys(c) for c in d.CELLULES_PHYSIQUE]
    bench = [_record_bench(c) for c in d.CELLULES_BENCHMARK]
    data = {
        "meta": {
            "version": "2.3",  # v2.3 = v2.2 + F3 fluence structurée
            "schema": "uniforme",
            "langues": ["fr", "en"],
            "n_physique": len(phys),
            "n_benchmark": len(bench),
            "generateur": f"generer_yaml_uniforme.py v{__version__}",
            "unites": {
                "area_cm2": "cm²", "ep_um": "µm", "cg_um": "µm",
                "T_ref_C": "°C", "Voc": "mV", "Isc": "mA",
                "Vmp": "mV", "Imp": "mA",
            },
            "champs_v28": CHAMPS_V28,
            "champs_f3": CHAMPS_F3,
            "note_f3": ("[v8-F3] Le champ 'radiation' remplace 'flu' + 'rad'. "
                        "Les champs 'flu' et 'rad' sont conservés pour "
                        "backward compatibility mais sont DÉPRÉCIÉS."),
            "rdc_mesures": {
                "proton_3MeV_vers_1MeV_e": 2.66,
                "proton_9p5MeV_vers_1MeV_e": 9.03,
                "source": "Rapport RT3 CDS 25.DING.ING.PCCEC, p.6",
            },
        },
        "references": getattr(d, "REFERENCES_BIBLIOGRAPHIQUES", ""),
        "cellules_physique": phys,
        "cellules_benchmark": bench,
    }
    with open(sortie, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False,
                       default_flow_style=False, width=90)
    print(f"✅ {sortie} : {len(phys)} physiques + {len(bench)} benchmark "
          f"(schéma v2.3 avec champs v28 + F3)")

# =============================================================================
# 10. VÉRIFICATION / VERIFICATION
# =============================================================================
def verifier(sortie: Path = SORTIE) -> None:
    """[FR] Vérifie l'uniformité du schéma + champs v28 + F3 après écriture.
    [EN] Verifies schema uniformity + v28 + F3 fields after writing."""
    db = yaml.safe_load(open(sortie, encoding="utf-8"))
    oblig = (CHAMPS_VALEUR + CHAMPS_DISPO + CHAMPS_PROP + CHAMPS_V28
             + CHAMPS_F3 + ["tc_interpole"])
    n_bad = 0

    for c in db["cellules_physique"] + db["cellules_benchmark"]:
        for k in oblig:
            if k not in c:
                print(f"  ⚠️  {c.get('ref')}: champ manquant / missing {k}")
                n_bad += 1

    # [v7] Vérifications spécifiques v28 / v28-specific checks
    n_tj = n_qj = 0
    for c in db["cellules_physique"]:
        tech = c.get("tech")
        sc = c.get("sous_cellules")
        if tech == "TJ":
            n_tj += 1
            if not sc:
                print(f"  ⚠️  {c.get('ref')}: TJ sans sous_cellules")
                n_bad += 1
        elif tech == "QJ":
            n_qj += 1
            if not sc:
                print(f"  ⚠️  {c.get('ref')}: QJ sans sous_cellules")
                n_bad += 1
        elif sc is not None:
            print(f"  ⚠️  {c.get('ref')}: {tech} avec sous_cellules "
                  f"(devrait être null)")
            n_bad += 1
        # Vérification profil_mission / Mission profile check
        pm = c.get("profil_mission")
        if pm is not None and pm not in PROFILS_MISSION_VALIDES:
            print(f"  ⚠️  {c.get('ref')}: profil_mission '{pm}' invalide")
            n_bad += 1

    # [v8-F3] Vérifications spécifiques F3 / F3-specific checks
    n_rad = 0
    for c in db["cellules_physique"]:
        rad = c.get("radiation")
        if rad is None:
            print(f"  ⚠️  {c.get('ref')}: radiation absent (F3)")
            n_bad += 1
            continue
        for r in rad:
            n_rad += 1
            # Validation particule / Particle validation
            if r.get("particule") not in PARTICULES_VALIDES:
                print(f"  ⚠️  {c.get('ref')}: particule invalide "
                      f"'{r.get('particule')}'")
                n_bad += 1
            # Validation fluence_type / Fluence type validation
            if r.get("fluence_type", "experimental") not in FLUENCE_TYPES:
                print(f"  ⚠️  {c.get('ref')}: fluence_type invalide "
                      f"'{r.get('fluence_type')}'")
                n_bad += 1
            # Validation unité / Unit validation
            if r.get("unit") not in UNITES_FLUENCE:
                print(f"  ⚠️  {c.get('ref')}: unité invalide '{r.get('unit')}'")
                n_bad += 1
            # Validation fluence (liste de floats) / Fluence validation
            flu = r.get("fluence")
            if not isinstance(flu, list) or not all(isinstance(x, (int, float)) for x in flu):
                print(f"  ⚠️  {c.get('ref')}: fluence non-liste ou non-numérique")
                n_bad += 1

    # Récapitulatif / Summary
    if n_bad == 0:
        print(f"✅ Schéma uniforme OK + aucune anomalie / "
              f"uniform schema OK, no issue.")
        print(f"   TJ avec sous_cellules : {n_tj}")
        print(f"   QJ avec sous_cellules : {n_qj}")
        print(f"   Enregistrements radiation (F3) : {n_rad}")
        print(f"   Champs v28 présents : {', '.join(CHAMPS_V28)}")
        print(f"   Champs F3 présents : {', '.join(CHAMPS_F3)}")
    else:
        print(f"⚠️ {n_bad} champ(s) manquant(s) ou anomalie(s) / "
              f"missing field(s) or issue(s)")

# =============================================================================
# 11. POINT D'ENTRÉE / ENTRY POINT
# =============================================================================
def main():
    """[FR] Génère puis vérifie le YAML uniforme. [EN] Generate + verify YAML."""
    p = argparse.ArgumentParser(
        description=f"Générateur YAML uniforme v{__version__} "
                    f"(+ champs v28 + F3) / uniform YAML generator (+ v28 + F3)")
    p.add_argument("--sortie", default=str(SORTIE),
                   help="fichier de sortie / output file")
    a = p.parse_args()
    sortie = Path(a.sortie)
    generer(sortie)
    verifier(sortie)


if __name__ == "__main__":
    main()